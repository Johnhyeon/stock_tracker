"""APScheduler 설정 및 관리."""
import logging
from datetime import datetime
from typing import Optional, Callable, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from core.config import get_settings

logger = logging.getLogger(__name__)


class SchedulerManager:
    """스케줄러 관리자.

    APScheduler의 AsyncIOScheduler를 래핑하여
    작업 등록, 상태 조회, 시작/종료를 관리합니다.
    """

    def __init__(self):
        self.settings = get_settings()
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._initialized = False

    @property
    def scheduler(self) -> AsyncIOScheduler:
        if self._scheduler is None:
            self._scheduler = AsyncIOScheduler(
                timezone="Asia/Seoul",
                job_defaults={
                    "coalesce": True,  # 놓친 작업 한번만 실행
                    "max_instances": 1,  # 동시 실행 방지
                    "misfire_grace_time": 60,  # 60초 이내 놓친 작업 실행
                }
            )
            self._scheduler.add_listener(
                self._job_listener,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
            )
        return self._scheduler

    def _job_listener(self, event: JobExecutionEvent):
        """작업 실행 이벤트 리스너."""
        if event.exception:
            logger.error(
                f"Job {event.job_id} failed: {event.exception}",
                exc_info=event.exception
            )
        else:
            logger.debug(f"Job {event.job_id} executed successfully")

    def add_interval_job(
        self,
        func: Callable,
        job_id: str,
        minutes: int = 5,
        **kwargs: Any,
    ) -> None:
        """일정 간격으로 실행되는 작업 등록."""
        self.scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=minutes),
            id=job_id,
            replace_existing=True,
            **kwargs,
        )
        logger.info(f"Added interval job: {job_id} (every {minutes} minutes)")

    def add_cron_job(
        self,
        func: Callable,
        job_id: str,
        hour: str = "*",
        minute: str = "0",
        day_of_week: str = "mon-fri",
        **kwargs: Any,
    ) -> None:
        """크론 스케줄로 실행되는 작업 등록."""
        self.scheduler.add_job(
            func,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=day_of_week,
                timezone="Asia/Seoul",
            ),
            id=job_id,
            replace_existing=True,
            **kwargs,
        )
        logger.info(f"Added cron job: {job_id}")

    def add_market_hours_job(
        self,
        func: Callable,
        job_id: str,
        minutes: int = 5,
        **kwargs: Any,
    ) -> None:
        """장 시간(09:00-15:30)에만 실행되는 작업 등록.

        월-금 09:00-15:30 사이에만 지정된 간격으로 실행됩니다.
        """
        # 장 시간 체크를 포함하는 래퍼 함수
        async def market_hours_wrapper():
            now = datetime.now()
            # 주말 체크
            if now.weekday() >= 5:  # 토(5), 일(6)
                logger.debug(f"Skipping {job_id}: weekend")
                return
            # 장 시간 체크 (09:00 - 15:30)
            current_time = now.hour * 100 + now.minute
            if current_time < 900 or current_time > 1530:
                logger.debug(f"Skipping {job_id}: outside market hours")
                return
            await func()

        self.scheduler.add_job(
            market_hours_wrapper,
            trigger=IntervalTrigger(minutes=minutes),
            id=job_id,
            replace_existing=True,
            **kwargs,
        )
        logger.info(
            f"Added market hours job: {job_id} (every {minutes} minutes, 09:00-15:30)"
        )

    def remove_job(self, job_id: str) -> bool:
        """작업 제거."""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
            return True
        except Exception:
            return False

    def get_jobs(self) -> list[dict]:
        """등록된 작업 목록."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs

    def start(self) -> None:
        """스케줄러 시작."""
        if not self.settings.scheduler_enabled:
            logger.info("Scheduler is disabled by configuration")
            return

        if not self._initialized:
            self._setup_jobs()
            self._initialized = True

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self) -> None:
        """스케줄러 종료."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler shutdown")

    def _setup_jobs(self) -> None:
        """기본 작업 등록."""
        from scheduler.jobs.price_update import update_active_position_prices
        from scheduler.jobs.disclosure_collect import collect_disclosures_for_active_positions
        from scheduler.jobs.youtube_collect import collect_youtube_videos
        from scheduler.jobs.alert_check import check_alerts
        from scheduler.jobs.trader_sync import sync_trader_mentions
        from scheduler.jobs.news_collect import collect_theme_news
        from scheduler.jobs.chart_pattern_analyze import analyze_chart_patterns
        from scheduler.jobs.theme_setup_calculate import calculate_theme_setups
        from scheduler.jobs.investor_flow_collect import collect_investor_flow
        from scheduler.jobs.ohlcv_collect import collect_ohlcv_daily, collect_ohlcv_for_new_ideas
        from scheduler.jobs.telegram_monitor import monitor_telegram_channels
        from scheduler.jobs.etf_collect import collect_etf_ohlcv_daily
        from scheduler.jobs.etf_rotation_notify import notify_rotation_signals

        # 활성 포지션 가격 업데이트 (장 시간에만)
        self.add_market_hours_job(
            update_active_position_prices,
            job_id="price_update",
            minutes=self.settings.price_update_interval_minutes,
        )

        # 공시 수집 (30분마다)
        self.add_interval_job(
            collect_disclosures_for_active_positions,
            job_id="disclosure_collect",
            minutes=self.settings.disclosure_check_interval_minutes,
        )

        # YouTube 수집 (6시간마다)
        self.add_interval_job(
            collect_youtube_videos,
            job_id="youtube_collect",
            minutes=self.settings.youtube_check_interval_hours * 60,
        )

        # 트레이더 관심종목 동기화 (30분마다)
        self.add_interval_job(
            sync_trader_mentions,
            job_id="trader_sync",
            minutes=30,
        )

        # 알림 체크 (5분마다)
        self.add_interval_job(
            check_alerts,
            job_id="alert_check",
            minutes=self.settings.alert_check_interval_minutes,
        )

        # 테마 뉴스 수집 (6시간마다)
        self.add_interval_job(
            collect_theme_news,
            job_id="theme_news_collect",
            minutes=self.settings.theme_news_check_interval_hours * 60,
        )

        # 차트 패턴 분석 (매일 16:30 장 마감 후)
        self.add_cron_job(
            analyze_chart_patterns,
            job_id="chart_pattern_analyze",
            hour="16",
            minute="30",
            day_of_week="mon-fri",
        )

        # 테마 셋업 점수 계산 (6시간마다)
        self.add_interval_job(
            calculate_theme_setups,
            job_id="theme_setup_calculate",
            minutes=self.settings.theme_setup_check_interval_hours * 60,
        )

        # 투자자 수급 데이터 수집 (매일 18:30 - KRX 발표 이후)
        self.add_cron_job(
            collect_investor_flow,
            job_id="investor_flow_collect",
            hour="18",
            minute="30",
            day_of_week="mon-fri",
        )

        # OHLCV 일별 수집 (매일 16:40 장 마감 후)
        self.add_cron_job(
            collect_ohlcv_daily,
            job_id="ohlcv_daily_collect",
            hour="16",
            minute="40",
            day_of_week="mon-fri",
        )

        # 신규 아이디어 종목 OHLCV 수집 (매일 07:00)
        self.add_cron_job(
            collect_ohlcv_for_new_ideas,
            job_id="ohlcv_new_ideas_collect",
            hour="7",
            minute="0",
            day_of_week="mon-fri",
        )

        # 텔레그램 채널 모니터링 (기본 5분마다)
        self.add_interval_job(
            monitor_telegram_channels,
            job_id="telegram_monitor",
            minutes=self.settings.telegram_monitor_interval_minutes,
        )

        # ETF OHLCV 일별 수집 (매일 16:45 장 마감 후)
        self.add_cron_job(
            collect_etf_ohlcv_daily,
            job_id="etf_ohlcv_collect",
            hour="16",
            minute="45",
            day_of_week="mon-fri",
        )

        # 순환매 시그널 알림 (매일 17:00 ETF 수집 후)
        self.add_cron_job(
            notify_rotation_signals,
            job_id="etf_rotation_notify",
            hour="17",
            minute="0",
            day_of_week="mon-fri",
        )

    @property
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running


# 싱글톤 인스턴스
_scheduler_manager: Optional[SchedulerManager] = None


def get_scheduler_manager() -> SchedulerManager:
    """스케줄러 매니저 싱글톤 반환."""
    global _scheduler_manager
    if _scheduler_manager is None:
        _scheduler_manager = SchedulerManager()
    return _scheduler_manager
