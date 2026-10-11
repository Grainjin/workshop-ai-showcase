from sqlalchemy import CheckConstraint, Column, Date, DateTime, Integer, String

from backend.database import Base


class DemoAIUsage(Base):
    __tablename__ = "demo_ai_usage"
    __table_args__ = (
        CheckConstraint("daily_count >= 0", name="ck_demo_ai_daily_nonnegative"),
        CheckConstraint("minute_count >= 0", name="ck_demo_ai_minute_nonnegative"),
    )

    usage_date = Column(Date, primary_key=True)
    subject_hash = Column(String(64), primary_key=True)
    daily_count = Column(Integer, nullable=False)
    minute_start = Column(DateTime(timezone=True), nullable=False)
    minute_count = Column(Integer, nullable=False)
