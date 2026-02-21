"""서버 시작 시 데이터 갭 자동 보정 서비스."""
import logging
from datetime import datetime, timedelta

from scheduler.job_tracker import async_get_last_success, catchup_status
from core.timezone import now_kst

logger = logging.getLogger(__name__)

# 안전 상한: 최대 7일치만 catch-up
MAX_CATCHUP_DAYS = 7

# Job별 예상 주기(시간)와 catch-up 전략
JOB_CONFIGS = {
    # job_name: (expected_interval_hours, strategy)
    # strategy: "rerun" = 단순 재실행, "skip" = catch-up 스킵
    "ohlcv_daily_collect": (24, "rerun"),
    "ohlcv_new_ideas_collect": (24, "rerun"),
    "investor_flow_collect": (24, "rerun"),
    "etf_ohlcv_collect": (24, "rerun"),
    "youtube_collect": (6, "rerun"),
    "chart_pattern_analyze": (24, "rerun"),
    "snapshot_collect": (24, "rerun"),
    "theme_news_collect": (6, "rerun"),
    "theme_setup_calculate": (6, "rerun"),
    "expert_sync": (0.5, "rerun"),
    "alert_check": (0.083, "skip"),       # 5분 — 실시간성, catch-up 불필요
    "price_update": (0.083, "skip"),       # 5분 — 장중에만 의미
    "telegram_monitor": (0.083, "skip"),   # last_message_id로 자동 복구
    "disclosure_collect": (0.5, "skip"),   # 이미 7일 윈도우
    "financial_collect": (168, "skip"),    # 주간 — 보통 OK
    "dart_corp_sync": (168, "skip"),       # 주간 — 보통 OK
    "telegram_report_collect": (0.083, "rerun"),
    "telegram_idea_collect": (4, "rerun"),
    "sentiment_analyze": (0.5, "rerun"),
    "etf_rotation_notify": (24, "skip"),   # 알림 — 과거 시점 무의미
}


async def run_catchup():
    """서버 시작 시 모든 job의 데이터 갭을 확인하고 필요한 것만 catch-up 실행."""
    catchup_status["running"] = True
    catchup_status["started_at"] = now_kst().isoformat()
    catchup_status["completed_jobs"] = []
    catchup_status["failed_jobs"] = []

    logger.info("=== Catch-up 프로세스 시작 ===")

    jobs_to_catchup = []

    for job_name, (interval_hours, strategy) in JOB_CONFIGS.items():
        if strategy == "skip":
            logger.debug(f"[catchup] {job_name}: 스킵 (전략=skip)")
            continue

        last_success = await async_get_last_success(job_name)
        if last_success is None:
            # 한 번도 성공한 적 없으면 catch-up 대상
            gap_hours = MAX_CATCHUP_DAYS * 24
            logger.info(f"[catchup] {job_name}: 실행 이력 없음 → catch-up 예정")
        else:
            gap = now_kst().replace(tzinfo=None) - last_success
            gap_hours = gap.total_seconds() / 3600

            # 예상 주기의 1.5배 이상 지났으면 catch-up
            threshold = interval_hours * 1.5
            if gap_hours < threshold:
                logger.debug(
                    f"[catchup] {job_name}: 정상 (gap={gap_hours:.1f}h < threshold={threshold:.1f}h)"
                )
                continue

            # MAX_CATCHUP_DAYS 초과 체크
            if gap_hours > MAX_CATCHUP_DAYS * 24:
                gap_hours = MAX_CATCHUP_DAYS * 24
                logger.warning(
                    f"[catchup] {job_name}: gap이 {MAX_CATCHUP_DAYS}일 초과, 최대 {MAX_CATCHUP_DAYS}일만 보정"
                )

        logger.info(f"[catchup] {job_name}: catch-up 필요 (gap={gap_hours:.1f}h)")
        jobs_to_catchup.append((job_name, gap_hours))

    if not jobs_to_catchup:
        logger.info("=== Catch-up 불필요: 모든 job이 최신 상태 ===")
        catchup_status["running"] = False
        return

    logger.info(f"=== {len(jobs_to_catchup)}개 job catch-up 시작 ===")

    for job_name, gap_hours in jobs_to_catchup:
        catchup_status["current_job"] = job_name
        try:
            await _run_single_catchup(job_name, gap_hours)
            catchup_status["completed_jobs"].append(job_name)
            logger.info(f"[catchup] {job_name}: 완료")
        except Exception as e:
            catchup_status["failed_jobs"].append({"job": job_name, "error": str(e)[:200]})
            logger.error(f"[catchup] {job_name}: 실패 - {e}")

    catchup_status["running"] = False
    catchup_status["current_job"] = None

    completed = len(catchup_status["completed_jobs"])
    failed = len(catchup_status["failed_jobs"])
    logger.info(f"=== Catch-up 완료: 성공 {completed}, 실패 {failed} ===")


async def _run_single_catchup(job_name: str, gap_hours: float):
    """개별 job의 catch-up 실행."""
    # 각 job의 함수를 import하고 _is_catchup=True로 호출
    job_func = _get_job_function(job_name)
    if job_func is None:
        logger.warning(f"[catchup] {job_name}: 함수를 찾을 수 없음")
        return

    logger.info(f"[catchup] {job_name} 실행 중... (gap={gap_hours:.1f}h)")
    await job_func(_is_catchup=True)


def _get_job_function(job_name: str):
    """job_name으로 실제 함수 참조를 반환."""
    try:
        if job_name == "ohlcv_daily_collect":
            from scheduler.jobs.ohlcv_collect import collect_ohlcv_daily
            return collect_ohlcv_daily
        elif job_name == "ohlcv_new_ideas_collect":
            from scheduler.jobs.ohlcv_collect import collect_ohlcv_for_new_ideas
            return collect_ohlcv_for_new_ideas
        elif job_name == "investor_flow_collect":
            from scheduler.jobs.investor_flow_collect import collect_investor_flow
            return collect_investor_flow
        elif job_name == "etf_ohlcv_collect":
            from scheduler.jobs.etf_collect import collect_etf_ohlcv_daily
            return collect_etf_ohlcv_daily
        elif job_name == "youtube_collect":
            from scheduler.jobs.youtube_collect import collect_youtube_videos
            return collect_youtube_videos
        elif job_name == "chart_pattern_analyze":
            from scheduler.jobs.chart_pattern_analyze import analyze_chart_patterns
            return analyze_chart_patterns
        elif job_name == "snapshot_collect":
            from scheduler.jobs.snapshot_collect import collect_daily_snapshots
            return collect_daily_snapshots
        elif job_name == "theme_news_collect":
            from scheduler.jobs.news_collect import collect_theme_news
            return collect_theme_news
        elif job_name == "theme_setup_calculate":
            from scheduler.jobs.theme_setup_calculate import calculate_theme_setups
            return calculate_theme_setups
        elif job_name == "expert_sync":
            from scheduler.jobs.expert_sync import sync_expert_mentions
            return sync_expert_mentions
        elif job_name == "telegram_report_collect":
            from scheduler.jobs.sentiment_analyze import collect_telegram_reports
            return collect_telegram_reports
        elif job_name == "telegram_idea_collect":
            from scheduler.jobs.telegram_idea_collect import collect_telegram_ideas
            return collect_telegram_ideas
        elif job_name == "sentiment_analyze":
            from scheduler.jobs.sentiment_analyze import analyze_telegram_sentiments
            return analyze_telegram_sentiments
        else:
            return None
    except ImportError as e:
        logger.error(f"[catchup] {job_name} import 실패: {e}")
        return None
