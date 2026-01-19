from datetime import datetime
from data.refresh_pipeline import refresh_pipeline
from data.rate_tracker import RateTracker


def main():
    print("\n=== Sui Lending Bot: Refresh Started ===\n")

    # Get current time
    current_time = datetime.now()

    # Run full refresh pipeline
    result = refresh_pipeline(
        timestamp=current_time,
        save_snapshots=True,
    )

    # -------------------------
    # Token registry summary
    # -------------------------
    token_summary = result.token_summary

    print("=== TOKEN REGISTRY UPDATE ===")
    print(f"Tokens seen this run      : {token_summary['seen']}")
    print(f"New tokens inserted      : {token_summary['inserted']}")
    print(f"Existing tokens updated  : {token_summary['updated']}")
    print(f"Total tokens in DB       : {token_summary['total']}")
    print("============================\n")

    # -------------------------
    # DB table counts (sanity check)
    # -------------------------
    tracker = RateTracker()
    table_counts = tracker.get_table_counts()

    print("=== DATABASE STATE ===")
    for table, count in table_counts.items():
        print(f"{table:20s}: {count}")
    print("======================\n")

    
    print("=== Refresh Complete ===\n")


if __name__ == "__main__":
    main()
