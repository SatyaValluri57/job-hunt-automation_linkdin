"""
Detects and fills Easy Apply form questions that aren't already handled by
fillPhoneNumber()/chooseResume() in linkedin.py.

Fill order per field:
  1. Match label against profile_data.yaml (case-insensitive substring).
  2. If no match and config.useGroqAI is on, ask Groq for an answer.
  3. If still unanswered, log it to data/review_queue_<date>.txt instead of
     guessing, and skip it.
"""

import os
import time
from typing import Dict, List, Optional

import yaml
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

import config
import groq_tailorer

PROFILE_DATA_FILE = "profile_data.yaml"
REVIEW_QUEUE_DIR = "data"

KNOWN_FIELD_LABELS = {
    "phone", "phone number", "mobile", "email", "first name", "last name",
    "full name", "name",
}


def load_profile_data() -> Dict:
    if not os.path.exists(PROFILE_DATA_FILE):
        return {}
    with open(PROFILE_DATA_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _label_for_input(driver, element) -> str:
    label = element.get_attribute("aria-label") or ""
    if label.strip():
        return label.strip()

    el_id = element.get_attribute("id") or ""
    if el_id:
        try:
            lbl = driver.find_element(By.XPATH, f"//label[@for='{el_id}']")
            if lbl.text.strip():
                return lbl.text.strip()
        except Exception:
            pass

    placeholder = element.get_attribute("placeholder") or ""
    if placeholder.strip():
        return placeholder.strip()

    try:
        parent = element.find_element(By.XPATH, "./ancestor::div[contains(@class,'fb-dash-form-element')][1]")
        for el in parent.find_elements(By.XPATH, ".//label | .//span[@data-test-form-label]"):
            if el.text.strip():
                return el.text.strip()
    except Exception:
        pass

    return ""


def _is_known(label: str) -> bool:
    return label.lower() in KNOWN_FIELD_LABELS


def detect_unknown_fields(driver) -> List[Dict]:
    unknown = []
    time.sleep(1)

    for selector in ["input[type='text']", "input[type='number']", "textarea"]:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                if not el.is_displayed():
                    continue
                if (el.get_attribute("value") or "").strip():
                    continue
                label = _label_for_input(driver, el)
                if label and not _is_known(label):
                    unknown.append({"type": "text", "label": label, "element": el, "options": []})
        except Exception:
            continue

    try:
        for sel_el in driver.find_elements(By.CSS_SELECTOR, "select"):
            if not sel_el.is_displayed():
                continue
            label = _label_for_input(driver, sel_el)
            try:
                sel = Select(sel_el)
                current = sel.first_selected_option.text.strip()
                options = [o.text.strip() for o in sel.options if o.text.strip()]
            except Exception:
                current, options = "", []
            if current in ("", "Select an option", "Select") and label and not _is_known(label):
                unknown.append({"type": "select", "label": label, "element": sel_el, "options": options})
    except Exception:
        pass

    try:
        radio_groups: Dict[str, Dict] = {}
        for r in driver.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
            if not r.is_displayed():
                continue
            name = r.get_attribute("name") or ""
            label = _label_for_input(driver, r) or name
            group_key = name or label
            group = radio_groups.setdefault(group_key, {"label": label, "elements": [], "options": []})
            group["elements"].append(r)
            val = r.get_attribute("value") or r.get_attribute("aria-label") or ""
            if val:
                group["options"].append(val)
        for group in radio_groups.values():
            if group["label"] and not _is_known(group["label"]):
                if not any(e.is_selected() for e in group["elements"]):
                    unknown.append({
                        "type": "radio",
                        "label": group["label"],
                        "element": group["elements"],
                        "options": group["options"],
                    })
    except Exception:
        pass

    try:
        for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
            if not cb.is_displayed() or cb.is_selected():
                continue
            label = _label_for_input(driver, cb)
            if label and not _is_known(label):
                unknown.append({"type": "checkbox", "label": label, "element": cb, "options": ["yes", "no"]})
    except Exception:
        pass

    return unknown


def _find_in_profile(label: str, profile: Dict) -> Optional[str]:
    label_lower = label.lower()
    for key, val in profile.items():
        if val in (None, "") :
            continue
        if key.lower() in label_lower or label_lower in key.lower():
            return str(val)
    return None


def _fill_text(element, value: str) -> bool:
    try:
        element.clear()
        element.send_keys(value)
        time.sleep(0.3)
        return True
    except Exception:
        return False


def _fill_select(element, value: str) -> bool:
    try:
        sel = Select(element)
        val_lower = value.lower()
        for opt in sel.options:
            if opt.text.strip().lower() == val_lower:
                sel.select_by_visible_text(opt.text.strip())
                return True
        for opt in sel.options:
            if val_lower in opt.text.strip().lower():
                sel.select_by_visible_text(opt.text.strip())
                return True
        return False
    except Exception:
        return False


def _fill_radio(elements: List, value: str) -> bool:
    try:
        val_lower = value.lower()
        for el in elements:
            opt_val = (el.get_attribute("value") or el.get_attribute("aria-label") or "").lower()
            if opt_val and (val_lower in opt_val or opt_val in val_lower):
                el.click()
                time.sleep(0.3)
                return True
    except Exception:
        return False

    default_option = getattr(config, "defaultRadioOption", None)
    if default_option and 1 <= default_option <= len(elements):
        try:
            elements[default_option - 1].click()
            time.sleep(0.3)
            return True
        except Exception:
            return False
    return False


def _fill_checkbox(element, value: str) -> bool:
    try:
        if value.lower() in ("yes", "true", "1"):
            if not element.is_selected():
                element.click()
                time.sleep(0.3)
            return True
        return True
    except Exception:
        return False


def _log_for_review(field: Dict, offer_page: str) -> None:
    if not os.path.exists(REVIEW_QUEUE_DIR):
        os.makedirs(REVIEW_QUEUE_DIR)
    file_path = os.path.join(REVIEW_QUEUE_DIR, f"review_queue_{time.strftime('%Y%m%d')}.txt")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(
            f"[REVIEW NEEDED] label='{field.get('label', '')}' | type={field.get('type', '')} "
            f"| options={field.get('options', [])[:5]} | job={offer_page}\n"
        )


def fill_unknown_fields(driver, unknown_fields: List[Dict], offer_page: str = "", jd_text: str = "") -> int:
    if not unknown_fields:
        return 0

    profile = load_profile_data()
    use_groq = getattr(config, "useGroqAI", False)
    resume_summary = getattr(config, "resumeSummary", "")
    needs_review = 0

    for field in unknown_fields:
        label = field.get("label", "")
        ftype = field.get("type", "text")
        element = field.get("element")
        options = field.get("options", [])

        if not label or element is None:
            continue

        answer = _find_in_profile(label, profile)

        if not answer and use_groq:
            result = groq_tailorer.get_field_answer(label, jd_text, resume_summary, options=options)
            if result.get("confidence") in ("high", "medium"):
                answer = result.get("answer") or None

        filled = False
        if answer:
            if ftype == "text":
                filled = _fill_text(element, answer)
            elif ftype == "select":
                filled = _fill_select(element, answer)
            elif ftype == "radio":
                filled = _fill_radio(element, answer)
            elif ftype == "checkbox":
                filled = _fill_checkbox(element, answer)
        elif ftype == "radio":
            filled = _fill_radio(element, "")
        elif ftype == "checkbox":
            fallback = getattr(config, "answerAllCheckboxes", "")
            if fallback != "":
                filled = _fill_checkbox(element, "yes" if fallback else "no")

        if not filled:
            needs_review += 1
            _log_for_review(field, offer_page)

    return needs_review
