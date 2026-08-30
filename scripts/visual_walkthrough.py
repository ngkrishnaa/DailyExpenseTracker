import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService

BASE_URL = "http://127.0.0.1:5000"
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def get_driver():
    # Try Chrome first, then Edge
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    
    # Try Chrome
    try:
        options = webdriver.ChromeOptions()
        if os.path.exists(chrome_path):
            options.binary_location = chrome_path
        options.add_argument("--window-size=1400,900")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)
        print("Initialized Chrome browser driver.")
        return driver
    except Exception as e1:
        print(f"Chrome initialization failed: {e1}. Trying Edge...")
        try:
            options = webdriver.EdgeOptions()
            if os.path.exists(edge_path):
                options.binary_location = edge_path
            options.add_argument("--window-size=1400,900")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            driver = webdriver.Edge(options=options)
            print("Initialized Edge browser driver.")
            return driver
        except Exception as e2:
            print(f"Edge initialization failed: {e2}")
            # Try headless Chrome as fallback
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1400,900")
            driver = webdriver.Chrome(options=options)
            print("Initialized Headless Chrome driver.")
            return driver

import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def safe_click(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.4)
    try:
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)

def save_step_screenshot(driver, step_name, description):
    filename = f"{step_name}.png"
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    time.sleep(1) # Allow CSS transitions / animations to settle
    driver.save_screenshot(filepath)
    print(f"[SCREENSHOT] {step_name}: {description} -> {filepath}")
    return filepath

def navigate_via_drawer(driver, wait, href_pattern):
    if not driver.execute_script("return document.body.classList.contains('drawer-open');"):
        drawer_toggle = wait.until(EC.element_to_be_clickable((By.ID, "drawer-toggle")))
        safe_click(driver, drawer_toggle)
        time.sleep(0.5)
    
    if href_pattern == "expenses":
        css = ".app-nav a[href='/expenses']"
    elif href_pattern == "dashboard":
        css = ".app-nav a[href='/dashboard']"
    elif href_pattern == "add_expense":
        css = ".app-nav a[href='/expenses/add']"
    elif href_pattern == "budget":
        css = ".app-nav a[href='/budget']"
    elif href_pattern == "reports":
        css = ".app-nav a[href='/reports']"
    elif href_pattern == "profile":
        css = ".app-nav a[href='/profile']"
    else:
        css = f".app-nav a[href*='{href_pattern}']"
        
    nav_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, css)))
    safe_click(driver, nav_link)
    time.sleep(0.6)

