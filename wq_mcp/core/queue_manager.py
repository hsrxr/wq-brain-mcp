from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wq_mcp.config import MAX_CONCURRENT, MAX_QUEUE_RETRIES, MAX_QUEUE_SIZE, MAX_POLL_RETRIES
from wq_mcp.core.api_client import (
    WqApiClient,
    RateLimitError,
    ValidationError,
    WqApiError,
    _extract_metrics,
)
from wq_mcp.logging_config import get_logger

logger = get_logger(__name__)


class FactorQueueManager:
    """Manages factor submission queue with 3-concurrent enforcement.

    Pure business logic — knows NOTHING about MCP.
    All external I/O happens through the injected WqApiClient.

    State lifecycle (in memory, persistable to JSON):
      _queue:    FIFO list of expressions waiting for a free slot
      _active:   dict of currently running/polling simulation jobs
      _completed: dict of finished simulation results
    """

    def __init__(
        self,
        api_client: WqApiClient,
        state_path: Path | None = None,
    ) -> None:
        self._api = api_client
        self._state_path = state_path

        # In-memory state
        self._queue: list[dict[str, Any]] = []
        self._active: dict[str, dict[str, Any]] = {}
        self._completed: dict[str, dict[str, Any]] = {}
        self._expression_history: set[str] = set()

        # Try to restore from disk
        if state_path and state_path.exists():
            self._load_state()

    # ── Properties ──

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def queued_count(self) -> int:
        return len(self._queue)

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    # ── Submission ──

    def submit(
        self,
        expression: str,
        settings: dict[str, Any] | None = None,
        dataset_id: str = "",
    ) -> dict[str, Any]:
        """Submit a factor or enqueue it if slots are full.

        Returns:
            {"status": "submitted"|"queued"|"failed",
             "job_id": str|None, "message": str,
             "position_in_queue": int|None}
        """
        # Track expression (normalized) for dedup history
        norm = expression.strip().replace(" ", "")
        self._expression_history.add(norm)

        final_settings = dict(settings) if settings else {}

        if self.active_count < MAX_CONCURRENT:
            return self._submit_immediately(expression, final_settings, dataset_id)
        else:
            return self._enqueue(expression, final_settings, dataset_id)

    def _submit_immediately(
        self, expression: str, settings: dict[str, Any], dataset_id: str
    ) -> dict[str, Any]:
        """Submit directly to WQ API without queueing."""
        try:
            result = self._api.submit_simulation(expression, settings)
            job_id = result.get("job_id", "")
            location_url = result.get("location_url", "")

            self._active[job_id] = {
                "job_id": job_id,
                "expression": expression,
                "settings": settings,
                "dataset_id": dataset_id,
                "location_url": location_url,
                "status": "running",
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "poll_retries": 0,
            }

            self._persist_state()
            logger.info("Submitted: job_id=%s expr=%s…", job_id, expression[:60])
            return {"status": "submitted", "job_id": job_id, "message": "Simulation started", "position_in_queue": None}

        except RateLimitError as e:
            return self._enqueue(expression, settings, dataset_id, rate_limited=True)
        except ValidationError as e:
            return {"status": "failed", "job_id": None, "message": str(e), "position_in_queue": None}
        except WqApiError as e:
            return {"status": "failed", "job_id": None, "message": str(e), "position_in_queue": None}

    def _enqueue(
        self,
        expression: str,
        settings: dict[str, Any],
        dataset_id: str,
        rate_limited: bool = False,
    ) -> dict[str, Any]:
        """Add expression to the FIFO queue."""
        if len(self._queue) >= MAX_QUEUE_SIZE:
            # Drop oldest
            dropped = self._queue.pop(0)
            logger.warning("Queue full, dropped oldest entry: %s…", dropped.get("expression", "")[:60])

        entry = {
            "expression": expression,
            "settings": settings,
            "dataset_id": dataset_id,
            "retry_count": 0,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }
        self._queue.append(entry)

        msg = "Rate limited, queued for retry" if rate_limited else "All slots full, queued"
        logger.info("Queued: %s (rate_limited=%s)", expression[:60], rate_limited)

        self._persist_state()
        return {
            "status": "queued",
            "job_id": None,
            "message": msg,
            "position_in_queue": len(self._queue),
        }

    # ── Polling ──

    def poll(self) -> dict[str, Any]:
        """Poll all active jobs and pump the queue.

        Returns:
            {"completed": [...], "running": [...], "queued": [...],
             "active_count": int, "queued_count": int, "connection_ok": bool}
        """
        connection_ok = True
        newly_completed: list[dict[str, Any]] = []

        # ── 1. Poll all active jobs ──
        job_ids = list(self._active.keys())
        for jid in job_ids:
            job = self._active.get(jid)
            if job is None:
                continue

            try:
                poll_result = self._api.poll_simulation(job["location_url"])
                status = poll_result.get("status", "failed")

                if status == "completed":
                    alpha_id = poll_result.get("alpha_id")
                    if alpha_id:
                        try:
                            alpha_detail = self._api.get_alpha_detail(alpha_id)
                            metrics = _extract_metrics(alpha_detail)
                        except WqApiError as e:
                            logger.warning("Failed to fetch alpha detail for %s: %s", alpha_id, e)
                            metrics = {}
                    else:
                        metrics = {}

                    completed = {
                        "job_id": jid,
                        "expression": job["expression"],
                        "settings": job.get("settings", {}),
                        "alpha_id": alpha_id,
                        "metrics": metrics,
                        "status": "completed",
                        "error": "",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    self._completed[jid] = completed
                    del self._active[jid]
                    newly_completed.append(completed)
                    logger.info("Job completed: jid=%s sharpe=%s", jid, metrics.get("sharpe"))

                elif status == "running":
                    job["status"] = "running"
                    # Ensure poll_retries resets on successful poll
                    job["poll_retries"] = 0

                else:
                    # failed / unknown — retry logic
                    job["poll_retries"] = job.get("poll_retries", 0) + 1
                    if job["poll_retries"] >= MAX_POLL_RETRIES:
                        # Give up
                        failed = {
                            "job_id": jid,
                            "expression": job["expression"],
                            "settings": job.get("settings", {}),
                            "alpha_id": None,
                            "metrics": {},
                            "status": "failed",
                            "error": f"Poll failed after {MAX_POLL_RETRIES} retries",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        }
                        self._completed[jid] = failed
                        del self._active[jid]
                        newly_completed.append(failed)
                        logger.warning("Job failed after retries: %s", jid)
                    else:
                        logger.debug("Job %s: poll_retry %d/%d", jid, job["poll_retries"], MAX_POLL_RETRIES)

            except WqApiError as e:
                logger.warning("Poll error for %s: %s", jid, e)
                job["poll_retries"] = job.get("poll_retries", 0) + 1
                if job["poll_retries"] >= MAX_POLL_RETRIES:
                    failed = {
                        "job_id": jid,
                        "expression": job["expression"],
                        "settings": job.get("settings", {}),
                        "alpha_id": None,
                        "metrics": {},
                        "status": "failed",
                        "error": str(e),
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                    self._completed[jid] = failed
                    del self._active[jid]
                    newly_completed.append(failed)
                connection_ok = False

        # ── 2. Pump queue — submit waiting entries if slots free ──
        self._pump_queue()

        # ── 3. Build response ──
        running_list = []
        for job in self._active.values():
            wait = 0
            if job.get("submitted_at"):
                try:
                    submitted = datetime.fromisoformat(job["submitted_at"])
                    wait = int((datetime.now(timezone.utc) - submitted).total_seconds())
                except (ValueError, TypeError):
                    pass
            running_list.append({
                "job_id": job["job_id"],
                "expression": job["expression"],
                "settings": job.get("settings", {}),
                "status": job.get("status", "running"),
                "submitted_at": job.get("submitted_at", ""),
                "wait_seconds": wait,
            })

        queued_list = [
            {
                "expression": e["expression"],
                "settings": e.get("settings", {}),
                "position": i + 1,
                "enqueued_at": e.get("enqueued_at", ""),
                "retry_count": e.get("retry_count", 0),
            }
            for i, e in enumerate(self._queue)
        ]

        self._persist_state()

        return {
            "completed": newly_completed,
            "running": running_list,
            "queued": queued_list,
            "active_count": self.active_count,
            "queued_count": self.queued_count,
            "connection_ok": connection_ok,
        }

    # ── Queue pump ──

    def _pump_queue(self) -> int:
        """Dequeue and submit waiting entries while slots are free.

        Returns:
            number of entries successfully submitted
        """
        submitted = 0
        while self.active_count < MAX_CONCURRENT and self._queue:
            entry = self._queue.pop(0)
            try:
                result = self._api.submit_simulation(entry["expression"], entry["settings"])
                job_id = result.get("job_id", "")
                location_url = result.get("location_url", "")

                self._active[job_id] = {
                    "job_id": job_id,
                    "expression": entry["expression"],
                    "settings": entry["settings"],
                    "dataset_id": entry.get("dataset_id", ""),
                    "location_url": location_url,
                    "status": "running",
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "poll_retries": 0,
                }
                submitted += 1
                logger.info("Dequeued and submitted: job_id=%s", job_id)

            except RateLimitError:
                # Re-queue with retry count
                entry["retry_count"] = entry.get("retry_count", 0) + 1
                if entry["retry_count"] < MAX_QUEUE_RETRIES:
                    self._queue.insert(0, entry)  # Put back at front
                    logger.warning("Rate limited during pump, will retry (attempt %d/%d)", entry["retry_count"], MAX_QUEUE_RETRIES)
                    break  # Stop pumping — likely to hit rate limit on next too
                else:
                    logger.error("Queue entry dropped after %d retries: %s…", MAX_QUEUE_RETRIES, entry.get("expression", "")[:60])

            except (ValidationError, WqApiError) as e:
                logger.error("Queue entry failed: %s — %s", entry.get("expression", "")[:60], e)
                # Entry is dropped (failed validation or API error)

        return submitted

    # ── Status queries ──

    def get_status(self) -> dict[str, Any]:
        """Return current queue status summary."""
        active_jobs = []
        for job in self._active.values():
            wait = 0
            if job.get("submitted_at"):
                try:
                    submitted = datetime.fromisoformat(job["submitted_at"])
                    wait = int((datetime.now(timezone.utc) - submitted).total_seconds())
                except (ValueError, TypeError):
                    pass
            active_jobs.append({
                "job_id": job["job_id"],
                "expression": job["expression"],
                "settings": job.get("settings", {}),
                "status": job.get("status", "running"),
                "submitted_at": job.get("submitted_at", ""),
                "wait_seconds": wait,
            })

        queued_entries = [
            {
                "expression": e["expression"],
                "settings": e.get("settings", {}),
                "position": i + 1,
                "enqueued_at": e.get("enqueued_at", ""),
                "retry_count": e.get("retry_count", 0),
            }
            for i, e in enumerate(self._queue)
        ]

        return {
            "active_count": self.active_count,
            "queued_count": self.queued_count,
            "completed_count": self.completed_count,
            "active_jobs": active_jobs,
            "queued_entries": queued_entries,
            "expression_history_count": len(self._expression_history),
        }

    def get_completed_since(self, since_job_id: str | None = None) -> list[dict[str, Any]]:
        """Return completed jobs. Optionally filter to those after a given job_id."""
        if since_job_id is None:
            return list(self._completed.values())

        found = False
        results = []
        for jid, job in self._completed.items():
            if found:
                results.append(job)
            elif jid == since_job_id:
                found = True
        return results

    def forget_completed(self, job_ids: list[str]) -> None:
        """Remove specific jobs from completed store."""
        for jid in job_ids:
            self._completed.pop(jid, None)

    # ── State persistence ──

    def _persist_state(self) -> None:
        if not self._state_path:
            return
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "active": {k: v for k, v in self._active.items()},
                "completed": {k: v for k, v in self._completed.items()},
            }
            import json
            self._state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to persist state: %s", e)

    def _load_state(self) -> None:
        try:
            import json
            state = json.loads(self._state_path.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            self._active = {k: v for k, v in state.get("active", {}).items() if v.get("status") == "running"}
            self._completed = state.get("completed", {})
            logger.info("Restored state: %d active, %d completed", len(self._active), len(self._completed))
        except Exception as e:
            logger.warning("Failed to load state: %s", e)
