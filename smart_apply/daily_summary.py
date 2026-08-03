"""
Daily summary writer — appends a readable summary report to data/daily_summary_YYYYMMDD.txt
"""

import os
import time
from typing import Dict


DATA_DIR = "data"


def write_daily_summary(stats: Dict) -> None:
    """
    Writes a human-readable daily summary.
    stats keys: applied, dry_run, external, below_threshold, low_confidence, duration_min
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    time_str = time.strftime("%Y%m%d")
    file_path = os.path.join(DATA_DIR, f"daily_summary_{time_str}.txt")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "",
        "=" * 60,
        f"  DAILY JOB APPLY SUMMARY — {timestamp}",
        "=" * 60,
        f"  ✅ Applied (Easy Apply):    {stats.get('applied', 0)}",
        f"  🧪 Dry-run (simulated):     {stats.get('dry_run', 0)}",
        f"  🔗 External apply (logged): {stats.get('external', 0)}",
        f"  ⛔ Below 60% match:         {stats.get('below_threshold', 0)}",
        f"  ⏳ Needs your review:       {stats.get('low_confidence', 0)}",
        f"  ⏱  Duration:                {stats.get('duration_min', 0)} min",
        "=" * 60,
        f"  Review file: data/review_queue_{time_str}.txt",
        f"  External file: data/external_apply_{time_str}.txt",
        "=" * 60,
        "",
    ]

    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("\n".join(lines))
