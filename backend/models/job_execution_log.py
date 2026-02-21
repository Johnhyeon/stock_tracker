"""Job 실행 이력 추적 모델."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text
from core.database import Base


class JobExecutionLog(Base):
    __tablename__ = "job_execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running, success, failed
    error_message = Column(Text, nullable=True)
    is_catchup = Column(Boolean, nullable=False, default=False)
