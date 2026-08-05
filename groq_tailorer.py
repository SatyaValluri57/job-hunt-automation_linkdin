"""
Optional AI fallback for Easy Apply questions that profile_data.yaml
does not answer.

Requires: pip install groq
Set GROQ_API_KEY in environment or .env file.
Degrades gracefully (returns low-confidence empty answer) if the key or
package is unavailable, so the rest of the bot works without it.
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
