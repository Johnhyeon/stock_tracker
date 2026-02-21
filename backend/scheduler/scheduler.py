"""APScheduler 설정 및 관리."""
import logging
from datetime import datetime
from typing import Optional, Callable, Any

from core.timezone import now_kst

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
            now = now_kst()
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
        from scheduler.jobs.youtube_collect import collect_youtube_videos, collect_youtube_hot_videos
        from scheduler.jobs.alert_check import check_alerts
        from scheduler.jobs.expert_sync import sync_expert_mentions
        from scheduler.jobs.news_collect import collect_theme_news
        from scheduler.jobs.chart_pattern_analyze import analyze_chart_patterns
        from scheduler.jobs.theme_setup_calculate import calculate_theme_setups
        from scheduler.jobs.investor_flow_collect import collect_investor_flow
        from scheduler.jobs.ohlcv_collect import collect_ohlcv_daily, collect_ohlcv_for_new_ideas
        from scheduler.jobs.telegram_monitor import monitor_telegram_channels
        from scheduler.jobs.etf_collect import collect_etf_ohlcv_daily
        from scheduler.jobs.etf_rotation_notify import notify_rotation_signals
        from scheduler.jobs.snapshot_collect import collect_daily_snapshots
        from scheduler.jobs.financial_collect import collect_financial_statements_job, sync_dart_corp_codes_job
        from scheduler.jobs.daily_report import send_daily_report
        from scheduler.jobs.narrative_generate import generate_narratives
        from scheduler.jobs.stock_news_collect import collect_hot_stock_news, collect_all_stock_news, classify_stock_news
        from scheduler.jobs.catalyst_track import detect_catalysts, update_catalyst_tracking
        from scheduler.jobs.index_ohlcv_collect import collect_index_ohlcv
        from scheduler.jobs.gap_recovery_scan import scan_gap_recovery

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

        # YouTube 수집 - 아이디어 종목 (6시간마다)
        self.add_interval_job(
            collect_youtube_videos,
            job_id="youtube_collect",
            minutes=self.settings.youtube_check_interval_hours * 60,
        )

        # YouTube 수집 - 키워드 기반 범용 (12시간마다)
        self.add_interval_job(
            collect_youtube_hot_videos,
            job_id="youtube_hot_collect",
            minutes=self.settings.youtube_check_interval_hours * 60 * 2,
        )

        # 전문가 관심종목 동기화 (30분마다)
        if self.settings.expert_feature_enabled:
            self.add_interval_job(
                sync_expert_mentions,
                job_id="expert_sync",
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

        # 일별 포트폴리오 스냅샷 수집 (매일 16:00 장 마감 후)
        self.add_cron_job(
            collect_daily_snapshots,
            job_id="snapshot_collect",
            hour="16",
            minute="0",
            day_of_week="mon-fri",
        )

        # 일일 시장 리포트 발송 (매일 19:00 - 수급 데이터 수집 후)
        self.add_cron_job(
            send_daily_report,
            job_id="daily_report",
            hour="19",
            minute="0",
            day_of_week="mon-fri",
        )

        # 내러티브 브리핑 자동 생성 (매일 17:30 장 마감 후)
        self.add_cron_job(
            generate_narratives,
            job_id="narrative_generate",
            hour="17",
            minute="30",
            day_of_week="mon-fri",
        )

        # 종목별 뉴스 수집 - Tier 1: 핫 종목 (2시간마다)
        self.add_interval_job(
            collect_hot_stock_news,
            job_id="stock_news_collect_hot",
            minutes=120,
        )

        # 종목별 뉴스 수집 - Tier 2: 테마맵 전체 (6시간마다)
        self.add_interval_job(
            collect_all_stock_news,
            job_id="stock_news_collect_all",
            minutes=360,
        )

        # 뉴스 Gemini 분류 (3시간마다)
        self.add_interval_job(
            classify_stock_news,
            job_id="stock_news_classify",
            minutes=180,
        )

        # 카탈리스트 감지 (매일 17:00 장 마감 후, OHLCV 수집 이후)
        self.add_cron_job(
            detect_catalysts,
            job_id="catalyst_detect",
            hour="17",
            minute="0",
            day_of_week="mon-fri",
        )

        # 카탈리스트 추적 업데이트 (매일 17:15)
        self.add_cron_job(
            update_catalyst_tracking,
            job_id="catalyst_update",
            hour="17",
            minute="15",
            day_of_week="mon-fri",
        )

        # 지수 OHLCV 수집 (매일 16:50 장 마감 후)
        self.add_cron_job(
            collect_index_ohlcv,
            job_id="index_ohlcv_collect",
            hour="16",
            minute="50",
            day_of_week="mon-fri",
        )

        # 장중 갭다운 회복 스캔 (장 시간 2분마다)
        self.add_market_hours_job(
            scan_gap_recovery,
            job_id="gap_recovery_scan",
            minutes=2,
        )

        # 재무제표 수집 (매주 토·수 03:00)
        # 토: 정기 수집, 수: 분기 보고서 시즌(3/5/8/11월)에 빠른 갱신
        self.add_cron_job(
            collect_financial_statements_job,
            job_id="financial_collect",
            hour="3",
            minute="0",
            day_of_week="wed,sat",
        )

        # DART 고유번호 동기화 (매주 일요일 02:00)
        self.add_cron_job(
            sync_dart_corp_codes_job,
            job_id="dart_corp_sync",
            hour="2",
            minute="0",
            day_of_week="sun",
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
