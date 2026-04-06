import re
import time
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger


class ReActAgent:
    """
    ReAct-style Agent following the Thought → Action → Observation loop.
    Supports: search_arxiv, get_paper_abstract, alpha_formatter,
              performance_monitor (BONUS), guardrail_validator.
    """

    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 10):
        self.llm = llm
        self.tools = tools
        self.max_steps = max_steps
        self.history = []

    # ------------------------------------------------------------------
    # System Prompt
    # ------------------------------------------------------------------

    def get_system_prompt(self) -> str:
        tool_descriptions = "\n".join(
            [f"  - {t['name']}: {t['description']}" for t in self.tools]
        )
        return f"""You are an expert quantitative finance research assistant.
You follow the ReAct reasoning framework strictly.

Available tools:
{tool_descriptions}

Output format for EVERY step — output ONLY ONE block per turn:
Thought: <your reasoning about what to do next>
Action: <tool_name>(param_name="value")

STOP after writing Action. Do NOT write Observation yourself — the system fills it in.
Do NOT write Final Answer in the same turn as an Action.

CRITICAL — always use the exact parameter names:
- search_arxiv(query="your keywords")
- get_paper_abstract(paper_id="2401.12345")
- alpha_formatter(text="full paper text here")

Only after you have received all Observations AND called alpha_formatter, write:
Final Answer: <your complete response>

Mandatory workflow (do NOT skip any step):
1. search_arxiv(query=...) — returns at most 3 papers.
2. get_paper_abstract(paper_id=...) — call for EACH of the (up to 3) papers found.
3. alpha_formatter(text=...) — call for EACH paper after getting its abstract.
4. Final Answer — only after ALL papers have been processed through steps 2 and 3.
5. Never fabricate paper IDs or abstracts — only use IDs/data from Observations.
6. Do NOT search again if you already have up to 3 papers — proceed to step 2 immediately.
"""

    # ------------------------------------------------------------------
    # Main ReAct Loop
    # ------------------------------------------------------------------

    def run(self, user_input: str) -> str:
        logger.log_event("AGENT_START", {"input": user_input, "model": self.llm.model_name})

        scratchpad = user_input
        steps = 0

        while steps < self.max_steps:
            step_start = time.time()

            result = self.llm.generate(scratchpad, system_prompt=self.get_system_prompt())
            response_text = result["content"]
            step_latency_ms = int((time.time() - step_start) * 1000)

            logger.log_event("AGENT_STEP", {
                "step": steps + 1,
                "latency_ms": step_latency_ms,
                "tokens": result.get("usage", {}),
                "preview": response_text[:300],
            })

            self._call_performance_monitor(
                step=steps + 1,
                latency_ms=step_latency_ms,
                usage=result.get("usage", {}),
            )

            # ── Final Answer ──────────────────────────────────────────
            if "Final Answer:" in response_text:
                final = response_text.split("Final Answer:", 1)[-1].strip()
                logger.log_event("AGENT_END", {"steps": steps + 1, "status": "success"})
                return final

            # ── Parse & Execute Action ────────────────────────────────
            action_match = re.search(
                r"Action:\s*(\w+)\(([^)]*)\)", response_text, re.DOTALL
            )
            if action_match:
                tool_name = action_match.group(1).strip()
                args_str = action_match.group(2).strip()
                observation = self._execute_tool(tool_name, args_str)

                logger.log_event("TOOL_CALL", {
                    "tool": tool_name,
                    "args": args_str,
                    "observation": str(observation)[:400],
                })

                scratchpad += f"\n{response_text}\nObservation: {observation}"
            else:
                # No action found — append response and continue
                scratchpad += f"\n{response_text}"

            steps += 1

        logger.log_event("AGENT_END", {"steps": steps, "status": "max_steps_reached"})

        if "Final Answer:" in scratchpad:
            return scratchpad.split("Final Answer:", 1)[-1].strip()
        return "Agent reached maximum steps without producing a Final Answer."

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------

    def _execute_tool(self, tool_name: str, args_str: str) -> str:
        import inspect

        for tool in self.tools:
            if tool["name"] == tool_name:
                fn = tool.get("function")
                if not callable(fn):
                    return f"[Error] Tool '{tool_name}' has no callable function defined."
                try:
                    kwargs = self._parse_args(args_str, fn)
                    return str(fn(**kwargs))
                except TypeError:
                    # Wrong param names — remap values to positional params in order
                    try:
                        params = list(inspect.signature(fn).parameters.keys())
                        values = list(self._parse_args(args_str, fn).values())
                        remapped = {params[i]: values[i] for i in range(min(len(params), len(values)))}
                        return str(fn(**remapped))
                    except Exception as exc2:
                        return f"[Error] {tool_name} raised: {exc2}"
                except Exception as exc:
                    return f"[Error] {tool_name} raised: {exc}"

        available = [t["name"] for t in self.tools]
        return f"[Error] Tool '{tool_name}' not found. Available tools: {available}"

    # ------------------------------------------------------------------
    # Argument Parser
    # Handles: key="val", key=123, key=word, and bare positional strings
    # ------------------------------------------------------------------

    def _parse_args(self, args_str: str, fn: Any = None) -> Dict[str, Any]:
        import inspect

        if not args_str.strip():
            return {}

        kwargs: Dict[str, Any] = {}
        kw_pattern = r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[\w.\-]+)'

        for match in re.finditer(kw_pattern, args_str):
            key = match.group(1)
            raw = match.group(2)
            kwargs[key] = self._coerce(raw)

        # If no kwargs matched, treat the whole string as a positional arg
        # and map it to the first parameter of the function
        if not kwargs and args_str.strip():
            raw = args_str.strip().strip('"\'')
            if fn is not None:
                try:
                    first_param = next(iter(inspect.signature(fn).parameters))
                    kwargs[first_param] = raw
                except (StopIteration, ValueError):
                    pass

        return kwargs

    def _coerce(self, raw: str) -> Any:
        """Strip quotes and coerce numeric strings."""
        if (raw.startswith('"') and raw.endswith('"')) or \
           (raw.startswith("'") and raw.endswith("'")):
            return raw[1:-1]
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            return raw

    # ------------------------------------------------------------------
    # Performance Monitor (BONUS) — called directly, not via LLM loop
    # ------------------------------------------------------------------

    def _call_performance_monitor(self, step: int, latency_ms: int, usage: Dict) -> None:
        for tool in self.tools:
            if tool["name"] == "performance_monitor":
                fn = tool.get("function")
                if callable(fn):
                    try:
                        fn(step=step, latency_ms=latency_ms, usage=usage)
                    except Exception as exc:
                        logger.error(f"performance_monitor error: {exc}", exc_info=False)
                break
