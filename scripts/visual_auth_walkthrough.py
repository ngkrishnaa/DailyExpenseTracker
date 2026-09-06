import os
import sys
import time
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mysql.connector
from app import app, get_db_connection_params
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5005"
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots", "auth")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def get_latest_otp(email, purpose):
    import json
    conn = mysql.connector.connect(**get_db_connection_params())
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT metadata FROM auth_otps WHERE email=%s AND purpose=%s AND is_used=FALSE ORDER BY id DESC LIMIT 1", (email, purpose))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row and row.get('metadata'):
        meta = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
        return meta.get('test_otp')
    return None

def get_driver(mobile=False):
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    
    width, height = (375, 812) if mobile else (1400, 900)
    
    try:
        options = webdriver.ChromeOptions()
        if os.path.exists(chrome_path):
            options.binary_location = chrome_path
        options.add_argument(f"--window-size={width},{height}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--headless=new")
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        try:
            options = webdriver.EdgeOptions()
            if os.path.exists(edge_path):
                options.binary_location = edge_path
            options.add_argument(f"--window-size={width},{height}")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--headless=new")
            driver = webdriver.Edge(options=options)
            return driver
        except Exception as e2:
            raise RuntimeError(f"Could not start Chrome or Edge: {e}, {e2}")

def take_shot(driver, name, desc):
    filepath = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
    time.sleep(0.8)
    driver.save_screenshot(filepath)
    print(f"  [SCREENSHOT] {name}: {desc} -> {filepath}")
    return filepath

