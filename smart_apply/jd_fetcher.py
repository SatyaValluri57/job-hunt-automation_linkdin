"""
Fetches job description text from the current LinkedIn job page.
Used by the matcher before deciding to apply.
"""

import time
from selenium.webdriver.common.by import By


def fetch_jd_text(driver) -> str:
    """
    Extracts job description text from the currently loaded LinkedIn job page.
    Returns empty string if extraction fails.
    """
    selectors = [
        "//div[contains(@class,'jobs-description__content')]",
        "//div[contains(@class,'jobs-box__html-content')]",
        "//article[contains(@class,'jobs-description')]",
        "//div[@id='job-details']",
    ]
    time.sleep(1)
    for xpath in selectors:
        try:
            el = driver.find_element(By.XPATH, xpath)
            text = el.text.strip()
            if text:
                return text
        except Exception:
            continue
    return ""
