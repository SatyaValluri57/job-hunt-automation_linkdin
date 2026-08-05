"""
Optional AI fallback for Easy Apply questions that profile_data.yaml
does not answer.

Requires: pip install groq
Set GROQ_API_KEY in environment or .env file.
Degrades gracefully (returns low-confidence empty answer) if the key or
package is unavailable, so the rest of the bot works without it.
"""

import os
from typing import Dict, List, Optional

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


def get_field_answer(question: str, jd_text: str, resume_summary: str, options: Optional[List[str]] = None) -> Dict[str, str]:
    """
    Given an unanswered form field, asks Groq for the exact value to enter.
    If options is given, the answer must be copied verbatim from that list.
    Returns: {"answer": "...", "confidence": "high|medium|low"}
    Falls back to {"answer": "", "confidence": "low"} if unavailable.
    """
    client = _get_client()
    if not client:
        return {"answer": "", "confidence": "low"}

    if options:
        instructions = (
            "You are filling a single field in a job application form.\n"
            "The field has a fixed set of options. Reply with ONLY the exact text of ONE "
            "option, copied verbatim from the list below — no rephrasing, no extra words.\n"
            f"Options: {' | '.join(options[:12])}\n"
        )
    else:
        instructions = (
            "You are filling a single field in a job application form.\n"
            "Reply with ONLY the exact value to enter into the field — a number, a word, "
            "or a short phrase. No sentences, no explanation, no restating the question.\n"
        )

    prompt = (
        instructions
        + "Be factual based on the candidate summary below. Do not invent experience.\n"
        "Also rate your confidence as: high, medium, or low.\n"
        "Reply in this exact format: ANSWER: <value> | CONFIDENCE: <high/medium/low>\n\n"
        f"Field label: {question}\n\n"
        f"Candidate summary: {resume_summary[:800]}\n\n"
        f"Job description excerpt: {jd_text[:800]}"
    )
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=40,
            temperature=0,
        )
        content = response.choices[0].message.content.strip()
        answer = ""
        confidence = "low"
        if "ANSWER:" in content and "CONFIDENCE:" in content:
            parts = content.split("|")
            answer = parts[0].replace("ANSWER:", "").strip()
            confidence = parts[1].replace("CONFIDENCE:", "").strip().lower()

        if options and answer:
            answer_lower = answer.lower()
            matched = next((o for o in options if o.lower() == answer_lower), None)
            if not matched:
                matched = next((o for o in options if answer_lower in o.lower() or o.lower() in answer_lower), None)
            answer = matched or ""
            if not answer:
                confidence = "low"

        return {"answer": answer, "confidence": confidence}
    except Exception:
        return {"answer": "", "confidence": "low"}
