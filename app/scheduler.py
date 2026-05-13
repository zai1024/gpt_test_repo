from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from app.config import settings
from app.services import sync_from_vcenter

_scheduler: BackgroundScheduler | None = None


def start_scheduler(app: Flask) -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    def job() -> None:
        with app.app_context():
            sync_from_vcenter()

    _scheduler.add_job(
        job,
        trigger="cron",
        hour=settings.sync_cron_hour,
        minute=settings.sync_cron_minute,
        id="daily_vcenter_sync",
        replace_existing=True,
    )
    _scheduler.start()
