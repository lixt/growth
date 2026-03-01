from __future__ import annotations

import copy
from collections import OrderedDict
from datetime import datetime
from threading import Lock
from typing import Any, Optional
from uuid import uuid4


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TaskTracker:
    def __init__(self, max_tasks: int = 200):
        self._tasks: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._lock = Lock()
        self._max_tasks = max_tasks

    def create_task(self, mode: str, date: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        task_id = uuid4().hex[:12]
        task = {
            "id": task_id,
            "mode": mode,
            "date": date,
            "payload": payload or {},
            "status": "queued",
            "error": None,
            "created_at": _now_str(),
            "started_at": None,
            "finished_at": None,
            "steps": OrderedDict(),
            "progress": {"done": 0, "total": 0, "percent": 0.0},
            "task_count": 0,
        }
        with self._lock:
            self._tasks[task_id] = task
            while len(self._tasks) > self._max_tasks:
                self._tasks.popitem(last=False)
            return copy.deepcopy(task)

    def start_task(self, task_id: str):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["status"] = "running"
            task["started_at"] = task["started_at"] or _now_str()

    def set_step(
        self,
        task_id: str,
        step_key: str,
        name: str,
        total: int = 0,
    ):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            steps: OrderedDict[str, dict[str, Any]] = task["steps"]
            step = {
                "key": step_key,
                "name": name,
                "status": "running",
                "done": 0,
                "total": max(total, 0),
                "percent": 0.0,
                "message": "",
            }
            steps[step_key] = step
            task["task_count"] = len(steps)
            self._recalc(task)

    def update_step(
        self,
        task_id: str,
        step_key: str,
        done: Optional[int] = None,
        total: Optional[int] = None,
        message: Optional[str] = None,
        status: Optional[str] = None,
    ):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            step = task["steps"].get(step_key)
            if not step:
                return
            if done is not None:
                step["done"] = max(done, 0)
            if total is not None:
                step["total"] = max(total, 0)
            if message is not None:
                step["message"] = message
            if status is not None:
                step["status"] = status
            step["percent"] = self._percent(step["done"], step["total"])
            self._recalc(task)

    def finish_step(self, task_id: str, step_key: str, done: Optional[int] = None):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            step = task["steps"].get(step_key)
            if not step:
                return
            if done is not None:
                step["done"] = max(done, 0)
            elif step["total"] > 0:
                step["done"] = step["total"]
            step["status"] = "success"
            step["percent"] = self._percent(step["done"], step["total"])
            self._recalc(task)

    def fail_task(self, task_id: str, error: str):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["status"] = "failed"
            task["error"] = error
            task["finished_at"] = _now_str()
            for step in task["steps"].values():
                if step["status"] == "running":
                    step["status"] = "failed"
            self._recalc(task)

    def finish_task(self, task_id: str):
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["status"] = "success"
            task["finished_at"] = _now_str()
            for step in task["steps"].values():
                if step["status"] == "running":
                    step["status"] = "success"
                    if step["total"] > 0:
                        step["done"] = step["total"]
                        step["percent"] = 100.0
            self._recalc(task)

    def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(task_id)
            return copy.deepcopy(task) if task else None

    def list_tasks(self, limit: int = 20, status: Optional[str] = None) -> list[dict[str, Any]]:
        with self._lock:
            values = list(self._tasks.values())
            if status:
                values = [t for t in values if t["status"] == status]
            values = list(reversed(values))
            return copy.deepcopy(values[: max(limit, 1)])

    @staticmethod
    def _percent(done: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round(min(max(done, 0), total) / total * 100, 2)

    def _recalc(self, task: dict[str, Any]):
        total = 0
        done = 0
        for step in task["steps"].values():
            step_total = int(step.get("total", 0) or 0)
            step_done = int(step.get("done", 0) or 0)
            total += step_total
            done += min(max(step_done, 0), step_total) if step_total > 0 else 0
            step["percent"] = self._percent(step_done, step_total)
        task["progress"] = {"done": done, "total": total, "percent": self._percent(done, total)}


task_tracker = TaskTracker()
