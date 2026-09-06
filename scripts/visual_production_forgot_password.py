import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://dailyexpensetracker-production-bf76.up.railway.app"
OUT_DIR = os.path.abspath(r".\screenshots\production_email")
os.makedirs(OUT_DIR, exist_ok=True)

def setup_driver(width=1400, height=900, is_mobile=False):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    if is_mobile:
        chrome_options.add_experimental_option("mobileEmulation", {
            "deviceMetrics": {"width": 375, "height": 812, "pixelRatio": 3.0},
            "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        })
    else:
        chrome_options.add_argument(f"--window-size={width},{height}")
    return webdriver.Chrome(options=chrome_options)

def run_visual_verification():
    # --- 1. Desktop Viewport ---
    print("--- 1. Testing Desktop Viewport (1400x900) ---")
    driver = setup_driver(1400, 900, is_mobile=False)
    try:
        # Step A: Forgot Password Page
        driver.get(f"{BASE_URL}/forgot-password")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        driver.save_screenshot(os.path.join(OUT_DIR, "01_forgot_password_desktop.png"))
        print("Captured: 01_forgot_password_desktop.png")

        # Step B: Enter email & submit
        email_input = driver.find_element(By.NAME, "email")
        email_input.clear()
        email_input.send_keys("test.expenseflow.verify@gmail.com")
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        # Step C: Wait for OTP verification page
        WebDriverWait(driver, 15).until(lambda d: "/verify-reset-otp" in d.current_url or "verify" in d.page_source.lower())
        time.sleep(1)
        driver.save_screenshot(os.path.join(OUT_DIR, "02_verify_reset_otp_desktop.png"))
        print("Captured: 02_verify_reset_otp_desktop.png")

        # Verify no sandbox warning on page
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert "Resend Sandbox Restriction" not in body_text, "Sandbox warning present in desktop!"
        print("Desktop verification: No Sandbox warning found! [PASS]")

    finally:
        driver.quit()

    # --- 2. Mobile Viewport (iPhone 375x812) ---
    print("\n--- 2. Testing Mobile Viewport (375x812) ---")
    driver_mobile = setup_driver(375, 812, is_mobile=True)
    try:
        # Step A: Mobile Forgot Password Page
        driver_mobile.get(f"{BASE_URL}/forgot-password")
        WebDriverWait(driver_mobile, 10).until(EC.presence_of_element_located((By.NAME, "email")))
        driver_mobile.save_screenshot(os.path.join(OUT_DIR, "03_forgot_password_mobile.png"))
        print("Captured: 03_forgot_password_mobile.png")

        # Step B: Enter email & submit
        email_input = driver_mobile.find_element(By.NAME, "email")
        email_input.clear()
        email_input.send_keys("test.expenseflow.verify@gmail.com")
        submit_btn = driver_mobile.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()

        # Step C: Wait for OTP verification page on mobile
        WebDriverWait(driver_mobile, 15).until(lambda d: "/verify-reset-otp" in d.current_url or "verify" in d.page_source.lower())
        time.sleep(1)
        driver_mobile.save_screenshot(os.path.join(OUT_DIR, "04_verify_reset_otp_mobile.png"))
        print("Captured: 04_verify_reset_otp_mobile.png")

        # Verify no sandbox warning on mobile
        body_text = driver_mobile.find_element(By.TAG_NAME, "body").text
        assert "Resend Sandbox Restriction" not in body_text, "Sandbox warning present in mobile!"
        print("Mobile verification: No Sandbox warning found! [PASS]")

    finally:
        driver_mobile.quit()

    print("\nALL VISUAL PRODUCTION VERIFICATIONS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_visual_verification()
