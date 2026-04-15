from __future__ import annotations

from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def build_scheduler(job_func, timezone: str = "UTC") -> BackgroundScheduler:
    zone = ZoneInfo(timezone)
    scheduler = BackgroundScheduler(timezone=zone)
    scheduler.add_job(
        job_func,
        trigger=CronTrigger(minute=5, timezone=zone),
        id="hourly_etl",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=900,
    )
    return scheduler
