"""
Phase 2 — Fills detected unknown fields using:
  1. profile_data.yaml (standard answers)
  2. Groq AI if field not in profile_data
  3. If AI confidence low → review queue
"""

import os
import time
import yaml
from typing import Dict, Optional, List

import config
from smart_apply.review_queue import add_low_confidence
from smart_apply.groq_tailorer import get_field_answer

try:
    from selenium.webdriver.support.ui import Select as SeleniumSelect
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


PROFILE_DATA_FILE = "profile_data.yaml"


def load_profile_data() -> Dict:
    """Load profile_data.yaml — standard answers for common fields."""
    if os.path.exists(PROFILE_DATA_FILE):
        with open(PROFILE_DATA_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data
    return {}


def _find_in_profile(label: str, profile: Dict) -> Optional[str]:
    """Case-insensitive label lookup in profile_data."""
    label_lower = label.lower()
    for key, val in profile.items():
        if key.lower() in label_lower or label_lower in key.lower():
            return str(val)
    return None


def _fill_text(element, value: str) -> None:
    try:
        element.clear()
        element.send_keys(value)
        time.sleep(0.3)
    except Exception:
        pass


def _fill_select(element, value: str) -> None:
    try:
        sel = SeleniumSelect(element)
        # Try exact match first, then partial
        options = [o.text.strip().lower() for o in sel.options]
        val_lower = value.lower()
        for opt in sel.options:
            if opt.text.strip().lower() == val_lower:
                sel.select_by_visible_text(opt.text.strip())
                return
        for opt in sel.options:
            if val_lower in opt.text.strip().lower():
                sel.select_by_visible_text(opt.text.strip())
                return
    except Exception:
        pass


def _fill_radio(elements: List, value: str) -> None:
    try:
        val_lower = value.lower()
        for el in elements:
            opt_val = (el.get_attribute("value") or el.get_attribute("aria-label") or "").lower()
            if val_lower in opt_val or opt_val in val_lower:
                el.click()
                time.sleep(0.3)
                return
        # fallback: click first option
        if elements:
            elements[0].click()
    except Exception:
        pass


def fill_unknown_fields(
    unknown_fields: List[Dict],
    jd_text: str,
    job_properties: str,
    offer_page: str,
    job_id: int = 0,
) -> int:
    """
    Try to fill each unknown field.
    Returns count of fields queued for review.
    """
    if not unknown_fields:
        return 0

    profile = load_profile_data()
    jd_snippet = jd_text[:800] if jd_text else ""
    resume_summary = getattr(config, "resumeSummary", "")
    use_groq = getattr(config, "useGroqAI", False)

    review_count = 0

    for field in unknown_fields:
        label = field.get("label", "")
        ftype = field.get("type", "text")
        element = field.get("element")
        options = field.get("options", [])

        if not label or element is None:
            continue

        # 1. Try profile_data.yaml first
        answer = _find_in_profile(label, profile)
        confidence = "high" if answer else "low"

        # 2. Try Groq AI if no profile match
        if not answer and use_groq:
            question = label
            if options:
                question += f" (options: {', '.join(str(o) for o in options[:8])})"
            result = get_field_answer(question, jd_snippet, resume_summary)
            answer = result.get("answer", "")
            confidence = result.get("confidence", "low")

        # 3. Route based on confidence
        if answer and confidence in ("high", "medium"):
            # Auto-fill
            try:
                if ftype == "text":
                    _fill_text(element, answer)
                elif ftype == "select":
                    _fill_select(element, answer)
                elif ftype == "radio":
                    _fill_radio(element if isinstance(element, list) else [element], answer)
                elif ftype == "checkbox":
                    if answer.lower() in ("yes", "true", "1"):
                        if not element.is_selected():
                            element.click()
            except Exception:
                pass
        else:
            # Low confidence or no answer → review queue
            review_count += 1
            add_low_confidence(
                job_id=job_id,
                match_score=0,
                offer_page=offer_page,
                job_properties=job_properties,
                reason=f"Unknown field: '{label}' | suggested: '{answer}' | confidence: {confidence} | options: {options[:5]}",
            )

    return review_count
