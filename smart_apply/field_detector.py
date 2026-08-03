"""
Phase 2 — Unknown form field detector.
Scans the currently visible LinkedIn Easy Apply form page and returns
a list of questions/fields the bot does not already know how to answer.
"""

import time
from typing import List, Dict
from selenium.webdriver.common.by import By


KNOWN_FIELD_LABELS = {
    "phone", "phone number", "mobile", "email", "first name", "last name",
    "full name", "name", "location", "city", "country", "address",
    "linkedin", "linkedin profile", "website", "portfolio", "github",
}


def _label_for_input(driver, element) -> str:
    """Try to find a human-readable label for a form element."""
    # aria-label
    label = element.get_attribute("aria-label") or ""
    if label.strip():
        return label.strip()
    # id-based label
    el_id = element.get_attribute("id") or ""
    if el_id:
        try:
            lbl = driver.find_element(By.XPATH, f"//label[@for='{el_id}']")
            return lbl.text.strip()
        except Exception:
            pass
    # placeholder
    placeholder = element.get_attribute("placeholder") or ""
    if placeholder.strip():
        return placeholder.strip()
    # parent label text
    try:
        parent = element.find_element(By.XPATH, "./ancestor::div[contains(@class,'fb-dash-form-element')][1]")
        spans = parent.find_elements(By.XPATH, ".//label | .//span[@data-test-form-label]")
        for s in spans:
            t = s.text.strip()
            if t:
                return t
    except Exception:
        pass
    return ""


def _is_known(label: str) -> bool:
    return label.lower() in KNOWN_FIELD_LABELS


def detect_unknown_fields(driver) -> List[Dict]:
    """
    Scans current Easy Apply form page for unknown fields.
    Returns list of dicts:
      {type, label, element, options (for select/radio)}
    """
    unknown = []
    time.sleep(1)

    # --- Text inputs / textareas ---
    for tag in ["input[type='text']", "input[type='number']", "textarea"]:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, tag)
            for el in elements:
                if not el.is_displayed():
                    continue
                current_val = el.get_attribute("value") or ""
                if current_val.strip():
                    continue  # already filled
                label = _label_for_input(driver, el)
                if label and not _is_known(label):
                    unknown.append({
                        "type": "text",
                        "label": label,
                        "element": el,
                        "options": [],
                    })
        except Exception:
            continue

    # --- Select dropdowns ---
    try:
        selects = driver.find_elements(By.CSS_SELECTOR, "select")
        for sel in selects:
            if not sel.is_displayed():
                continue
            label = _label_for_input(driver, sel)
            from selenium.webdriver.support.ui import Select as SeleniumSelect
            try:
                s = SeleniumSelect(sel)
                current = s.first_selected_option.text.strip()
                options = [o.text.strip() for o in s.options if o.text.strip()]
            except Exception:
                current = ""
                options = []
            if current in ("", "Select an option", "Select") and label and not _is_known(label):
                unknown.append({
                    "type": "select",
                    "label": label,
                    "element": sel,
                    "options": options,
                })
    except Exception:
        pass

    # --- Radio button groups ---
    try:
        radio_groups: Dict[str, Dict] = {}
        radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
        for r in radios:
            if not r.is_displayed():
                continue
            name = r.get_attribute("name") or ""
            label = _label_for_input(driver, r)
            if not label:
                label = name
            group_key = name or label
            if group_key not in radio_groups:
                radio_groups[group_key] = {"label": label, "elements": [], "options": []}
            val = r.get_attribute("value") or r.get_attribute("aria-label") or ""
            radio_groups[group_key]["elements"].append(r)
            if val:
                radio_groups[group_key]["options"].append(val)
        for gk, grp in radio_groups.items():
            if grp["label"] and not _is_known(grp["label"]):
                # check none selected
                if not any(e.is_selected() for e in grp["elements"]):
                    unknown.append({
                        "type": "radio",
                        "label": grp["label"],
                        "element": grp["elements"],
                        "options": grp["options"],
                    })
    except Exception:
        pass

    # --- Checkboxes (unanswered) ---
    try:
        checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
        for cb in checkboxes:
            if not cb.is_displayed():
                continue
            label = _label_for_input(driver, cb)
            if label and not _is_known(label) and not cb.is_selected():
                unknown.append({
                    "type": "checkbox",
                    "label": label,
                    "element": cb,
                    "options": ["yes", "no"],
                })
    except Exception:
        pass

    return unknown
