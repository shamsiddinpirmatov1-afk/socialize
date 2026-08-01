from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
from autopilot import run_autopilot

scheduler = AsyncIOScheduler()

def setup_scheduler():
    """Настройка планировщика"""
    
    # Запуск каждые 30 минут
    scheduler.add_job(
        run_autopilot,
        trigger=IntervalTrigger(minutes=30),
        id="autopilot_30min"
    )
    
    scheduler.start()
    print("⏰ Планировщик автопилота запущен! (каждые 30 минут)")