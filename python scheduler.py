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

    # Daytime schedule: Every 15 minutes between 8am-6pm
    scheduler.add_job(
        run_refresh,
        'cron',
        minute='0,15,30,45',
        hour='8-17',  # 8am to 5:59pm (hour 17 is 5:00-5:59pm)
        misfire_grace_time=None,  # Don't run missed jobs (skip if overlapping)
        id='daytime_refresh'
    )

    # Nighttime schedule: Every 2 hours between 6pm-8am (top of the hour)
    scheduler.add_job(
        run_refresh,
        'cron',
        minute='0',
        hour='18,20,22,0,2,4,6',  # 6pm, 8pm, 10pm, 12am, 2am, 4am, 6am
        misfire_grace_time=None,  # Don't run missed jobs (skip if overlapping)
        id='nighttime_refresh'
    )

    print(f"\n🚀 Scheduler started")
    print("   Daytime (8am-6pm): Every 15 minutes at :00, :15, :30, :45")
    print("   Nighttime (6pm-8am): Every 2 hours at :00")
    print("   Press Ctrl+C to stop\n")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n⚠️  Scheduler stopped")

if __name__ == "__main__":
    main()