def run_visual_walkthrough():
    driver = get_driver()
    driver.maximize_window()
    wait = WebDriverWait(driver, 10)

    try:
        # Step 1: Open Website Home Page
        print("\n--- STEP 1: Open Website Home Page ---")
        driver.get(BASE_URL + "/")
        save_step_screenshot(driver, "01_home_page", "Website Landing Page")
        time.sleep(1.5)

        # Step 2: Open Login Page
        print("\n--- STEP 2: Navigate to Login Page ---")
        login_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='login']")))
        safe_click(driver, login_link)
        save_step_screenshot(driver, "02_login_page", "Login Screen")
        time.sleep(1)

        # Step 3: Perform Login
        print("\n--- STEP 3: Fill Credentials and Log In ---")
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        password_input = driver.find_element(By.NAME, "password")
        email_input.clear()
        email_input.send_keys("demo@expenseflow.com")
        password_input.clear()
        password_input.send_keys("Password123")
        save_step_screenshot(driver, "03_login_filled", "Login form filled with demo credentials")
        time.sleep(1)
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        # Step 4: Verify Dashboard After Login (Full-Width View with Smart Financial Insights)
        print("\n--- STEP 4: Land on Dashboard (Full-Width with Smart Insights) ---")
        insights_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".insights-panel")))
        save_step_screenshot(driver, "04_dashboard_overview", "Dashboard overview with Smart Financial Insights and full-width layout")
        time.sleep(0.5)
        
        # Step 4c: Dedicated Financial Insights Section
        print("\n--- STEP 4c: View Financial Insights Section ---")
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", insights_el)
        time.sleep(1)
        save_step_screenshot(driver, "04c_financial_insights_panel", "Smart Financial Insights 4-card intelligence grid")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

        # Step 4b: Test Hamburger Menu / Slide-out Drawer
        print("\n--- STEP 4b: Open Slide-Out Navigation Drawer ---")
        drawer_toggle = wait.until(EC.element_to_be_clickable((By.ID, "drawer-toggle")))
        safe_click(driver, drawer_toggle)
        time.sleep(0.8)
        save_step_screenshot(driver, "04b_slideout_drawer_open", "Slide-out navigation drawer smoothly opened with all options and close button")
        time.sleep(1)

        # Step 5: Click Add Expense from Drawer
        print("\n--- STEP 5: Navigate to Add Expense Form from Drawer ---")
        add_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".app-nav a[href*='/expenses/add']")))
        safe_click(driver, add_btn)
        wait.until(EC.presence_of_element_located((By.NAME, "amount")))
        save_step_screenshot(driver, "05_add_expense_form", "Empty Add Expense form in full-width mode")
        time.sleep(1)

        # Step 6: Fill and Save New Expense
        print("\n--- STEP 6: Enter Expense Details ---")
        driver.find_element(By.NAME, "amount").send_keys("450.00")
        Select(driver.find_element(By.NAME, "category")).select_by_visible_text("Food")
        Select(driver.find_element(By.NAME, "payment_method")).select_by_visible_text("UPI")
        desc_box = driver.find_element(By.NAME, "description")
        desc_box.clear()
        desc_box.send_keys("Team lunch at cafe")
        save_step_screenshot(driver, "06_add_expense_filled", "Add Expense form filled with Food / UPI / ₹450")
        time.sleep(1)
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, ".app-form button[type='submit']"))

        # Step 7: View New Expense in My Expenses (with Export CSV button)
        print("\n--- STEP 7: View My Expenses List with Export CSV button ---")
        wait.until(EC.presence_of_element_located((By.ID, "export-csv-btn")))
        save_step_screenshot(driver, "07_my_expenses_after_add", "My Expenses table with Export CSV button and ₹450 record")
        time.sleep(1.5)

        # Step 8: Edit the Expense
        print("\n--- STEP 8: Click Edit on the Expense ---")
        edit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".edit-btn")))
        safe_click(driver, edit_btn)
        wait.until(EC.presence_of_element_located((By.NAME, "amount")))
        save_step_screenshot(driver, "08_edit_expense_form", "Edit Expense pre-filled form")
        time.sleep(1)

        # Step 9: Update Amount and Description
        print("\n--- STEP 9: Update Expense to ₹520.00 ---")
        amount_input = driver.find_element(By.NAME, "amount")
        amount_input.clear()
        amount_input.send_keys("520.00")
        desc_input = driver.find_element(By.NAME, "description")
        desc_input.clear()
        desc_input.send_keys("Team lunch at bistro (updated)")
        save_step_screenshot(driver, "09_edit_expense_filled", "Edit form updated to ₹520.00")
        time.sleep(1)
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, ".app-form button[type='submit']"))

        # Step 10: View Updated Expense in My Expenses
        print("\n--- STEP 10: Verify Updated Record in Table ---")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".expense-table")))
        save_step_screenshot(driver, "10_my_expenses_after_edit", "My Expenses table showing updated ₹520.00 record")
        time.sleep(1.5)

        # Step 11: Return to Dashboard and Check Updates via Drawer
        print("\n--- STEP 11: Navigate Back to Dashboard via Drawer ---")
        navigate_via_drawer(driver, wait, "dashboard")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".summary-grid")))
        save_step_screenshot(driver, "11_dashboard_after_expense", "Dashboard reflecting updated ₹520.00 spent")
        time.sleep(1.5)

        # Step 12: Set Monthly Budget via Drawer
        print("\n--- STEP 12: Navigate to Budget Page via Drawer ---")
        navigate_via_drawer(driver, wait, "budget")
        wait.until(EC.presence_of_element_located((By.NAME, "budget_amount")))
        save_step_screenshot(driver, "12_budget_page_form", "Monthly Budget setting form in full width")
        time.sleep(1)

        print("\n--- STEP 13: Save Monthly Budget of ₹10,000.00 ---")
        budget_input = driver.find_element(By.NAME, "budget_amount")
        budget_input.clear()
        budget_input.send_keys("10000.00")
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, ".app-form button[type='submit']"))
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".budget-hero")))
        save_step_screenshot(driver, "13_budget_hero_saved", "Budget hero card showing ₹10,000.00 budget and balance")
        time.sleep(1.5)

        # Step 14: Check Dashboard Budget Progress Widget via Drawer
        print("\n--- STEP 14: Return to Dashboard for Budget Progress via Drawer ---")
        navigate_via_drawer(driver, wait, "dashboard")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".budget-panel")))
        save_step_screenshot(driver, "14_dashboard_budget_progress", "Dashboard with live budget progress bar and remaining balance")
        time.sleep(1.5)

        # Step 14b: Test Notifications Bell & Dropdown
        print("\n--- STEP 14b: Test Notification Bell and Dropdown ---")
        notif_btn = wait.until(EC.element_to_be_clickable((By.ID, "notification-bell-btn")))
        safe_click(driver, notif_btn)
        time.sleep(0.8)
        save_step_screenshot(driver, "14b_notifications_dropdown_open", "Notifications bell dropdown open displaying threshold alert notifications")
        time.sleep(1)
        # Close notification dropdown by clicking outside or bell
        safe_click(driver, notif_btn)
        time.sleep(0.5)

        # Step 14c: Test Advanced Search & Amount Filters
        print("\n--- STEP 14c: Test Advanced Search & Amount Filters ---")
        navigate_via_drawer(driver, wait, "expenses")
        wait.until(EC.presence_of_element_located((By.NAME, "min_amount")))
        min_box = driver.find_element(By.NAME, "min_amount")
        min_box.clear()
        min_box.send_keys("100")
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, ".filter-actions button[type='submit']"))
        time.sleep(1)
        save_step_screenshot(driver, "14c_advanced_filters_active", "My Expenses table filtered with Min Amount and Active Filter Chips")
        time.sleep(1.5)

        # Step 15: Open Reports via Drawer
        print("\n--- STEP 15: Navigate to Reports via Drawer ---")
        navigate_via_drawer(driver, wait, "reports")
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".chart-panel, .report-summary")))
        save_step_screenshot(driver, "15_reports_page", "Spending Reports and Category Analytics in full-width")
        time.sleep(1.5)

        # Step 16: Check Profile via Drawer
        print("\n--- STEP 16: Navigate to Profile via Drawer ---")
        navigate_via_drawer(driver, wait, "profile")
        wait.until(EC.presence_of_element_located((By.NAME, "name")))
        save_step_screenshot(driver, "16_profile_page", "User Profile and Password Settings in full-width")
        time.sleep(1.5)

        print("\n========================================================")
        print("ALL VISUAL WALKTHROUGH STEPS COMPLETED SUCCESSFULLY!")
        print(f"Screenshots saved to: {SCREENSHOTS_DIR}")
        print("========================================================")

    finally:
        driver.quit()

if __name__ == "__main__":
    run_visual_walkthrough()
