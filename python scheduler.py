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

    # Then run at exact 15-minute intervals (:00, :15, :30, :45)
    scheduler.add_job(
        run_refresh,
        'cron',
        minute='0,15,30,45',  # Run at these minutes every hour
        misfire_grace_time=None,  # Don't run missed jobs (skip if overlapping)
        id='refresh_job'
    )

    print(f"\n🚀 Scheduler started - running at :00, :15, :30, :45 of every hour")
    print("   Press Ctrl+C to stop\n")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n⚠️  Scheduler stopped")

if __name__ == "__main__":
    main()