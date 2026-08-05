import hashlib
import os
import pickle
import random
import sys
import time
from typing import Optional

import config
import constants
import utils

sys.stdout.reconfigure(encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By

from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

try:
    from selenium_stealth import stealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

class Linkedin:
    def __init__(self) -> None:
        utils.prYellow("🤖 Thanks for using Easy Apply Jobs bot, for more information you can visit our site - www.automated-bots.com")
        utils.prYellow("🌐 Bot will run in Chrome browser and log in Linkedin for you.")
        
        # Fix for WinError 193: Explicitly construct chromedriver path
        try:
            chrome_install = ChromeDriverManager().install()
            folder = os.path.dirname(chrome_install)
            chromedriver_path = os.path.join(folder, "chromedriver.exe")
            service = ChromeService(chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=utils.chromeBrowserOptions())
        except Exception as e:
            # Fallback to original method if explicit path fails
            if config.displayWarnings:
                utils.prYellow(f"⚠️ Warning: Could not use explicit chromedriver path, using default: {str(e)[0:50]}")
            self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=utils.chromeBrowserOptions())
        
        # Apply stealth mode if available
        if STEALTH_AVAILABLE:
            try:
                stealth(self.driver,
                        languages=["en-US", "en"],
                        vendor="Google Inc.",
                        platform="Win32",
                        webgl_vendor="Intel Inc.",
                        renderer="Intel Iris OpenGL Engine",
                        fix_hairline=True)
            except Exception as e:
                utils.prYellow(f"⚠️ Warning: Could not apply stealth mode: {str(e)}")
        
        self.cookies_path = f"{os.path.join(os.getcwd(),'cookies')}/{self.getHash(config.email)}.pkl"
        self.driver.get('https://www.linkedin.com')
        self.loadCookies()

        if not self.isLoggedIn():
            self.driver.get("https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
            utils.prYellow("🔄 Trying to log in Linkedin...")
            try:    
                self.driver.find_element("id","username").send_keys(config.email)
                time.sleep(2)
                self.driver.find_element("id","password").send_keys(config.password)
                time.sleep(2)
                self.driver.find_element("xpath",'//button[@type="submit"]').click()
                time.sleep(30)
            except Exception:
                utils.prRed("❌ Couldn't log in Linkedin by using Chrome. Please check your Linkedin credentials on config files line 7 and 8.")

            self.saveCookies()

    def getHash(self, string: str) -> str:
        return hashlib.md5(string.encode('utf-8')).hexdigest()

    def loadCookies(self) -> None:
        if os.path.exists(self.cookies_path):
            with open(self.cookies_path, "rb") as f:
                cookies = pickle.load(f)
            self.driver.delete_all_cookies()
            for cookie in cookies:
                self.driver.add_cookie(cookie)

    def saveCookies(self) -> None:
        try:
            # Get the directory path for cookies
            cookies_dir = os.path.dirname(self.cookies_path)
            
            # Create cookies directory if it doesn't exist
            if cookies_dir and not os.path.exists(cookies_dir):
                os.makedirs(cookies_dir, exist_ok=True)
            
            # Save cookies to file
            with open(self.cookies_path, "wb") as f:
                pickle.dump(self.driver.get_cookies(), f)
        except Exception as e:
            if config.displayWarnings:
                utils.prYellow(f"⚠️ Warning: Could not save cookies: {str(e)[0:100]}")
            # Don't raise the exception - cookie saving is not critical for bot operation
    
    def isLoggedIn(self) -> bool:
        self.driver.get('https://www.linkedin.com/feed')
        try:
            self.driver.find_element(By.XPATH,'//*[@id="ember14"]')
            return True
        except Exception:
            pass
        return False 
    
    def generateUrls(self) -> None:
        if not os.path.exists('data'):
            os.makedirs('data')
        try: 
            with open('data/urlData.txt', 'w',encoding="utf-8" ) as file:
                linkedinJobLinks = utils.LinkedinUrlGenerate().generateUrlLinks()
                for url in linkedinJobLinks:
                    file.write(url+ "\n")
            utils.prGreen("✅ Apply urls are created successfully, now the bot will visit those urls.")
        except Exception:
            utils.prRed("❌ Couldn't generate urls, make sure you have editted config file line 25-39")

    def linkJobApply(self) -> None:
        self.generateUrls()
        countApplied = 0
        countJobs = 0
        countBlacklisted = 0
        countAlreadyApplied = 0
        countCannotApply = 0
        startTime = time.time()
        reachedCap = False

        urlData = utils.getUrlDataFile()

        for url in urlData:        
            self.driver.get(url)
            time.sleep(random.uniform(1, constants.botSpeed))

            # Handle case where no jobs are found (//small element doesn't exist)
            try:
                totalJobs = self.driver.find_element(By.XPATH,'//small').text 
            except Exception as e:
                urlWords = utils.urlToKeywords(url)
                lineToWrite = "\n Category: " + urlWords[0] + ", Location: " + urlWords[1] + ", No jobs found for this search criteria. Skipping..."
                self.displayWriteResults(lineToWrite)
                if config.displayWarnings:
                    utils.prYellow(f"⚠️ Warning: No jobs found for {urlWords[0]} in {urlWords[1]}. The //small element was not found.")
                continue  # Skip to next URL

            totalPages = utils.jobsToPages(totalJobs)

            urlWords =  utils.urlToKeywords(url)
            lineToWrite = "\n Category: " + urlWords[0] + ", Location: " +urlWords[1] + ", Applying " +str(totalJobs)+ " jobs."
            self.displayWriteResults(lineToWrite)

            for page in range(totalPages):
                currentPageJobs = constants.jobsPerPage * page
                url = url +"&start="+ str(currentPageJobs)
                self.driver.get(url)
                time.sleep(random.uniform(1, constants.botSpeed))

                offersPerPage = self.driver.find_elements(By.XPATH, '//li[@data-occludable-job-id]')
                offerIds = []
                
                # Extract all offer IDs immediately to avoid stale element references
                for offer in offersPerPage:
                    try:
                        offerId = offer.get_attribute("data-occludable-job-id")
                        if offerId:
                            offerIds.append(int(offerId.split(":")[-1]))
                    except Exception as e:
                        if config.displayWarnings:
                            utils.prYellow(f"⚠️ Warning: Could not get offer ID: {str(e)[0:50]}")
                        continue
                
                time.sleep(random.uniform(1, constants.botSpeed))
                
                # Check for "Applied" status by re-finding elements to avoid stale references
                try:
                    offersPerPage = self.driver.find_elements(By.XPATH, '//li[@data-occludable-job-id]')
                    appliedOfferIds = []
                    for offer in offersPerPage:
                        try:
                            # Strict check: only match the 'Applied' badge LinkedIn shows
                            # for jobs you already submitted — not 'X applicants applied'.
                            already_applied = (
                                self.element_exists(offer, By.XPATH,
                                    ".//*[contains(@class,'job-card-container__footer-job-state') and normalize-space(text())='Applied']")
                                or self.element_exists(offer, By.XPATH,
                                    ".//*[contains(@class,'artdeco-inline-feedback') and normalize-space(text())='Applied']")
                                or self.element_exists(offer, By.XPATH,
                                    ".//li-icon[@type='checkmark-icon']/following-sibling::*[normalize-space(text())='Applied']")
                            )
                            if already_applied:
                                offerId = offer.get_attribute("data-occludable-job-id")
                                if offerId:
                                    appliedOfferIds.append(int(offerId.split(":")[-1]))
                        except Exception:
                            continue
                    # Remove already applied jobs from the list
                    offerIds = [jobId for jobId in offerIds if jobId not in appliedOfferIds]
                except Exception as e:
                    if config.displayWarnings:
                        utils.prYellow(f"⚠️ Warning: Could not check applied status: {str(e)[0:50]}")

                for jobID in offerIds:
                    offerPage = 'https://www.linkedin.com/jobs/view/' + str(jobID)
                    self.driver.get(offerPage)
                    time.sleep(random.uniform(1, constants.botSpeed))

                    countJobs += 1

                    jobProperties = self.getJobProperties(countJobs)
                    if "blacklisted" in jobProperties: 
                        countBlacklisted += 1
                        lineToWrite = jobProperties + " | " + "* 🤬 Blacklisted Job, skipped!: " +str(offerPage)
                        self.displayWriteResults(lineToWrite)
                    
                    else :                    
                        easyApplybutton = self.easyApplyButton()

                        if easyApplybutton is not None:
                            easyApplybutton.click()
                            time.sleep(random.uniform(1, constants.botSpeed))

                            result = self.completeApplyFlow(offerPage)
                            lineToWrite = jobProperties + " | " + result
                            self.displayWriteResults(lineToWrite)

                            if "Just Applied" in result:
                                countApplied += 1
                                if config.maxApplicationsPerRun and countApplied >= config.maxApplicationsPerRun:
                                    reachedCap = True
                            elif "Cannot apply" in result:
                                countCannotApply += 1
                        else:
                            if self.isAlreadyApplied():
                                countAlreadyApplied += 1
                                lineToWrite = jobProperties + " | " + "* 🥳 Already applied! Job: " +str(offerPage)
                                self.displayWriteResults(lineToWrite)
                            else:
                                countCannotApply += 1
                                lineToWrite = jobProperties + " | " + "* ⚠️ No Easy Apply button found (external apply or selector miss): " +str(offerPage)
                                self.displayWriteResults(lineToWrite)

                    if reachedCap:
                        break
                if reachedCap:
                    break
            if reachedCap:
                break

            utils.prYellow("Category: " + urlWords[0] + "," +urlWords[1]+ " applied: " + str(countApplied) +
                  " jobs out of " + str(countJobs) + ".")
        
        if reachedCap:
            utils.prYellow("🛑 Reached max applications per run limit (" + str(config.maxApplicationsPerRun) + "). Stopping.")
        durationSec = time.time() - startTime
        utils.printSessionSummary(
            countJobs, countApplied, countBlacklisted, countAlreadyApplied, countCannotApply, durationSec
        )
        utils.donate()

    def chooseResume(self) -> None:
        try:
            self.driver.find_element(
                By.CLASS_NAME, "jobs-document-upload__title--is-required")
            resumes = self.driver.find_elements(
                By.XPATH, "//div[contains(@class, 'ui-attachment--pdf')]")
            if (len(resumes) == 1 and resumes[0].get_attribute("aria-label") == "Select this resume"):
                resumes[0].click()
            elif (len(resumes) > 1 and resumes[config.preferredCv-1].get_attribute("aria-label") == "Select this resume"):
                resumes[config.preferredCv-1].click()
            elif (type(len(resumes)) != int):
                utils.prRed(
                    "❌ No resume has been selected please add at least one resume to your Linkedin account.")
        except Exception:
            pass

    def getJobProperties(self, count: int) -> str:
        textToWrite = ""
        jobTitle = ""
        jobLocation = ""

        try:
            titleSelectors = [
                "//h1[contains(@class, 'job-title')]",
                "//div[contains(@class,'job-details-jobs-unified-top-card')]//h1",
                "//h1[contains(@class,'t-24')]",
            ]
            jobTitle = ""
            for selector in titleSelectors:
                try:
                    jobTitle = self.driver.find_element(By.XPATH, selector).get_attribute("innerHTML").strip()
                    if jobTitle:
                        break
                except Exception:
                    continue
            res = [blItem for blItem in config.blackListTitles if (blItem.lower() in jobTitle.lower())]
            if (len(res) > 0):
                jobTitle += "(blacklisted title: " + ' '.join(res) + ")"
        except Exception as e:
            if (config.displayWarnings):
                utils.prYellow("⚠️ Warning in getting jobTitle: " + str(e)[0:50])
            jobTitle = ""

        try:
            time.sleep(5)
            detailSelectors = [
                "//div[contains(@class,'job-details-jobs-unified-top-card__primary-description-container')]",
                "//div[contains(@class, 'job-details-jobs-unified-top-card')]//div[contains(@class,'tvm__text')]/..",
                "//div[contains(@class, 'job-details-jobs')]//div",
            ]
            jobDetail = ""
            for selector in detailSelectors:
                try:
                    jobDetail = self.driver.find_element(By.XPATH, selector).text.replace("·", "|")
                    if jobDetail:
                        break
                except Exception:
                    continue
            res = [blItem for blItem in config.blacklistCompanies if (blItem.lower() in jobTitle.lower())]
            if (len(res) > 0):
                jobDetail += "(blacklisted company: " + ' '.join(res) + ")"
        except Exception as e:
            if (config.displayWarnings):
                print(e)
                utils.prYellow("⚠️ Warning in getting jobDetail: " + str(e)[0:100])
            jobDetail = ""

        try:
            jobWorkStatusSpans = self.driver.find_elements(By.XPATH, "//span[contains(@class,'ui-label ui-label--accent-3 text-body-small')]//span[contains(@aria-hidden,'true')]")
            for span in jobWorkStatusSpans:
                jobLocation = jobLocation + " | " + span.text

        except Exception as e:
            if (config.displayWarnings):
                print(e)
                utils.prYellow("⚠️ Warning in getting jobLocation: " + str(e)[0:100])
            jobLocation = ""

        textToWrite = str(count) + " | " + jobTitle +" | " + jobDetail + jobLocation
        return textToWrite

    def easyApplyButton(self) -> Optional[webdriver.remote.webelement.WebElement]:
        time.sleep(random.uniform(1, constants.botSpeed))
        selectors = [
            "//button[@id='jobs-apply-button-id']",
            "//button[contains(@class,'jobs-apply-button') and .//span[normalize-space(text())='Easy Apply']]",
            "//button[contains(@aria-label,'Easy Apply')]",
        ]
        for selector in selectors:
            try:
                button = self.driver.find_element(By.XPATH, selector)
                if button.is_displayed():
                    return button
            except Exception:
                continue

        return None

    def isAlreadyApplied(self) -> bool:
        try:
            return self.element_exists(
                self.driver,
                By.XPATH,
                "//span[contains(@class,'artdeco-inline-feedback') and contains(normalize-space(text()),'Applied')]"
                " | //*[contains(@class,'jobs-s-apply') and contains(normalize-space(text()),'Applied')]"
            )
        except Exception:
            return False

    def fillPhoneNumber(self) -> None:
        """Fill phone number fields if they exist and are empty"""
        try:
            # Get phone number from config or additionalQuestions.yaml
            phone_number = ""
            
            # Try to get from config.Phone first
            if hasattr(config, 'Phone') and config.Phone and config.Phone.strip():
                phone_number = config.Phone.strip()
            else:
                # Try to read from additionalQuestions.yaml if available
                try:
                    import yaml
                    if os.path.exists('additionalQuestions.yaml'):
                        with open('additionalQuestions.yaml', 'r', encoding='utf-8') as f:
                            questions = yaml.safe_load(f)
                            if questions and 'inputField' in questions:
                                phone_number = questions['inputField'].get('Phone Number', '').strip()
                except Exception:
                    pass
            
            if not phone_number:
                return  # No phone number configured, skip filling
            
            # Try multiple selectors to find phone number input fields
            phone_selectors = [
                "input[type='tel']",
                "input[name*='phone']",
                "input[id*='phone']",
                "input[aria-label*='phone']",
                "input[placeholder*='phone']",
                "input[data-test-single-line-text-input]",
                "input[class*='phone']"
            ]
            
            phone_filled = False
            
            # Also try XPath selectors for case-insensitive matching
            xpath_selectors = [
                "//input[contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'phone')]",
                "//input[contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'phone')]",
                "//input[contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'phone')]",
                "//input[contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'phone')]"
            ]
            
            # Try CSS selectors first
            for selector in phone_selectors:
                try:
                    phone_inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for phone_input in phone_inputs:
                        try:
                            # Check if field is visible and empty
                            if phone_input.is_displayed():
                                current_value = phone_input.get_attribute("value") or ""
                                if current_value == "":
                                    phone_input.clear()
                                    phone_input.send_keys(phone_number)
                                    time.sleep(0.5)
                                    phone_filled = True
                                    if config.displayWarnings:
                                        utils.prYellow(f"✅ Filled phone number: {phone_number}")
                                    break
                        except Exception:
                            continue
                    if phone_filled:
                        break
                except Exception:
                    continue
            
            # Try XPath selectors if CSS didn't work
            if not phone_filled:
                for xpath in xpath_selectors:
                    try:
                        phone_inputs = self.driver.find_elements(By.XPATH, xpath)
                        for phone_input in phone_inputs:
                            try:
                                if phone_input.is_displayed():
                                    current_value = phone_input.get_attribute("value") or ""
                                    if current_value == "":
                                        phone_input.clear()
                                        phone_input.send_keys(phone_number)
                                        time.sleep(0.5)
                                        phone_filled = True
                                        if config.displayWarnings:
                                            utils.prYellow(f"✅ Filled phone number: {phone_number}")
                                        break
                            except Exception:
                                continue
                        if phone_filled:
                            break
                    except Exception:
                        continue
                
        except Exception as e:
            if config.displayWarnings:
                utils.prYellow(f"⚠️ Warning: Error in fillPhoneNumber: {str(e)[0:50]}")

    def completeApplyFlow(self, offerPage: str) -> str:
        maxSteps = 15
        for _ in range(maxSteps):
            self.chooseResume()
            self.fillPhoneNumber()

            submitButton = self.findVisibleButton(["Submit application"])
            if submitButton is not None:
                if config.dryRun:
                    return "* 🧪 DRY RUN - Would apply to this job: " + str(offerPage)
                submitButton.click()
                time.sleep(random.uniform(1, constants.botSpeed))
                return "* 🥳 Just Applied to this job: " + str(offerPage)

            reviewButton = self.findVisibleButton(["Review your application"])
            if reviewButton is not None:
                reviewButton.click()
                time.sleep(random.uniform(1, constants.botSpeed))
                if config.followCompanies is False:
                    try:
                        self.driver.find_element(By.CSS_SELECTOR, "label[for='follow-company-checkbox']").click()
                    except Exception:
                        pass
                continue

            nextButton = self.findVisibleButton(["Continue to next step", "Next"])
            if nextButton is not None:
                nextButton.click()
                time.sleep(random.uniform(1, constants.botSpeed))
                continue

            break

        return "* 🥵 Cannot apply to this Job! " + str(offerPage)

    def findVisibleButton(self, labels: list) -> Optional[webdriver.remote.webelement.WebElement]:
        for label in labels:
            selectors = [
                (By.CSS_SELECTOR, f"button[aria-label='{label}']"),
                (By.XPATH, f"//button[.//span[normalize-space(text())='{label}']]"),
            ]
            for by, selector in selectors:
                try:
                    button = self.driver.find_element(by, selector)
                    if button.is_displayed() and button.is_enabled():
                        return button
                except Exception:
                    continue
        return None

    def displayWriteResults(self, lineToWrite: str) -> None:
        try:
            print(lineToWrite)
            utils.writeResults(lineToWrite)
        except Exception as e:
            utils.prRed("❌ Error in DisplayWriteResults: " +str(e))

    def element_exists(self, parent: webdriver.remote.webelement.WebElement, by: str, selector: str) -> bool:
        return len(parent.find_elements(by, selector)) > 0


def main() -> None:
    start = time.time()
    bot = Linkedin()
    bot.linkJobApply()
    end = time.time()
    utils.prYellow("---Took: " + str(round((time.time() - start)/60)) + " minute(s).")


if __name__ == "__main__":
    main()