def run_auth_verification():
    print("==================================================")
    print("STARTING LIVE VISUAL AUTH VERIFICATION")
    print("==================================================")
    
    # 1. Desktop Visual Check of Auth Pages
    print("\n--- 1. Testing Desktop Layouts (1400x900) ---")
    driver = get_driver(mobile=False)
    driver.set_window_size(1400, 900)
    wait = WebDriverWait(driver, 10)
    
    try:
        # Login page
        driver.get(f"{BASE_URL}/login")
        take_shot(driver, "01_desktop_login", "Login Page Desktop")
        
        # Register page
        driver.get(f"{BASE_URL}/register")
        take_shot(driver, "02_desktop_register", "Register Page Desktop")
        
        # Forgot password page
        driver.get(f"{BASE_URL}/forgot-password")
        take_shot(driver, "03_desktop_forgot_password", "Forgot Password Page Desktop")
        
        # 2. Registration Flow with OTP
        print("\n--- 2. Live Registration + OTP + Auto-login Flow ---")
        driver.get(f"{BASE_URL}/register")
        test_email = f"vis_user_{int(time.time())}@example.com"
        
        driver.find_element(By.NAME, "name").send_keys("Visual Tester")
        driver.find_element(By.NAME, "email").send_keys(test_email)
        driver.find_element(By.NAME, "password").send_keys("SecurePass@123")
        driver.find_element(By.NAME, "confirm_password").send_keys("SecurePass@123")
        try:
            driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']").click()
        except Exception:
            pass
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # Land on OTP verification screen
        wait.until(EC.presence_of_element_located((By.NAME, "otp")))
        take_shot(driver, "04_desktop_verify_otp", "Registration OTP Page")
        
        # Get OTP from database
        otp = get_latest_otp(test_email, 'registration')
        print(f"    Fetched OTP from DB for {test_email}: {otp}")
        assert otp is not None, "Registration OTP was not stored in auth_otps"
        
        driver.find_element(By.NAME, "otp").send_keys(otp)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # Land on dashboard
        wait.until(EC.url_contains("/dashboard"))
        print("    Successfully logged in and reached Dashboard!")
        take_shot(driver, "05_desktop_dashboard_after_register", "Dashboard after Registration")
        
        # 3. Logout
        print("\n--- 3. Logout Flow ---")
        driver.get(f"{BASE_URL}/logout")
        wait.until(EC.url_contains("/login"))
        take_shot(driver, "06_desktop_login_after_logout", "Login Page after Logout")
        
        # 4. Forgot Password -> OTP -> Reset Password -> Login Flow
        print("\n--- 4. Live Forgot Password + OTP + Reset Password Flow ---")
        driver.get(f"{BASE_URL}/forgot-password")
        driver.find_element(By.NAME, "email").send_keys(test_email)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        wait.until(EC.url_contains("/verify-reset-otp"))
        take_shot(driver, "07_desktop_verify_reset_otp", "Password Reset OTP Page")
        
        reset_otp = get_latest_otp(test_email, 'password_reset')
        print(f"    Fetched Reset OTP from DB for {test_email}: {reset_otp}")
        assert reset_otp is not None, "Reset OTP was not stored in auth_otps"
        
        driver.find_element(By.NAME, "otp").send_keys(reset_otp)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # Land on /reset-password
        wait.until(EC.url_contains("/reset-password"))
        take_shot(driver, "08_desktop_reset_password_page", "Reset Password Page")
        
        driver.find_element(By.NAME, "password").send_keys("NewSecurePass@456")
        driver.find_element(By.NAME, "confirm_password").send_keys("NewSecurePass@456")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # Redirected to /login
        wait.until(EC.url_contains("/login"))
        take_shot(driver, "09_desktop_login_after_reset", "Login Page after Password Reset")
        
        # Log in with new password
        print("    Logging in with new password...")
        driver.find_element(By.NAME, "email").send_keys(test_email)
        driver.find_element(By.NAME, "password").send_keys("NewSecurePass@456")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        wait.until(EC.url_contains("/dashboard"))
        print("    Successfully logged in with new password!")
        take_shot(driver, "10_desktop_dashboard_after_login", "Dashboard after Login with New Password")
        
        driver.get(f"{BASE_URL}/logout")
        wait.until(EC.url_contains("/login"))

        # 5. Google Account Flow: Set Application Password
        print("\n--- 5. Google User Set Application Password Flow ---")
        google_email = f"google_vis_{int(time.time())}@example.com"
        conn = mysql.connector.connect(**get_db_connection_params())
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (name, email, password, auth_provider, has_set_password)
            VALUES (%s, %s, NULL, 'google', FALSE)
        """, ("Google User", google_email))
        conn.commit()
        cur.close()
        conn.close()

        # Log in via test auth endpoint for Google user
        driver.get(f"{BASE_URL}/test-auth-login-google?email={google_email}")
        wait.until(EC.url_contains("/set-password"))
        print(f"    Current URL: {driver.current_url}")
        take_shot(driver, "11_desktop_set_password_page", "Set Password Page for New Google User")

        # Fill in password and confirm password
        driver.find_element(By.ID, "password").send_keys("AppPass@2026")
        driver.find_element(By.ID, "confirm_password").send_keys("AppPass@2026")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Land on dashboard
        wait.until(EC.url_contains("/dashboard"))
        print("    Password set! Redirected to Dashboard successfully.")
        take_shot(driver, "12_desktop_dashboard_after_set_password", "Dashboard after Setting App Password")

        # Check profile page shows Change Password now that password is set
        driver.get(f"{BASE_URL}/profile")
        take_shot(driver, "13_desktop_profile_after_password_set", "Profile Page with Change Password")

        # Logout
        driver.get(f"{BASE_URL}/logout")
        wait.until(EC.url_contains("/login"))

        # Now log in using the application password via normal login!
        print("    Testing email/password login for Google user with set app password...")
        driver.get(f"{BASE_URL}/login")
        driver.find_element(By.NAME, "email").send_keys(google_email)
        driver.find_element(By.NAME, "password").send_keys("AppPass@2026")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        wait.until(EC.url_contains("/dashboard"))
        print("    Successfully logged in with newly set application password!")
        take_shot(driver, "14_desktop_login_with_app_password", "Dashboard after login with app password")

        driver.get(f"{BASE_URL}/logout")
        wait.until(EC.url_contains("/login"))

        # 6. Mobile Layout Visual Verification (375x812)
        print("\n--- 6. Mobile Layouts (375x812 - iPhone dimensions) ---")
        driver.set_window_size(375, 812)
        time.sleep(1)

        driver.get(f"{BASE_URL}/login")
        take_shot(driver, "15_mobile_login", "Mobile Login Page")

        driver.get(f"{BASE_URL}/register")
        take_shot(driver, "16_mobile_register", "Mobile Register Page")

        driver.get(f"{BASE_URL}/forgot-password")
        take_shot(driver, "17_mobile_forgot_password", "Mobile Forgot Password Page")

        # Check set-password in mobile view with a new unconfigured Google user
        unconf_email = f"mobile_unconf_{int(time.time())}@example.com"
        conn = mysql.connector.connect(**get_db_connection_params())
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (name, email, password, auth_provider, has_set_password)
            VALUES (%s, %s, NULL, 'google', FALSE)
        """, ("Mobile Google User", unconf_email))
        conn.commit()
        cur.close()
        conn.close()

        driver.get(f"{BASE_URL}/test-auth-login-google?email={unconf_email}")
        wait.until(EC.url_contains("/set-password"))
        take_shot(driver, "18_mobile_set_password", "Mobile Set Password Page")

    finally:
        driver.quit()

    print("\n==================================================")
    print("ALL VISUAL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_auth_verification()
