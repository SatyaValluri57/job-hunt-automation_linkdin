"""
JD vs profile skill matcher.
Returns a match score (0-100). If score >= config.matchThreshold, bot proceeds.
"""

import re
from typing import List


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s+#]", " ", text)
    return [t.strip() for t in text.split() if len(t.strip()) > 1]


def score_match(jd_text: str, profile_skills: List[str]) -> int:
    """
    Simple keyword overlap score between JD text and candidate skills.
    Returns integer 0-100.
    """
    if not jd_text or not profile_skills:
        return 0

    jd_tokens = set(_tokenize(jd_text))
    matched = 0
    total = len(profile_skills)

    if total == 0:
        return 0

    for skill in profile_skills:
        skill_tokens = set(_tokenize(skill))
        if skill_tokens & jd_tokens:
            matched += 1

    score = int((matched / total) * 100)
    return min(score, 100)


def is_above_threshold(score: int, threshold: int = 60) -> bool:
    return score >= threshold
