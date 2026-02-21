"""Job 실행 추적 데코레이터 및 헬퍼."""
import logging
import functools
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from core.database import async_session_maker, SessionLocal
from core.timezone import now_kst
from models.job_execution_log import JobExecutionLog

logger = logging.getLogger(__name__)

# catch-up 진행 상태 (서버 내 글로벌)
catchup_status: dict = {
    "running": False,
    "started_at": None,
    "completed_jobs": [],
    "failed_jobs": [],
    "current_job": None,
}


def track_job_execution(job_name: str):
    """Job 실행을 DB에 자동 기록하는 데코레이터.

    Usage:
        @track_job_execution("ohlcv_daily_collect")
        async def collect_ohlcv_daily():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            started_at = now_kst().replace(tzinfo=None)

            # 실행 시작 기록
            async with async_session_maker() as db:
                log = JobExecutionLog(
                    job_name=job_name,
                    started_at=started_at,
                    status="running",
                    is_catchup=kwargs.pop("_is_catchup", False),
                )
                db.add(log)
                await db.commit()
                await db.refresh(log)
                log_id = log.id

            try:
                result = await func(*args, **kwargs)

                # 성공 기록
                finished_at = now_kst().replace(tzinfo=None)
                async with async_session_maker() as db:
                    log = await db.get(JobExecutionLog, log_id)
                    if log:
                        log.status = "success"
                        log.finished_at = finished_at
                        log.duration_seconds = (finished_at - started_at).total_seconds()
                        await db.commit()

                return result

            except Exception as e:
                # 실패 기록
                finished_at = now_kst().replace(tzinfo=None)
                error_msg = str(e)[:2000]
                async with async_session_maker() as db:
                    log = await db.get(JobExecutionLog, log_id)
                    if log:
                        log.status = "failed"
                        log.finished_at = finished_at
                        log.duration_seconds = (finished_at - started_at).total_seconds()
                        log.error_message = error_msg
                        await db.commit()

                raise

        return wrapper
    return decorator


def get_last_success(job_name: str) -> Optional[datetime]:
    """특정 job의 마지막 성공 시간 조회 (동기)."""
    db: Session = SessionLocal()
    try:
        result = db.query(JobExecutionLog).filter(
            JobExecutionLog.job_name == job_name,
            JobExecutionLog.status == "success",
        ).order_by(desc(JobExecutionLog.finished_at)).first()
        return result.finished_at if result else None
    finally:
        db.close()


async def async_get_last_success(job_name: str) -> Optional[datetime]:
    """특정 job의 마지막 성공 시간 조회 (비동기)."""
    async with async_session_maker() as db:
        stmt = (
            select(JobExecutionLog)
            .where(
                JobExecutionLog.job_name == job_name,
                JobExecutionLog.status == "success",
            )
            .order_by(desc(JobExecutionLog.finished_at))
            .limit(1)
        )
        result = await db.execute(stmt)
        log = result.scalar_one_or_none()
        return log.finished_at if log else None


async def get_all_job_stats() -> list[dict]:
    """모든 job의 최근 실행 통계 조회."""
    async with async_session_maker() as db:
        # 각 job_name별 마지막 실행 기록
        from sqlalchemy import func, distinct

        # 모든 고유 job_name 조회
        stmt = select(distinct(JobExecutionLog.job_name))
        result = await db.execute(stmt)
        job_names = [row[0] for row in result.fetchall()]

        stats = []
        for name in job_names:
            # 마지막 실행
            stmt = (
                select(JobExecutionLog)
                .where(JobExecutionLog.job_name == name)
                .order_by(desc(JobExecutionLog.started_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            last_run = result.scalar_one_or_none()

            # 마지막 성공
            stmt = (
                select(JobExecutionLog)
                .where(
                    JobExecutionLog.job_name == name,
                    JobExecutionLog.status == "success",
                )
                .order_by(desc(JobExecutionLog.finished_at))
                .limit(1)
            )
            result = await db.execute(stmt)
            last_success = result.scalar_one_or_none()

            # 최근 24시간 실행 횟수
            since = now_kst().replace(tzinfo=None) - timedelta(hours=24)
            stmt = (
                select(func.count())
                .select_from(JobExecutionLog)
                .where(
                    JobExecutionLog.job_name == name,
                    JobExecutionLog.started_at >= since,
                )
            )
            result = await db.execute(stmt)
            run_count_24h = result.scalar() or 0

            # 최근 24시간 실패 횟수
            stmt = (
                select(func.count())
                .select_from(JobExecutionLog)
                .where(
                    JobExecutionLog.job_name == name,
                    JobExecutionLog.status == "failed",
                    JobExecutionLog.started_at >= since,
                )
            )
            result = await db.execute(stmt)
            fail_count_24h = result.scalar() or 0

            stats.append({
                "job_name": name,
                "last_run": {
                    "started_at": last_run.started_at.isoformat() if last_run else None,
                    "status": last_run.status if last_run else None,
                    "duration_seconds": last_run.duration_seconds if last_run else None,
                    "error_message": last_run.error_message if last_run else None,
                    "is_catchup": last_run.is_catchup if last_run else False,
                },
                "last_success_at": last_success.finished_at.isoformat() if last_success else None,
                "runs_24h": run_count_24h,
                "failures_24h": fail_count_24h,
            })

        return stats
