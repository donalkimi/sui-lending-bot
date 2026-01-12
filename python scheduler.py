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
    
    # Then run every CHECK_INTERVAL_MINUTES
    scheduler.add_job(
        run_refresh,
        'interval',
        minutes=settings.CHECK_INTERVAL_MINUTES,
        id='refresh_job'
    )
    
    print(f"\n🚀 Scheduler started - running every {settings.CHECK_INTERVAL_MINUTES} minutes")
    print("   Press Ctrl+C to stop\n")
    
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("\n⚠️  Scheduler stopped")

if __name__ == "__main__":
    main()