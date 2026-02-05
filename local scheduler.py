from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
from data.refresh_pipeline import refresh_pipeline
from config import settings

def run_refresh():
    """Run one refresh cycle"""
    print(f"\n⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting refresh...")
    
    try:
        result = refresh_pipeline(save_snapshots=True)
        print(f"✅ Refresh complete - {len(result.all_results)} strategies found")
    except Exception as e:
        print(f"❌ Refresh failed: {e}")

def main():
    scheduler = BlockingScheduler()
    
    # Run immediately on start
    run_refresh()

    # Weekday daytime schedule: Every hour between 8am-6pm (Mon-Fri)
    scheduler.add_job(
        run_refresh,
        'cron',
        minute='0',
        hour='8-17',  # 8am to 5:59pm (hour 17 is 5:00-5:59pm)
        day_of_week='mon-fri',
        misfire_grace_time=None,  # Don't run missed jobs (skip if overlapping)
        id='weekday_daytime_refresh'
    )

    # Weekday nighttime schedule: Every 4 hours between 6pm-8am (Mon-Fri)
    scheduler.add_job(
        run_refresh,
        'cron',
        minute='0',
        hour='18,22,2,6',  # 6pm, 10pm, 2am, 6am
        day_of_week='mon-fri',
        misfire_grace_time=None,  # Don't run missed jobs (skip if overlapping)
        id='weekday_nighttime_refresh'
    )

    # Weekend schedule: Every 4 hours all day (Sat-Sun)
    scheduler.add_job(
        run_refresh,
        'cron',
        minute='0',
        hour='*/4',  # Every 4 hours
        day_of_week='sat-sun',
        misfire_grace_time=None,  # Don't run missed jobs (skip if overlapping)
        id='weekend_refresh'
    )

    print(f"\n🚀 Scheduler started")
    print("   Weekdays (Mon-Fri):")
    print("      - Daytime (8am-6pm): Every hour at :00")
    print("      - Nighttime (6pm-8am): Every 4 hours at :00")
    print("   Weekends (Sat-Sun): Every 4 hours at :00")
    print("   Press Ctrl+C to stop\n")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n⚠️  Scheduler stopped")

if __name__ == "__main__":
    main()