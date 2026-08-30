
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from shared.logging import get_logger, log_step

logger = get_logger("healthlink.observability")

@dataclass
class TraceStep:

    name: str
    latency_ms: float
    detail: str = ""

@dataclass
class Trace:

    request_id: str
    steps: list[TraceStep] = field(default_factory=list)

    def add(self, name: str, latency_ms: float, detail: str = "") -> None:
        self.steps.append(TraceStep(name=name, latency_ms=latency_ms, detail=detail))
        log_step(logger, name, latency_ms, event="agent_step")

    def summary(self) -> dict:
        return {
            "request_id": self.request_id,
            "total_ms": round(sum(s.latency_ms for s in self.steps), 1),
            "steps": [
                {"step": s.name, "latency_ms": round(s.latency_ms, 1), "detail": s.detail}
                for s in self.steps
            ],
        }

@contextmanager
def timed(step_name: str, trace: Trace | None = None, detail: str = ""):

    start = time.monotonic()
    try:
        yield
    finally:
        elapsed = (time.monotonic() - start) * 1000
        if trace is not None:
            trace.add(step_name, elapsed, detail)
        else:
            log_step(logger, step_name, elapsed, event="agent_step")
