"""수집 작업 상태 관리."""
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from core.timezone import now_kst


@dataclass
class CollectionTask:
    """수집 작업 상태."""
    is_running: bool = False
    started_at: Optional[datetime] = None
    task_type: str = ""  # "investor_flow", "patterns", "calculate"
    progress: str = ""


class CollectionStatusManager:
    """수집 상태 관리자 (싱글톤)."""

    def __init__(self):
        self._tasks: dict[str, CollectionTask] = {
            "investor_flow": CollectionTask(),
            "patterns": CollectionTask(),
            "calculate": CollectionTask(),
        }

    def start(self, task_type: str, progress: str = ""):
        """작업 시작."""
        if task_type in self._tasks:
            self._tasks[task_type] = CollectionTask(
                is_running=True,
                started_at=now_kst(),
                task_type=task_type,
                progress=progress,
            )

    def finish(self, task_type: str):
        """작업 완료."""
        if task_type in self._tasks:
            self._tasks[task_type] = CollectionTask()

    def update_progress(self, task_type: str, progress: str):
        """진행 상황 업데이트."""
        if task_type in self._tasks and self._tasks[task_type].is_running:
            self._tasks[task_type].progress = progress

    def get_status(self, task_type: str) -> dict:
        """작업 상태 조회."""
        task = self._tasks.get(task_type, CollectionTask())
        return {
            "is_running": task.is_running,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "task_type": task.task_type,
            "progress": task.progress,
        }

    def get_all_status(self) -> dict:
        """모든 작업 상태 조회."""
        return {
            task_type: self.get_status(task_type)
            for task_type in self._tasks
        }


# 싱글톤 인스턴스
_status_manager: Optional[CollectionStatusManager] = None


def get_collection_status() -> CollectionStatusManager:
    """수집 상태 관리자 싱글톤 반환."""
    global _status_manager
    if _status_manager is None:
        _status_manager = CollectionStatusManager()
    return _status_manager
