import time
from typing import Any, Callable, Dict, Optional

from src.telemetry.logger import logger
from src.telemetry.metrics import tracker


def track_llm_result(
    result: Dict[str, Any],
    fallback_provider: Optional[str] = None,
    fallback_model: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Normalize and record telemetry for a successful LLM call.
    Returns the same result payload for convenient chaining.
    """
    usage = result.get("usage", {}) or {}
    tracker.track_request(
        provider=result.get("provider") or fallback_provider or "unknown",
        model=result.get("model") or fallback_model or "unknown",
        usage={
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        latency_ms=int(result.get("latency_ms", 0) or 0),
        metadata=metadata,
    )
    return result


def track_llm_error(
    provider: str,
    model: str,
    error: Exception,
    latency_ms: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    payload: Dict[str, Any] = {
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    if metadata:
        payload.update(metadata)

    logger.log_event("LLM_ERROR", payload)


def track_performance(
    provider: str,
    model: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    Decorator for wrapping a function that returns an LLM result dict.
    Expected keys in result: usage, latency_ms, provider, model.
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return track_llm_result(
                    result,
                    fallback_provider=provider,
                    fallback_model=model,
                    metadata=metadata,
                )
            except Exception as exc:
                latency_ms = int((time.time() - start) * 1000)
                track_llm_error(
                    provider=provider,
                    model=model,
                    error=exc,
                    latency_ms=latency_ms,
                    metadata=metadata,
                )
                raise

        return wrapper

    return decorator
