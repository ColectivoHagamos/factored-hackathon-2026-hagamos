"""Operational view of the service (P54): structured logs, a trace per conversation and counters.

Logs are one JSON object per line and carry no personal data: no message text, no customer reference, only route
templates, statuses, timings, rule ids, tool names and the conversation id, which is random. The conversation id is
the trace id: with it, the request lines, the turn lines and the hash-chained event log tell one story end to end.
"""

import json
import logging
import statistics
import threading
from collections import Counter, deque
from collections.abc import Sequence
from datetime import UTC, datetime

from vera.contracts.events import Event, EventType

logger = logging.getLogger("vera.operations")
LATENCY_SAMPLES = 2000


def log_event(event: str, **fields: object) -> None:
    record = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), "event": event, **fields}
    logger.info(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str))


def configure_logging() -> None:
    """Operations lines go to standard output as plain JSON, without the prefix of the root logger."""
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def turn_summary(events: Sequence[Event]) -> dict:
    """What one turn did, from its events: rules applied, tools and their results, transfer and safety flags."""
    start = max((i for i, e in enumerate(events) if e.type is EventType.CUSTOMER_MESSAGE), default=0)
    turn = events[start:]
    rules = [e.data.get("rule") for e in turn if e.type is EventType.RULE_DECISION]
    results = [(e.data.get("tool"), e.data.get("result")) for e in turn if e.type is EventType.TOOL_RESULT]
    handoffs = [e.data.get("queue") for e in turn if e.type is EventType.HANDOFF]
    return {
        "rules": [rule for rule in rules if rule and rule != "output_validator"],
        "tools": [f"{tool}:{result}" for tool, result in results],
        "tool_failures": sum(result in ("failure", "timeout") for _, result in results),
        "handoff": handoffs[-1] if handoffs else None,
        "security_event": any(e.type is EventType.SECURITY_EVENT for e in turn),
        "validator_blocked": "output_validator" in rules,
        "fraud_alert": any(e.type is EventType.FRAUD_ALERT for e in turn),
    }


class Metrics:
    """Counters since the process started; enough to watch the demo and to set the alerts of docs/operations.md."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()
        self._request_ms: deque[float] = deque(maxlen=LATENCY_SAMPLES)
        self._turn_ms: deque[float] = deque(maxlen=LATENCY_SAMPLES)

    def request(self, status: int, ms: float) -> None:
        with self._lock:
            self._counts["requests"] += 1
            self._counts[f"responses_{status // 100}xx"] += 1
            self._request_ms.append(ms)

    def turn(self, summary: dict, ms: float) -> None:
        with self._lock:
            self._counts["turns"] += 1
            self._counts["tool_failures"] += summary["tool_failures"]
            self._counts["security_events"] += summary["security_event"]
            self._counts["validator_blocks"] += summary["validator_blocked"]
            self._counts["fraud_alerts"] += summary["fraud_alert"]
            if summary["handoff"]:
                self._counts[f"handoffs_{summary['handoff']}"] += 1
            self._turn_ms.append(ms)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counts": dict(sorted(self._counts.items())),
                "request_ms": _percentiles(self._request_ms),
                "turn_ms": _percentiles(self._turn_ms),
            }


def _percentiles(values: deque[float]) -> dict:
    if len(values) < 2:
        return {"n": len(values), "p50": values[0] if values else None, "p95": values[0] if values else None}
    cuts = statistics.quantiles(values, n=20)
    return {"n": len(values), "p50": round(statistics.median(values), 1), "p95": round(cuts[18], 1)}
