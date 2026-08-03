"""
Optional AI tailoring step using Groq free API.
- Extracts required skills from JD
- Computes a richer match score using LLM
- Returns field answers for low-confidence questions

Requires: pip install groq
Set GROQ_API_KEY in environment or .env file.
Skips gracefully if GROQ_API_KEY is not set (falls back to keyword matcher).
"""

import os
from typing import Dict, Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


def _get_client() -> Optional[object]:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or not GROQ_AVAILABLE:
        return None
    return Groq(api_key=api_key)


def score_match_with_ai(jd_text: str, resume_summary: str) -> int:
    """
    Uses Groq LLM to score how well candidate matches the JD.
    Returns integer 0-100. Falls back to 0 if unavailable.
    """
    client = _get_client()
    if not client:
        return -1  # signal: use keyword fallback

    prompt = (
        "Rate how well this candidate matches this job description. "
        "Reply with ONLY a single integer from 0 to 100. No explanation.\n\n"
        f"JOB DESCRIPTION:\n{jd_text[:2000]}\n\n"
        f"CANDIDATE SUMMARY:\n{resume_summary[:1000]}"
    )
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        score_text = response.choices[0].message.content.strip()
        score = int("".join(filter(str.isdigit, score_text)))
        return min(max(score, 0), 100)
    except Exception:
        return -1


def get_field_answer(question: str, jd_text: str, resume_summary: str) -> Dict[str, str]:
    """
    Given an unanswered form question, asks Groq to suggest an honest answer.
    Returns: {"answer": "...", "confidence": "high|medium|low"}
    Falls back to {"answer": "", "confidence": "low"} if unavailable.
    """
    client = _get_client()
    if not client:
        return {"answer": "", "confidence": "low"}

    prompt = (
        "You are filling in a job application form honestly based on the candidate's resume.\n"
        "Answer the following question in 1-2 sentences. Be factual. Do not invent experience.\n"
        "Also rate your confidence as: high, medium, or low.\n"
        "Reply in this exact format: ANSWER: <your answer> | CONFIDENCE: <high/medium/low>\n\n"
        f"Question: {question}\n\n"
        f"Candidate resume summary: {resume_summary[:800]}\n\n"
        f"Job description excerpt: {jd_text[:800]}"
    )
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
        answer = ""
        confidence = "low"
        if "ANSWER:" in content and "CONFIDENCE:" in content:
            parts = content.split("|")
            answer = parts[0].replace("ANSWER:", "").strip()
            confidence = parts[1].replace("CONFIDENCE:", "").strip().lower()
        return {"answer": answer, "confidence": confidence}
    except Exception:
        return {"answer": "", "confidence": "low"}
