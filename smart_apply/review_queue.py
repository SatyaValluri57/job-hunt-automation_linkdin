"""
Review queue — logs jobs needing human review (low confidence fields / below threshold).
Written to: data/review_queue_YYYYMMDD.txt
"""

import os
import time


DATA_DIR = "data"


def _ensure_dir() -> None:
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)


def add_low_confidence(job_id: int, match_score: int, offer_page: str, job_properties: str, reason: str = "") -> None:
    """Queue a job for manual human review before final submit."""
    _ensure_dir()
    time_str = time.strftime("%Y%m%d")
    file_path = os.path.join(DATA_DIR, f"review_queue_{time_str}.txt")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(
            f"[REVIEW NEEDED] match={match_score}% | {reason} | {job_properties} | {offer_page}\n"
        )


def add_external_apply(job_id: int, offer_page: str, job_properties: str) -> None:
    """Log external (non-Easy-Apply) jobs for manual follow-up."""
    _ensure_dir()
    time_str = time.strftime("%Y%m%d")
    file_path = os.path.join(DATA_DIR, f"external_apply_{time_str}.txt")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[EXTERNAL APPLY] {job_properties} | {offer_page}\n")
