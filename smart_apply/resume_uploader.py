"""
Phase 3 — Resume upload support.
Detects LinkedIn Easy Apply upload field and uploads a local resume file.
Falls back gracefully to LinkedIn-saved resume selection if no upload field present.
"""

import os
import time
from typing import Optional

from selenium.webdriver.common.by import By


RESUMES_DIR = "resumes"


def get_resume_path(preferred_index: int = 1) -> Optional[str]:
    """
    Returns absolute path of the preferred local resume file.
    preferred_index: 1-based (1 = first file alphabetically).
    """
    if not os.path.exists(RESUMES_DIR):
        return None
    files = sorted([
        f for f in os.listdir(RESUMES_DIR)
        if f.lower().endswith((".pdf", ".docx", ".doc"))
    ])
    if not files:
        return None
    idx = max(0, preferred_index - 1)
    idx = min(idx, len(files) - 1)
    return os.path.abspath(os.path.join(RESUMES_DIR, files[idx]))


def _is_cover_letter_field(inp) -> bool:
    """True if the input's own attributes suggest it's for a cover letter / other document, not a resume."""
    try:
        attrs = " ".join([
            inp.get_attribute("id") or "",
            inp.get_attribute("name") or "",
            inp.get_attribute("aria-label") or "",
        ]).lower()
        return "cover" in attrs
    except Exception:
        return False


def _verify_upload(driver, inp, resume_path: str) -> bool:
    """
    Best-effort check that the resume was actually accepted by the form.
    Returns False if an error indicator is visible (definite failure).
    Returns True if the filename is found reflected back in the page.
    If neither can be confirmed, logs a warning and returns True (send_keys did not raise),
    so an unconfirmed upload does not get treated as a hard failure and re-attempted elsewhere.
    """
    filename = os.path.basename(resume_path)
    try:
        errors = driver.find_elements(
            By.XPATH,
            "//*[contains(@class,'artdeco-inline-feedback--error') or contains(@class,'file-upload-error')]"
        )
        if any(e.is_displayed() for e in errors):
            return False
    except Exception:
        pass
    try:
        value = inp.get_attribute("value") or ""
        if filename.lower() in value.lower():
            return True
    except Exception:
        pass
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        if filename in page_text:
            return True
    except Exception:
        pass
    print(f"⚠️ Could not confirm resume upload was accepted (filename '{filename}' not found in form).")
    return True


def detect_and_upload_resume(driver, preferred_index: int = 1, explicit_path: Optional[str] = None) -> bool:
    """
    Checks if Easy Apply form has a file upload input for resume.
    If found, uploads explicit_path (if given and it exists) or the preferred
    local resume file from RESUMES_DIR otherwise.
    Returns True if upload was performed and not flagged as failed, False if not
    (fallback to LinkedIn saved resume) — either because no field was found or
    the field was ambiguous (e.g. could be a cover-letter upload) and we chose
    not to guess.
    """
    resume_path = explicit_path if explicit_path and os.path.exists(explicit_path) else get_resume_path(preferred_index)
    if not resume_path:
        return False  # no local resumes, use LinkedIn saved

    # Specific, unambiguous selectors first — these clearly target a resume/CV upload field.
    specific_selectors = [
        "input[type='file'][accept*='pdf']",
        "input[type='file'][accept*='.pdf']",
        "input[type='file'][id*='resume' i]",
        "input[type='file'][name*='resume' i]",
        "input[type='file'][aria-label*='resume' i]",
        "input[type='file'][id*='cv' i]",
        "input[type='file'][aria-label*='cv' i]",
    ]

    for selector in specific_selectors:
        try:
            upload_inputs = [
                inp for inp in driver.find_elements(By.CSS_SELECTOR, selector)
                if not _is_cover_letter_field(inp)
            ]
            if not upload_inputs:
                continue
            inp = upload_inputs[0]
            inp.send_keys(resume_path)
            time.sleep(1.5)
            return _verify_upload(driver, inp, resume_path)
        except Exception:
            continue

    # No resume-specific field matched. Only fall back to a bare file input when
    # there is exactly one on the page — otherwise we can't tell resume apart from
    # cover-letter/other-document fields, so don't guess.
    try:
        generic_inputs = [
            inp for inp in driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if not _is_cover_letter_field(inp)
        ]
    except Exception:
        generic_inputs = []

    if len(generic_inputs) == 1:
        try:
            inp = generic_inputs[0]
            inp.send_keys(resume_path)
            time.sleep(1.5)
            return _verify_upload(driver, inp, resume_path)
        except Exception:
            return False
    elif len(generic_inputs) > 1:
        print(
            f"⚠️ Found {len(generic_inputs)} unlabeled file upload fields — "
            "cannot safely tell which is the resume field. Skipping upload for this job."
        )

    return False  # no unambiguous upload field found


def choose_or_upload_resume(driver, preferred_index: int = 1, explicit_path: Optional[str] = None) -> None:
    """
    Main entry: try upload first (explicit_path if given, else the preferred
    file in RESUMES_DIR), then fall back to selecting LinkedIn saved resume.
    """
    uploaded = detect_and_upload_resume(driver, preferred_index, explicit_path)
    if not uploaded:
        # fall back to selecting LinkedIn saved resume (original chooseResume logic)
        _select_linkedin_resume(driver, preferred_index)


def _select_linkedin_resume(driver, preferred_index: int = 1) -> None:
    """Select from LinkedIn-saved resumes (original bot logic)."""
    try:
        driver.find_element(By.CLASS_NAME, "jobs-document-upload__title--is-required")
        resumes = driver.find_elements(By.XPATH, "//div[contains(@class, 'ui-attachment--pdf')]")
        if len(resumes) == 1 and resumes[0].get_attribute("aria-label") == "Select this resume":
            resumes[0].click()
        elif len(resumes) > 1:
            idx = max(0, preferred_index - 1)
            idx = min(idx, len(resumes) - 1)
            if resumes[idx].get_attribute("aria-label") == "Select this resume":
                resumes[idx].click()
    except Exception:
        pass
