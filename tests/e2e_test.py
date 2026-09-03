"""
Comprehensive End-to-End Test Suite for DailyExpenseTracker
===========================================================
Tests every user journey, edge case, and potential failure point.
Produces a structured JSON report.
"""

import json
import sys
import os
import traceback
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch
from collections import OrderedDict

# Ensure safe encoding for Windows console output
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import (
    app as flask_app,
    db,
    pending_registrations,
    password_reset_requests,
    CATEGORIES,
    PAYMENT_METHODS,
    EXPENSES_PER_PAGE,
)
from werkzeug.security import generate_password_hash, check_password_hash


class E2ETestRunner:
    def __init__(self):
        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False
        self.client = flask_app.test_client()
        self.created_user_ids = []
        self.results = []
        self.section = ""
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0
        self.ts_suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")

    def _record(self, test_name, status, detail=""):
        entry = {"section": self.section, "test": test_name, "status": status, "detail": detail}
        self.results.append(entry)
        if status == "PASS":
            self.pass_count += 1
        elif status == "FAIL":
            self.fail_count += 1
        elif status == "WARN":
            self.warn_count += 1
        icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}.get(status, "[INFO]")
        detail_str = f" - {detail}" if detail else ""
        print(f"  {icon} {test_name}{detail_str}")

    def _assert(self, condition, test_name, fail_detail="", pass_detail=""):
        if condition:
            self._record(test_name, "PASS", pass_detail)
        else:
            self._record(test_name, "FAIL", fail_detail)

    def _create_user(self, name, email, password="Password123"):
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email.lower(), generate_password_hash(password)),
        )
        db.commit()
        uid = cursor.lastrowid
        cursor.close()
        self.created_user_ids.append(uid)
        return uid

    def _login(self, email, password="Password123"):
        return self.client.post("/login", data={"email": email, "password": password}, follow_redirects=True)

    def _logout(self):
        return self.client.post("/logout", follow_redirects=True)

    def _add_expense(self, amount, category="Food", pay="UPI", desc="Test", exp_date=None):
        return self.client.post("/expenses/add", data={
            "amount": str(amount), "category": category,
            "expense_date": (exp_date or date.today()).isoformat(),
            "payment_method": pay, "description": desc,
        }, follow_redirects=True)

    def cleanup(self):
        if self.created_user_ids:
            cursor = db.cursor()
            fmt = ",".join(["%s"] * len(self.created_user_ids))
            for tbl in ("notifications", "expenses", "budgets"):
                cursor.execute(f"DELETE FROM {tbl} WHERE user_id IN ({fmt})", tuple(self.created_user_ids))
            cursor.execute(f"DELETE FROM users WHERE id IN ({fmt})", tuple(self.created_user_ids))
            db.commit()
            cursor.close()
        pending_registrations.clear()
        password_reset_requests.clear()

    def test_01_public_pages(self):
        self.section = "1. Public Pages & Routing"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        res = self.client.get("/")
        self._assert(res.status_code == 200, "Home page loads (200)")
        self._assert(b"ExpenseFlow" in res.data, "Home page contains branding")
        res = self.client.get("/login")
        self._assert(res.status_code == 200, "Login page loads (200)")
        res = self.client.get("/register")
        self._assert(res.status_code == 200, "Register page loads (200)")
        res = self.client.get("/forgot-password")
        self._assert(res.status_code == 200, "Forgot password page loads (200)")
        res = self.client.get("/this-page-does-not-exist-xyz")
        self._assert(res.status_code == 404, "Non-existent page returns 404")
        self._assert(b"Page not found" in res.data, "404 page shows error message")
        res = self.client.get("/test-db")
        self._assert(res.status_code == 200, "/test-db endpoint works")
        self._assert(b"Database connected" in res.data, "/test-db confirms DB connection")

    def test_02_protected_routes_redirect(self):
        self.section = "2. Protected Routes (Unauthenticated)"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        for path in ["/dashboard", "/expenses", "/expenses/add", "/budget", "/reports", "/profile"]:
            res = self.client.get(path)
            self._assert(res.status_code == 302, f"GET {path} redirects when unauthenticated", f"Got {res.status_code}")
        for path in ["/logout", "/expenses/1/delete", "/notifications/1/read", "/notifications/read-all"]:
            res = self.client.post(path)
            self._assert(res.status_code == 302, f"POST {path} redirects when unauthenticated", f"Got {res.status_code}")
        res = self.client.get("/expenses/export")
        self._assert(res.status_code == 302, "GET /expenses/export redirects when unauthenticated")

    def test_03_registration_flow(self):
        self.section = "3. Registration & OTP Verification"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_reg_{self.ts_suffix}@test.com"
        with patch("app.send_otp_email") as mock_send:
            mock_send.return_value = True
            res = self.client.post("/register", data={"name": "T", "email": email, "password": "Ab1", "confirm_password": "Ab1"})
            self._assert(b"at least 8 characters" in res.data, "Rejects password < 8 chars")
            res = self.client.post("/register", data={"name": "T", "email": email, "password": "12345678", "confirm_password": "12345678"})
            self._assert(b"at least one letter" in res.data, "Rejects password without letters")
            res = self.client.post("/register", data={"name": "T", "email": email, "password": "abcdefgh", "confirm_password": "abcdefgh"})
            self._assert(b"at least one number" in res.data, "Rejects password without numbers")
            res = self.client.post("/register", data={"name": "T", "email": email, "password": "Password123", "confirm_password": "Different456"})
            self._assert(b"do not match" in res.data, "Rejects mismatched passwords")
            res = self.client.post("/register", data={"name": "E2E User", "email": email, "password": "Password123", "confirm_password": "Password123"})
            self._assert(email in pending_registrations, "Registration creates pending entry")
            self._assert(len(pending_registrations[email]["otp"]) == 6, "OTP is 6 digits")
            self._assert(mock_send.called, "OTP email function was called")
            res = self.client.post(f"/verify-otp?email={email}", data={"otp": "000000"})
            self._assert(b"Incorrect OTP" in res.data, "Wrong OTP rejected with error")
            valid_otp = pending_registrations[email]["otp"]
            res = self.client.post(f"/verify-otp?email={email}", data={"otp": valid_otp}, follow_redirects=True)
            self._assert(b"Account created successfully" in res.data, "Correct OTP creates account")
            self._assert(email not in pending_registrations, "Pending registration cleaned up")
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            self._assert(user is not None, "User exists in database after OTP")
            if user:
                self.created_user_ids.append(user["id"])
            res = self.client.get("/dashboard")
            self._assert(res.status_code == 200, "User auto-logged in after registration")
            self._logout()
        with patch("app.send_otp_email") as mock_send:
            mock_send.return_value = True
            res = self.client.post("/register", data={"name": "Dup", "email": email, "password": "Password123", "confirm_password": "Password123"})
            self._assert(b"already exists" in res.data, "Duplicate email rejected")

    def test_04_otp_edge_cases(self):
        self.section = "4. OTP Edge Cases"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_otp_{self.ts_suffix}@test.com"
        with patch("app.send_otp_email") as mock_send:
            mock_send.return_value = True
            self.client.post("/register", data={"name": "OTP Edge", "email": email, "password": "Password123", "confirm_password": "Password123"})
            pending_registrations[email]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=10)
            res = self.client.post(f"/verify-otp?email={email}", data={"otp": "123456"}, follow_redirects=True)
            self._assert(b"expired" in res.data, "Expired OTP correctly rejected")
            self.client.post("/register", data={"name": "OTP Edge", "email": email, "password": "Password123", "confirm_password": "Password123"})
            for i in range(5):
                self.client.post(f"/verify-otp?email={email}", data={"otp": "999999"})
            res = self.client.post(f"/verify-otp?email={email}", data={"otp": "999999"}, follow_redirects=True)
            self._assert(b"Too many" in res.data or email not in pending_registrations, "Max OTP attempts invalidates registration")
            self.client.post("/register", data={"name": "Resend", "email": email, "password": "Password123", "confirm_password": "Password123"})
            pending_registrations[email]["attempts"] = 3
            res = self.client.get(f"/resend-otp?email={email}", follow_redirects=True)
            self._assert(b"new verification code" in res.data, "Resend OTP sends new code")
            self._assert(pending_registrations[email]["attempts"] == 0, "Resend resets attempt counter")
            res = self.client.get("/verify-otp?email=nonexistent@test.com", follow_redirects=True)
            self._assert(b"expired or invalid" in res.data, "Invalid email redirects with error")
            res = self.client.get("/resend-otp?email=nonexistent@test.com", follow_redirects=True)
            self._assert(b"expired or invalid" in res.data, "Resend with invalid email handled")
            pending_registrations.pop(email, None)

    def test_05_login_logout(self):
        self.section = "5. Login & Logout"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_login_{self.ts_suffix}@test.com"
        uid = self._create_user("Login User", email)
        res = self.client.post("/login", data={"email": email, "password": "WrongPass123"})
        self._assert(b"Invalid email or password" in res.data, "Wrong password rejected")
        res = self.client.post("/login", data={"email": "nobody@test.com", "password": "Password123"})
        self._assert(b"Invalid email or password" in res.data, "Non-existent email rejected")
        res = self._login(email)
        self._assert(b"Welcome back, Login User!" in res.data, "Successful login shows welcome")
        res = self.client.get("/login")
        self._assert(res.status_code == 302, "Logged-in user redirected from login page")
        with self.client.session_transaction() as sess:
            self._assert(sess.get("user_id") == uid, "Session has correct user_id")
            self._assert(sess.get("user_name") == "Login User", "Session has correct user_name")
            self._assert(sess.get("user_email") == email, "Session has correct user_email")
        res = self._logout()
        self._assert(b"logged out" in res.data, "Logout shows confirmation")
        res = self.client.get("/dashboard", follow_redirects=True)
        self._assert(b"Please log in" in res.data, "Post-logout access redirects to login")

    def test_06_forgot_and_reset_password(self):
        self.section = "6. Forgot & Reset Password"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_reset_{self.ts_suffix}@test.com"
        uid = self._create_user("Reset User", email)
        with patch("app.send_password_reset_otp_email") as mock_send:
            mock_send.return_value = True
            res = self.client.post("/forgot-password", data={"email": email}, follow_redirects=True)
            self._assert(b"password reset code has been sent" in res.data, "Reset request accepted")
            with self.client.session_transaction() as sess:
                token = sess.get("password_reset_token")
            self._assert(token is not None, "Reset token in session")
            res = self.client.post("/verify-reset-otp", data={"otp": "000000"})
            self._assert(b"Incorrect code" in res.data, "Wrong reset OTP rejected")
            actual_otp = mock_send.call_args[0][1]
            res = self.client.post("/verify-reset-otp", data={"otp": actual_otp}, follow_redirects=True)
            self._assert(b"Code verified" in res.data, "Correct reset OTP accepted")
            res = self.client.post("/reset-password", data={"password": "short", "confirm_password": "short"})
            self._assert(b"at least 8 characters" in res.data, "Reset rejects short password")
            res = self.client.post("/reset-password", data={"password": "NewPass456", "confirm_password": "Diff789"})
            self._assert(b"do not match" in res.data, "Reset rejects mismatched passwords")
            res = self.client.post("/reset-password", data={"password": "NewPass456", "confirm_password": "NewPass456"}, follow_redirects=True)
            self._assert(b"password has been reset" in res.data, "Password reset successful")
            res = self._login(email, "NewPass456")
            self._assert(b"Welcome back" in res.data, "Login with new password works")
            self._logout()
            res = self.client.post("/login", data={"email": email, "password": "Password123"})
            self._assert(b"Invalid email or password" in res.data, "Old password no longer works")
        with patch("app.send_password_reset_otp_email") as mock_send:
            mock_send.return_value = True
            res = self.client.post("/forgot-password", data={"email": "ghost@test.com"}, follow_redirects=True)
            self._assert(b"password reset code has been sent" in res.data, "Non-existent email gets same message (no info leak)")
            self._assert(not mock_send.called, "No email sent for non-existent account")
        res = self.client.get("/reset-password", follow_redirects=True)
        self._assert(res.status_code == 200, "Reset page without token handles gracefully")
        res = self.client.get("/verify-reset-otp", follow_redirects=True)
        self._assert(res.status_code == 200, "Verify-reset without token handles gracefully")

    def test_07_dashboard_empty_state(self):
        self.section = "7. Dashboard (Empty State)"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_dash_empty_{self.ts_suffix}@test.com"
        self._create_user("Empty Dashboard", email)
        self._login(email)
        res = self.client.get("/dashboard")
        self._assert(res.status_code == 200, "Dashboard loads for new user")
        self._assert(b"Good to see you, Empty Dashboard" in res.data, "Dashboard shows user name")
        self._assert(b"Not set" in res.data, "Dashboard shows 'Not set' for budget")
        self._assert(b"Welcome to Financial Insights!" in res.data, "Empty insights message shown")
        self._assert("₹".encode() in res.data or b"&#8377;" in res.data, "Rupee symbol present")
        self._logout()

    def test_08_expense_crud(self):
        self.section = "8. Expense CRUD Operations"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_crud_{self.ts_suffix}@test.com"
        uid = self._create_user("CRUD User", email)
        self._login(email)
        res = self.client.get("/expenses/add")
        self._assert(res.status_code == 200, "Add expense form renders")
        for cat in CATEGORIES:
            self._assert(cat.encode() in res.data, f"Category '{cat}' in form")
        for pm in PAYMENT_METHODS:
            self._assert(pm.encode() in res.data, f"Payment method '{pm}' in form")
        res = self._add_expense(250.50, "Food", "UPI", "Lunch with team")
        self._assert(b"Expense added successfully" in res.data, "Valid expense added")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expenses WHERE user_id = %s ORDER BY id DESC LIMIT 1", (uid,))
        exp = cursor.fetchone()
        cursor.close()
        self._assert(exp is not None, "Expense exists in database")
        if exp:
            self._assert(Decimal(str(exp["amount"])) == Decimal("250.50"), "Amount stored correctly")
            self._assert(exp["category"] == "Food", "Category stored correctly")
            expense_id = exp["id"]
            res = self.client.get(f"/expenses/{expense_id}/edit")
            self._assert(res.status_code == 200, "Edit form renders for own expense")
            res = self.client.post(f"/expenses/{expense_id}/edit", data={
                "amount": "300.00", "category": "Shopping", "expense_date": date.today().isoformat(),
                "payment_method": "Credit Card", "description": "Updated"
            }, follow_redirects=True)
            self._assert(b"Expense updated successfully" in res.data, "Expense updated")
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
            updated = cursor.fetchone()
            cursor.close()
            self._assert(Decimal(str(updated["amount"])) == Decimal("300.00"), "Updated amount correct")
            res = self.client.post(f"/expenses/{expense_id}/delete", follow_redirects=True)
            self._assert(b"Expense deleted successfully" in res.data, "Expense deleted")
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
            self._assert(cursor.fetchone() is None, "Expense removed from DB")
            cursor.close()
        res = self.client.post("/expenses/99999999/delete", follow_redirects=True)
        self._assert(b"Expense not found" in res.data, "Deleting non-existent expense handled")
        res = self.client.get("/expenses/99999999/edit", follow_redirects=True)
        self._assert(b"Expense not found" in res.data, "Editing non-existent expense handled")
        self._logout()

    def test_09_expense_validation(self):
        self.section = "9. Expense Form Validation"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_val_{self.ts_suffix}@test.com"
        self._create_user("Val User", email)
        self._login(email)
        res = self._add_expense(-50)
        self._assert(b"greater than zero" in res.data, "Negative amount rejected")
        res = self._add_expense(0)
        self._assert(b"greater than zero" in res.data, "Zero amount rejected")
        res = self._add_expense(10.555)
        self._assert(b"at most two decimal" in res.data, "3+ decimal places rejected")
        res = self.client.post("/expenses/add", data={"amount": "100", "category": "InvalidCat", "expense_date": date.today().isoformat(), "payment_method": "Cash", "description": "T"})
        self._assert(b"valid category" in res.data, "Invalid category rejected")
        res = self.client.post("/expenses/add", data={"amount": "100", "category": "Food", "expense_date": date.today().isoformat(), "payment_method": "Bitcoin", "description": "T"})
        self._assert(b"valid payment method" in res.data, "Invalid payment method rejected")
        res = self.client.post("/expenses/add", data={"amount": "100", "category": "Food", "expense_date": "not-a-date", "payment_method": "Cash", "description": "T"})
        self._assert(b"valid expense date" in res.data, "Invalid date rejected")
        res = self.client.post("/expenses/add", data={"amount": "", "category": "Food", "expense_date": date.today().isoformat(), "payment_method": "Cash", "description": "T"})
        self._assert(b"valid amount" in res.data, "Empty amount rejected")
        res = self.client.post("/expenses/add", data={"amount": "abc", "category": "Food", "expense_date": date.today().isoformat(), "payment_method": "Cash", "description": "T"})
        self._assert(b"valid amount" in res.data, "Non-numeric amount rejected")
        res = self.client.post("/expenses/add", data={"amount": "100", "category": "Food", "expense_date": date.today().isoformat(), "payment_method": "Cash", "description": "A" * 256})
        self._assert(b"255 characters" in res.data, "Long description rejected")
        res = self._add_expense(50, desc="B" * 255)
        self._assert(b"Expense added successfully" in res.data, "255-char description accepted")
        res = self._add_expense(75, desc="")
        self._assert(b"Expense added successfully" in res.data, "Empty description accepted")
        res = self._add_expense(0.01)
        self._assert(b"Expense added successfully" in res.data, "0.01 amount accepted")
        self._logout()

    def test_10_search_filter_pagination(self):
        self.section = "10. Search, Filters & Pagination"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_filter_{self.ts_suffix}@test.com"
        uid = self._create_user("Filter User", email)
        self._login(email)
        today = date.today()
        yesterday = today - timedelta(days=1)
        cursor = db.cursor()
        test_data = [
            (uid, 100, "Food", today, "UPI", "Morning coffee"),
            (uid, 250, "Food", today, "Cash", "Lunch at restaurant"),
            (uid, 500, "Transportation", today, "UPI", "Uber ride"),
            (uid, 1200, "Shopping", today, "Credit Card", "New headphones"),
            (uid, 3000, "Bills", today, "Bank Transfer", "Electricity bill"),
            (uid, 150, "Entertainment", today, "Debit Card", "Movie tickets"),
            (uid, 800, "Health", today, "UPI", "Doctor visit"),
            (uid, 450, "Education", today, "Cash", "Book purchase"),
            (uid, 5000, "Travel", today, "Credit Card", "Flight booking"),
            (uid, 200, "Groceries", today, "UPI", "Weekly groceries"),
            (uid, 8000, "Rent", yesterday, "Bank Transfer", "Monthly rent"),
            (uid, 350, "Other", yesterday, "Cash", "Miscellaneous item"),
        ]
        for d in test_data:
            cursor.execute("INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES (%s, %s, %s, %s, %s, %s)", d)
        db.commit()
        cursor.close()
        res = self.client.get("/expenses?page=1")
        self._assert(b"Page 1 of 2" in res.data, "Page 1 pagination correct")
        res = self.client.get("/expenses?page=2")
        self._assert(b"Page 2 of 2" in res.data, "Page 2 pagination correct")
        res = self.client.get("/expenses?page=999")
        self._assert(res.status_code == 302, "Page beyond max redirects")
        res = self.client.get("/expenses?category=Food")
        self._assert(b"Morning coffee" in res.data, "Category filter shows Food items")
        self._assert(b"Uber ride" not in res.data, "Category filter excludes non-Food")
        res = self.client.get("/expenses?payment_method=UPI")
        self._assert(b"Morning coffee" in res.data, "Payment filter shows UPI items")
        res = self.client.get("/expenses?search=headphones")
        self._assert(b"New headphones" in res.data, "Search finds 'headphones'")
        self._assert(b"Morning coffee" not in res.data, "Search excludes non-matching")
        res = self.client.get(f"/expenses?date_from={today.isoformat()}&date_to={today.isoformat()}")
        self._assert(b"Monthly rent" not in res.data, "Date filter excludes yesterday's items")
        res = self.client.get("/expenses?min_amount=1000")
        self._assert(b"Morning coffee" not in res.data, "Min amount excludes <1000")
        res = self.client.get("/expenses?max_amount=200")
        self._assert(b"Morning coffee" in res.data, "Max amount includes <=200")
        self._assert(b"New headphones" not in res.data, "Max amount excludes >200")
        res = self.client.get("/expenses?sort=highest")
        self._assert(res.status_code == 200, "Sort by highest loads")
        res = self.client.get("/expenses?sort=lowest")
        self._assert(res.status_code == 200, "Sort by lowest loads")
        res = self.client.get("/expenses?date_from=invalid-date")
        self._assert(res.status_code == 200, "Invalid date filter handled gracefully")
        res = self.client.get("/expenses?min_amount=abc")
        self._assert(res.status_code == 200, "Invalid min_amount handled gracefully")
        self._logout()

    def test_11_csv_export(self):
        self.section = "11. CSV Export"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_export_{self.ts_suffix}@test.com"
        uid = self._create_user("Export User", email)
        self._login(email)
        cursor = db.cursor()
        cursor.execute("INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES (%s, 150.00, 'Food', %s, 'UPI', 'Test food'), (%s, 2500.50, 'Bills', %s, 'Credit Card', 'Test bill')", (uid, date.today(), uid, date.today()))
        db.commit()
        cursor.close()
        res = self.client.get("/expenses/export")
        self._assert(res.status_code == 200, "Export returns 200")
        self._assert(res.content_type.startswith("text/csv"), "Content type is text/csv")
        self._assert("attachment" in res.headers.get("Content-Disposition", ""), "Has attachment header")
        csv_text = res.data.decode("utf-8")
        lines = [l.strip() for l in csv_text.strip().splitlines()]
        self._assert(lines[0] == "Date,Category,Payment Method,Description,Amount", "CSV header correct")
        self._assert(len(lines) == 3, "CSV has header + 2 data rows")
        res = self.client.get("/expenses/export?category=Food")
        csv_text = res.data.decode("utf-8")
        self._assert("Test food" in csv_text, "Filtered export includes matching")
        self._assert("Test bill" not in csv_text, "Filtered export excludes non-matching")
        self._logout()

    def test_12_user_isolation(self):
        self.section = "12. User Data Isolation"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email_a = f"e2e_iso_a_{self.ts_suffix}@test.com"
        email_b = f"e2e_iso_b_{self.ts_suffix}@test.com"
        uid_a = self._create_user("User A", email_a)
        uid_b = self._create_user("User B", email_b)
        self._login(email_a)
        self._add_expense(999.99, desc="User A Secret")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id FROM expenses WHERE user_id = %s ORDER BY id DESC LIMIT 1", (uid_a,))
        exp_a = cursor.fetchone()
        cursor.close()
        self._logout()
        self._login(email_b)
        res = self.client.get("/expenses")
        self._assert(b"User A Secret" not in res.data, "User B cannot see User A's expenses")
        if exp_a:
            res = self.client.get(f"/expenses/{exp_a['id']}/edit", follow_redirects=True)
            self._assert(b"Expense not found" in res.data, "User B cannot edit User A's expense")
            res = self.client.post(f"/expenses/{exp_a['id']}/delete", follow_redirects=True)
            self._assert(b"Expense not found" in res.data, "User B cannot delete User A's expense")
        res = self.client.get("/expenses/export")
        self._assert("User A Secret" not in res.data.decode("utf-8"), "User B export doesn't leak User A data")
        self._logout()

    def test_13_budget(self):
        self.section = "13. Budget Management"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_budget_{self.ts_suffix}@test.com"
        uid = self._create_user("Budget User", email)
        self._login(email)
        res = self.client.get("/budget")
        self._assert(res.status_code == 200, "Budget page loads")
        res = self.client.post("/budget", data={"budget_amount": "0"}, follow_redirects=True)
        self._assert(b"valid monthly budget" in res.data, "Zero budget rejected")
        res = self.client.post("/budget", data={"budget_amount": "-500"}, follow_redirects=True)
        self._assert(b"valid monthly budget" in res.data, "Negative budget rejected")
        res = self.client.post("/budget", data={"budget_amount": "abc"}, follow_redirects=True)
        self._assert(b"valid monthly budget" in res.data, "Non-numeric budget rejected")
        res = self.client.post("/budget", data={"budget_amount": "10000.00"}, follow_redirects=True)
        self._assert(b"Monthly budget saved" in res.data, "Valid budget saved")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT budget_amount FROM budgets WHERE user_id = %s AND month = %s AND year = %s", (uid, date.today().month, date.today().year))
        bud = cursor.fetchone()
        cursor.close()
        self._assert(bud is not None and Decimal(str(bud["budget_amount"])) == Decimal("10000.00"), "Budget in DB correct")
        res = self.client.post("/budget", data={"budget_amount": "15000.00"}, follow_redirects=True)
        self._assert(b"Monthly budget saved" in res.data, "Budget update works")
        self._logout()

    def test_14_dashboard_with_data(self):
        self.section = "14. Dashboard with Data"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_dashdata_{self.ts_suffix}@test.com"
        uid = self._create_user("Dash Data User", email)
        self._login(email)
        today = date.today()
        prev_month = (today.replace(day=1) - timedelta(days=5)).replace(day=15)
        cursor = db.cursor()
        cursor.execute("INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES (%s, 5000.00, 'Food', %s, 'Cash', 'Prev month'), (%s, 3000.00, 'Shopping', %s, 'UPI', 'Current'), (%s, 1500.00, 'Food', %s, 'Cash', 'Today food')", (uid, prev_month, uid, today, uid, today))
        db.commit()
        cursor.close()
        res = self.client.get("/dashboard")
        self._assert(res.status_code == 200, "Dashboard loads with data")
        self._assert(b"Monthly Trend" in res.data, "Monthly trend insight present")
        self._assert(b"less than last month" in res.data, "Shows spending decrease vs previous month")
        self._assert(b"Spending by Category" in res.data, "Category breakdown present")
        self._assert(b"Recent Expenses" in res.data, "Recent expenses section present")
        self._logout()

    def test_15_reports(self):
        self.section = "15. Reports & Analytics"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_reports_{self.ts_suffix}@test.com"
        uid = self._create_user("Report User", email)
        self._login(email)
        today = date.today()
        cursor = db.cursor()
        cursor.execute("INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES (%s, 500, 'Food', %s, 'Cash', 'Report food'), (%s, 1500, 'Bills', %s, 'UPI', 'Report bill')", (uid, today, uid, today))
        db.commit()
        cursor.close()
        res = self.client.get("/reports?period=current")
        self._assert(res.status_code == 200, "Reports loads (current)")
        self._assert(b"TOTAL SPENT" in res.data, "Total spent present")
        self._assert(b"Category spending" in res.data, "Category chart present")
        self._assert(b"Daily spending" in res.data, "Daily chart present")
        self._assert(b"Monthly spending" in res.data, "Monthly chart present")
        res = self.client.get("/reports?period=previous")
        self._assert(res.status_code == 200, "Reports loads (previous)")
        res = self.client.get(f"/reports?period=custom&date_from={today.isoformat()}&date_to={today.isoformat()}")
        self._assert(res.status_code == 200, "Reports loads (custom)")
        res = self.client.get(f"/reports?period=custom&date_from={today.isoformat()}&date_to={(today - timedelta(days=5)).isoformat()}", follow_redirects=True)
        self._assert(b"valid custom date range" in res.data, "Invalid date range rejected")
        res = self.client.get("/reports?period=custom&date_from=&date_to=", follow_redirects=True)
        self._assert(b"valid custom date range" in res.data, "Missing custom dates rejected")
        self._logout()

    def test_16_notifications(self):
        self.section = "16. Notifications System"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_notif_{self.ts_suffix}@test.com"
        uid = self._create_user("Notif User", email)
        self._login(email)
        today = date.today()
        cursor = db.cursor()
        cursor.execute("INSERT INTO budgets (user_id, month, year, budget_amount) VALUES (%s, %s, %s, 10000.00)", (uid, today.month, today.year))
        cursor.execute("INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES (%s, 8500.00, 'Shopping', %s, 'Credit Card', 'Laptop')", (uid, today))
        db.commit()
        cursor.close()
        res = self.client.get("/dashboard")
        self._assert(b"Budget Alert" in res.data, "Budget alert notification generated")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM notifications WHERE user_id = %s", (uid,))
        notifs = cursor.fetchall()
        cursor.close()
        notif_types = [n["type"] for n in notifs]
        self._assert("budget_80" in notif_types or "budget_90" in notif_types, "Budget alert in DB")
        if notifs:
            nid = notifs[0]["id"]
            self.client.post(f"/notifications/{nid}/read")
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT is_read FROM notifications WHERE id = %s", (nid,))
            self._assert(cursor.fetchone()["is_read"], "Notification marked read")
            cursor.close()
            self.client.post("/notifications/read-all")
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS c FROM notifications WHERE user_id = %s AND is_read = FALSE", (uid,))
            self._assert(cursor.fetchone()["c"] == 0, "All notifications marked read")
            cursor.close()
            self.client.post(f"/notifications/{nid}/dismiss")
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT * FROM notifications WHERE id = %s", (nid,))
            self._assert(cursor.fetchone() is None, "Notification dismissed/deleted")
            cursor.close()
        self._logout()

    def test_17_notification_isolation(self):
        self.section = "17. Notification Isolation"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email_a = f"e2e_niso_a_{self.ts_suffix}@test.com"
        email_b = f"e2e_niso_b_{self.ts_suffix}@test.com"
        uid_a = self._create_user("Notif A", email_a)
        uid_b = self._create_user("Notif B", email_b)
        cursor = db.cursor()
        cursor.execute("INSERT INTO notifications (user_id, type, title, message) VALUES (%s, 'test', 'User A Alert', 'Private')", (uid_a,))
        nid = cursor.lastrowid
        db.commit()
        cursor.close()
        self._login(email_b)
        self.client.post(f"/notifications/{nid}/dismiss")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM notifications WHERE id = %s", (nid,))
        self._assert(cursor.fetchone() is not None, "User B cannot dismiss User A notification")
        cursor.close()
        self.client.post(f"/notifications/{nid}/read")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT is_read FROM notifications WHERE id = %s", (nid,))
        self._assert(not cursor.fetchone()["is_read"], "User B cannot mark User A notification read")
        cursor.close()
        self._logout()

    def test_18_profile(self):
        self.section = "18. Profile Management"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_profile_{self.ts_suffix}@test.com"
        self._create_user("Original Name", email)
        self._login(email)
        res = self.client.get("/profile")
        self._assert(res.status_code == 200, "Profile page loads")
        self._assert(b"Original Name" in res.data, "Profile shows current name")
        res = self.client.post("/profile", data={"action": "name", "name": "Updated Name"}, follow_redirects=True)
        self._assert(b"Profile updated" in res.data, "Name update accepted")
        with self.client.session_transaction() as sess:
            self._assert(sess.get("user_name") == "Updated Name", "Session name updated")
        res = self.client.post("/profile", data={"action": "name", "name": "A"}, follow_redirects=True)
        self._assert(b"between 2 and 120" in res.data, "Too-short name rejected")
        res = self.client.post("/profile", data={"action": "name", "name": "X" * 121}, follow_redirects=True)
        self._assert(b"between 2 and 120" in res.data, "Too-long name rejected")
        res = self.client.post("/profile", data={"action": "password", "current_password": "Wrong123", "new_password": "NewPass123", "confirm_password": "NewPass123"}, follow_redirects=True)
        self._assert(b"current password is incorrect" in res.data, "Wrong current password rejected")
        res = self.client.post("/profile", data={"action": "password", "current_password": "Password123", "new_password": "weak", "confirm_password": "weak"}, follow_redirects=True)
        self._assert(b"8 characters" in res.data, "Weak new password rejected")
        res = self.client.post("/profile", data={"action": "password", "current_password": "Password123", "new_password": "NewPass123", "confirm_password": "Diff456"}, follow_redirects=True)
        self._assert(b"do not match" in res.data, "Mismatched new passwords rejected")
        res = self.client.post("/profile", data={"action": "password", "current_password": "Password123", "new_password": "BrandNew789", "confirm_password": "BrandNew789"}, follow_redirects=True)
        self._assert(b"Password changed" in res.data, "Password change successful")
        self._logout()
        res = self._login(email, "BrandNew789")
        self._assert(b"Welcome back" in res.data, "Login with new password works")
        self._logout()

    def test_19_security_headers(self):
        self.section = "19. Security Headers"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        res = self.client.get("/")
        self._assert(res.headers.get("X-Content-Type-Options") == "nosniff", "X-Content-Type-Options: nosniff")
        self._assert(res.headers.get("X-Frame-Options") == "SAMEORIGIN", "X-Frame-Options: SAMEORIGIN")
        self._assert(res.headers.get("X-XSS-Protection") == "1; mode=block", "X-XSS-Protection set")
        self._assert(res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin", "Referrer-Policy set")

    def test_20_csrf_protection(self):
        self.section = "20. CSRF Protection"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_csrf_{self.ts_suffix}@test.com"
        self._create_user("CSRF User", email)
        flask_app.config["WTF_CSRF_ENABLED"] = True
        try:
            res = self.client.post("/login", data={"email": email, "password": "Password123"})
            self._assert(res.status_code == 400, "POST without CSRF token returns 400")
            self._assert(b"CSRF" in res.data, "CSRF error message shown")
            self.client.get("/login")
            with self.client.session_transaction() as sess:
                csrf = sess.get("csrf_token")
            self._assert(csrf is not None, "CSRF token generated")
            self._assert(len(csrf) == 64, "CSRF token is 64-char hex")
            res = self.client.post("/login", data={"email": email, "password": "Password123", "csrf_token": csrf}, follow_redirects=True)
            self._assert(res.status_code == 200 and b"Dashboard" in res.data, "Login succeeds with valid CSRF")
            self._logout()
        finally:
            flask_app.config["WTF_CSRF_ENABLED"] = False

    def test_21_xss_handling(self):
        self.section = "21. XSS & Special Characters"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_xss_{self.ts_suffix}@test.com"
        self._create_user("XSS User", email)
        self._login(email)
        xss_payload = '<script>alert("xss")</script>'
        res = self._add_expense(100, desc=xss_payload)
        self._assert(b"Expense added" in res.data, "Expense with special chars accepted")
        res = self.client.get("/expenses")
        self._assert(b'<script>alert("xss")</script>' not in res.data, "Script tags escaped in output")
        self._assert(b"&lt;script&gt;" in res.data, "Script tags HTML-escaped")
        res = self.client.get('/expenses?search=<script>alert(1)</script>')
        self._assert(res.status_code == 200, "XSS in search param doesn't crash")
        unicode_desc = "Café ☕ — 日本語"
        res = self._add_expense(50, desc=unicode_desc)
        self._assert(b"Expense added" in res.data, "Unicode description accepted")
        self._logout()

    def test_22_sql_injection(self):
        self.section = "22. SQL Injection Protection"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_sqli_{self.ts_suffix}@test.com"
        uid = self._create_user("SQL User", email)
        self._login(email)
        for payload in ["'; DROP TABLE users; --", "1' OR '1'='1", "\" UNION SELECT * FROM users --"]:
            res = self.client.get(f"/expenses?search={payload}")
            self._assert(res.status_code == 200, f"SQLi search '{payload[:30]}...' handled safely")
        res = self._add_expense(100, desc="'; DROP TABLE expenses; --")
        self._assert(b"Expense added" in res.data, "SQLi in description handled safely")
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE id = %s", (uid,))
        self._assert(cursor.fetchone()[0] == 1, "Users table intact after SQLi")
        cursor.close()
        self._logout()

    def test_23_budget_status_transitions(self):
        self.section = "23. Budget Status Transitions"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_bstatus_{self.ts_suffix}@test.com"
        uid = self._create_user("Budget Status User", email)
        self._login(email)
        today = date.today()
        cursor = db.cursor()
        cursor.execute("INSERT INTO budgets (user_id, month, year, budget_amount) VALUES (%s, %s, %s, 10000.00)", (uid, today.month, today.year))
        db.commit()
        cursor.close()
        self._add_expense(4000, desc="Normal spend")
        res = self.client.get("/dashboard")
        self._assert(b"Safe and on track" in res.data or b"On Track" in res.data, "Budget < 80% shows On Track")
        self._add_expense(4500, desc="Warning spend")
        res = self.client.get("/dashboard")
        self._assert(b"approaching your limit" in res.data, "Budget >= 80% shows warning")
        self._add_expense(2000, desc="Over spend")
        res = self.client.get("/dashboard")
        self._assert(b"exceeded" in res.data, "Budget > 100% shows exceeded")
        self._logout()

    def test_24_session_edge_cases(self):
        self.section = "24. Session Edge Cases"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_session_{self.ts_suffix}@test.com"
        self._create_user("Session User", email)
        self._login(email)
        with self.client.session_transaction() as sess:
            self._assert(sess.permanent is True, "Session is marked permanent")
        self._logout()

    def test_25_inr_filter(self):
        self.section = "25. INR Currency Formatting"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_inr_{self.ts_suffix}@test.com"
        self._create_user("INR User", email)
        self._login(email)
        self._add_expense(1234567.89, desc="Large INR")
        res = self.client.get("/dashboard")
        self._assert("₹1,234,567.89".encode() in res.data, "INR formatting with commas", "Check manually if format differs")
        self._logout()

    def test_26_empty_states(self):
        self.section = "26. Empty States"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        email = f"e2e_empty_{self.ts_suffix}@test.com"
        self._create_user("Empty User", email)
        self._login(email)
        res = self.client.get("/expenses")
        self._assert(b"No expenses found" in res.data, "Empty expenses state")
        res = self.client.get("/dashboard")
        self._assert(b"Start your financial story" in res.data or b"No category data" in res.data, "Empty dashboard state")
        res = self.client.get("/reports")
        self._assert(res.status_code == 200, "Empty reports loads")
        res = self.client.get("/budget")
        self._assert(res.status_code == 200, "Empty budget loads")
        self._logout()

    def test_27_http_methods(self):
        self.section = "27. HTTP Method Validation"
        print(f"\n{'='*60}\n  {self.section}\n{'='*60}")
        res = self.client.get("/logout")
        self._assert(res.status_code == 405, "GET /logout returns 405")
        res = self.client.get("/expenses/1/delete")
        self._assert(res.status_code == 405, "GET /expenses/1/delete returns 405")
        res = self.client.get("/notifications/1/read")
        self._assert(res.status_code == 405, "GET notification/read returns 405")
        res = self.client.get("/notifications/read-all")
        self._assert(res.status_code == 405, "GET notification/read-all returns 405")
        res = self.client.get("/notifications/1/dismiss")
        self._assert(res.status_code == 405, "GET notification/dismiss returns 405")

    def run_all(self):
        print("=" * 60)
        print("  COMPREHENSIVE E2E TEST SUITE")
        print("  DailyExpenseTracker - ExpenseFlow")
        print("=" * 60)
        tests = [
            self.test_01_public_pages, self.test_02_protected_routes_redirect,
            self.test_03_registration_flow, self.test_04_otp_edge_cases,
            self.test_05_login_logout, self.test_06_forgot_and_reset_password,
            self.test_07_dashboard_empty_state, self.test_08_expense_crud,
            self.test_09_expense_validation, self.test_10_search_filter_pagination,
            self.test_11_csv_export, self.test_12_user_isolation,
            self.test_13_budget, self.test_14_dashboard_with_data,
            self.test_15_reports, self.test_16_notifications,
            self.test_17_notification_isolation, self.test_18_profile,
            self.test_19_security_headers, self.test_20_csrf_protection,
            self.test_21_xss_handling, self.test_22_sql_injection,
            self.test_23_budget_status_transitions, self.test_24_session_edge_cases,
            self.test_25_inr_filter, self.test_26_empty_states,
            self.test_27_http_methods,
        ]
        for test_fn in tests:
            try:
                test_fn()
            except Exception as e:
                self._record(f"EXCEPTION in {test_fn.__name__}", "FAIL", f"{type(e).__name__}: {e}")
                traceback.print_exc()
        self.cleanup()
        print(f"\n{'='*60}")
        print(f"  FINAL RESULTS")
        print(f"{'='*60}")
        total = self.pass_count + self.fail_count + self.warn_count
        print(f"  Total:  {total}")
        print(f"  PASS: {self.pass_count}")
        print(f"  FAIL: {self.fail_count}")
        print(f"  WARN: {self.warn_count}")
        print(f"{'='*60}")
        report = {"summary": {"total": total, "pass": self.pass_count, "fail": self.fail_count, "warn": self.warn_count}, "results": self.results}
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "e2e_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n  Report saved to: {report_path}")
        return report


if __name__ == "__main__":
    runner = E2ETestRunner()
    report = runner.run_all()
    sys.exit(1 if report["summary"]["fail"] > 0 else 0)
