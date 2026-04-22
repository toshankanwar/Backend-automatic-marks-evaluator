import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ProcessTracker:
    def __init__(self, submission_id: str, student_id: Optional[str] = None):
        self.submission_id = submission_id
        self.student_id = student_id
        self._t0 = time.perf_counter()
        self._stage_start: Dict[str, float] = {}
        self.stage_ms: Dict[str, int] = {}
        self.events: List[Dict[str, Any]] = []

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def log(self, event: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self.events.append({
            "event": event,
            "timestamp": self._now_iso(),
            "submission_id": self.submission_id,
            "student_id": self.student_id,
            "meta": meta or {}
        })

    def stage_start(self, stage: str) -> None:
        self._stage_start[stage] = time.perf_counter()
        self.log(f"{stage.upper()}_STARTED")

    def stage_end(self, stage: str, meta: Optional[Dict[str, Any]] = None) -> None:
        st = self._stage_start.get(stage)
        dur = int((time.perf_counter() - st) * 1000) if st is not None else None
        if dur is not None:
            self.stage_ms[f"{stage}_ms"] = dur
        payload = {"duration_ms": dur}
        if meta:
            payload.update(meta)
        self.log(f"{stage.upper()}_COMPLETED", payload)

    def finalize(self) -> Dict[str, Any]:
        total_ms = int((time.perf_counter() - self._t0) * 1000)
        self.log("RESULT_PUBLISHED", {"total_ms": total_ms})
        return {
            "total_ms": total_ms,
            **self.stage_ms
        }