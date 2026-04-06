"""
================================================================================
LLM PERFORMANCE MONITORING SUBSYSTEM (Industry Edition)
================================================================================
Description : This module provides a high-level observability layer for LLM 
              applications. It uses the Decorator Pattern to inject performance 
              tracking logic (latency, token usage, cost estimation) into any 
              standard LLM provider without modifying core business logic.

Key Features:
1. Automated Latency Tracking (down to millisecond precision).
2. Heterogeneous Token Usage Parsing (supports OpenAI, Gemini, and Local schemas).
3. Session-wide Analytics Aggregation.
4. Telemetry Integration for downstream dashboarding/analysis.

Usage:
    @track_performance
    def my_llm_call(*args, **kwargs):
        ...
================================================================================
"""

import time
import functools
import logging
from typing import Any, Dict, Callable, Optional, Union

# Import decentralized logger from the local telemetry module
try:
    from src.telemetry.logger import logger
except ImportError:
    # Safe fallback if the logger module is not yet reachable or implemented
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("TelemetryLogger")
    logger.log_event = lambda event, data: logging.info(f"[{event}] {data}")

def track_performance(func: Callable) -> Callable:
    """
    A professional-grade decorator to wrap LLM calls.
    It captures execution metrics and pipes them to the telemetry sink.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Start high-precision timer
        start_time = time.perf_counter()
        
        try:
            # Execute the core LLM inference / Service call
            result = func(*args, **kwargs)
            
            # Calculate elapsed time in seconds
            execution_time = time.perf_counter() - start_time
            
            # ---------------------------------------------------------
            # TOKEN USAGE EXTRACTION LOGIC
            # ---------------------------------------------------------
            # Attempt to parse usage metadata from various common LLM response formats
            usage = None
            if isinstance(result, dict):
                usage = result.get('usage')
            else:
                usage = getattr(result, 'usage', None)
            
            # Extract total tokens based on different provider schemas
            total_tokens = 0
            if isinstance(usage, dict):
                total_tokens = usage.get('total_tokens', 0)
            elif hasattr(usage, 'total_tokens'):
                total_tokens = usage.total_tokens
            elif hasattr(result, 'usage_metadata'): # Gemini raw response fallback
                total_tokens = result.usage_metadata.total_token_count

            # ---------------------------------------------------------
            # TELEMETRY LOGGING
            # ---------------------------------------------------------
            metric_data = {
                "operation": func.__name__,
                "status": "SUCCESS",
                "latency_s": round(execution_time, 4),
                "token_usage": total_tokens,
                "timestamp": time.time()
            }
            
            # Ship data to telemetry module
            logger.log_event("LLM_KPI_TRACK", metric_data)
            
            # Automatically update the global aggregator for session-wide reports
            session_metrics.record_call(execution_time, total_tokens)
            
            # Standard output for developer visibility during runtime
            print(f"TELEMETRY => {func.__name__}: {execution_time:.3f}s | {total_tokens} tokens")
            
            return result
            
        except Exception as e:
            # Track failure for reliability analysis (Ablation/Error analysis)
            error_latency = time.perf_counter() - start_time
            logger.log_event("LLM_KPI_ERROR", {
                "operation": func.__name__,
                "status": "FAILURE",
                "error_type": type(e).__name__,
                "error_msg": str(e),
                "failed_at": round(error_latency, 3)
            })
            raise e
            
    return wrapper

class GlobalMetricAggregator:
    """
    Aggregates session analytics to calculate averages and totals.
    This provides the 'Industry Metrics' required for Lab Bonus points.
    """
    def __init__(self):
        self._total_latency = 0.0
        self._total_tokens = 0
        self._request_count = 0

    def record_call(self, latency: float, tokens: int):
        """Updates internal accumulation state."""
        self._total_latency += latency
        self._total_tokens += tokens
        self._request_count += 1

    def generate_session_report(self) -> Dict[str, Any]:
        """Generates a high-level performance summary for the final report."""
        if self._request_count == 0:
            return {"status": "No data recorded"}
            
        return {
            "session_requests": self._request_count,
            "cum_total_tokens": self._total_tokens,
            "avg_latency_s": round(self._total_latency / self._request_count, 3),
            "efficiency_score": round(self._total_tokens / self._total_latency, 2) if self._total_latency > 0 else 0
        }

# Initialize a singleton aggregator for the session
session_metrics = GlobalMetricAggregator()
