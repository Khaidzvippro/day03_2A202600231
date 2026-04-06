import os
import json
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.openai_provider import OpenAIProvider

PROMPT = (
    "Tìm cho tôi 2 nghiên cứu về Alpha Momentum trên thị trường chứng khoán Mỹ "
    "được đăng trên ArXiv trong tháng 3 năm 2026 và trích xuất logic giao dịch của chúng thành JSON."
)

SYSTEM_PROMPT = """You are a financial research assistant with deep knowledge of quantitative finance and academic literature.
When asked about research papers, use your knowledge to provide the most relevant papers you know about.
If exact papers matching the query are not in your knowledge, provide the closest matching papers on the topic.
Always respond with a valid JSON array containing exactly 2 elements.
Each element must have exactly these fields:
{
  "title": "full paper title",
  "author": "author name(s)",
  "abstract": "brief abstract summary",
  "url": "arxiv paper URL",
  "published_date": "YYYY-MM-DD",
  "logic": {
    "category": "momentum / mean-reversion / etc.",
    "input_variable": "variables used (e.g. past returns, volume)",
    "economic_rationale": "why this strategy should work",
    "trading_logic": "step-by-step logic of the strategy",
    "direction": "long / short / long-short"
  }
}
Return only the raw JSON array, no markdown, no explanation."""


def run_chatbot() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("DEFAULT_MODEL", "gpt-4o")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env file.")

    provider = OpenAIProvider(model_name=model, api_key=api_key)

    print("=" * 60)
    print("BASE CHATBOT — OpenAI API")
    print(f"Model : {model}")
    print("=" * 60)
    print(f"Prompt: {PROMPT}\n")

    result = provider.generate(prompt=PROMPT, system_prompt=SYSTEM_PROMPT)

    raw_content = result["content"]

    print("--- Raw Response ---")
    print(raw_content)
    print()

    try:
        papers = json.loads(raw_content)
        print("--- Parsed JSON ---")
        print(json.dumps(papers, ensure_ascii=False, indent=2))
    except json.JSONDecodeError as e:
        print(f"[Warning] Could not parse response as JSON: {e}")

    print("\n--- Telemetry ---")
    print(f"Latency  : {result['latency_ms']} ms")
    print(f"Tokens   : {result['usage']}")
    print(f"Provider : {result['provider']}")


if __name__ == "__main__":
    run_chatbot()
