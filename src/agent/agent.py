import re
import time
from typing import List, Dict, Any, Optional
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger


class ReActAgent:
    """
    ReAct-style Agent following the Thought → Action → Observation loop.
    Supports: search_arxiv, get_paper_summary, alpha_formatter,
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

Output format for EVERY step (never skip Thought):
Thought: <your reasoning about what to do next>
Action: <tool_name>(key="value", key2=value2)
Observation: <system will fill this in>

Repeat Thought/Action/Observation until you have all information needed.
When finished, write:
Final Answer: <your complete response>

Operational rules:
1. Always start with search_arxiv to find relevant papers.
2. Call get_paper_summary for EACH paper found to obtain its abstract.
3. Call alpha_formatter with the raw abstract to produce structured JSON.
   If alpha_formatter returns a validation error, fix the input and retry.
4. Call guardrail_validator on the final JSON before writing Final Answer.
5. Never fabricate paper IDs or abstracts — only use data from Observations.
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
        for tool in self.tools:
            if tool["name"] == tool_name:
                fn = tool.get("function")
                if not callable(fn):
                    return f"[Error] Tool '{tool_name}' has no callable function defined."
                try:
                    kwargs = self._parse_args(args_str)
                    return str(fn(**kwargs))
                except Exception as exc:
                    return f"[Error] {tool_name} raised: {exc}"

        available = [t["name"] for t in self.tools]
        return f"[Error] Tool '{tool_name}' not found. Available tools: {available}"

    # ------------------------------------------------------------------
    # Argument Parser  (key="val", key=123, key=word)
    # ------------------------------------------------------------------

    def _parse_args(self, args_str: str) -> Dict[str, Any]:
        if not args_str.strip():
            return {}

        kwargs: Dict[str, Any] = {}
        pattern = r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[\w.\-]+)'

        for match in re.finditer(pattern, args_str):
            key = match.group(1)
            raw = match.group(2)

            # Strip surrounding quotes
            if (raw.startswith('"') and raw.endswith('"')) or \
               (raw.startswith("'") and raw.endswith("'")):
                val: Any = raw[1:-1]
            else:
                # Try numeric coercion
                try:
                    val = int(raw)
                except ValueError:
                    try:
                        val = float(raw)
                    except ValueError:
                        val = raw

            kwargs[key] = val

        return kwargs

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
