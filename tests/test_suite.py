import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import re
from unittest.mock import patch

import app
from app import (
    app as flask_app,
    db,
    pending_registrations,
    password_reset_requests,
    REGISTRATION_OTP_EXPIRY_MINUTES,
    REGISTRATION_OTP_MAX_ATTEMPTS,
    RESET_OTP_EXPIRY_MINUTES,
    RESET_OTP_MAX_ATTEMPTS,
)
from werkzeug.security import generate_password_hash, check_password_hash

class ExpenseFlowTestSuite(unittest.TestCase):
    def setUp(self):
        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False
        self.client = flask_app.test_client()
        pending_registrations.clear()
        password_reset_requests.clear()
        
        self.test_email_1 = f"test_user1_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@example.com"
        self.test_email_2 = f"test_user2_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@example.com"
        self.test_password = "Password123"
        self.created_user_ids = []

    def tearDown(self):
        if self.created_user_ids:
            cursor = db.cursor()
            format_strings = ','.join(['%s'] * len(self.created_user_ids))
            cursor.execute(f"DELETE FROM users WHERE id IN ({format_strings})", tuple(self.created_user_ids))
            db.commit()
            cursor.close()

    def create_user_direct(self, name, email, password):
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email.lower(), generate_password_hash(password))
        )
        db.commit()
        user_id = cursor.lastrowid
        cursor.close()
        self.created_user_ids.append(user_id)
        return user_id

    # -------------------------------------------------------------
    # 1. AUTHENTICATION & REGISTRATION OTP TESTS
    # -------------------------------------------------------------
    @patch("app.send_otp_email")
    def test_registration_flow_and_otp_verification(self, mock_send):
        mock_send.return_value = True

        # Test validation failures
        res = self.client.post("/register", data={
            "name": "Test User",
            "email": self.test_email_1,
            "password": "short",
            "confirm_password": "short"
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Password must be at least 8 characters", res.data)

        # Successful registration initiation
        res = self.client.post("/register", data={
            "name": "Test User",
            "email": self.test_email_1,
            "password": self.test_password,
            "confirm_password": self.test_password
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(self.test_email_1, pending_registrations)
        reg_state = pending_registrations[self.test_email_1]
        self.assertEqual(reg_state["name"], "Test User")
        self.assertEqual(len(reg_state["otp"]), 6)
        self.assertEqual(reg_state["attempts"], 0)
        mock_send.assert_called_once()

        # OTP Verification: Wrong OTP (attempt 1)
        res = self.client.post(f"/verify-otp?email={self.test_email_1}", data={"otp": "000000"})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Incorrect OTP. 4 attempt(s) remaining.", res.data)
        self.assertEqual(pending_registrations[self.test_email_1]["attempts"], 1)

        # OTP Verification: Correct OTP
        valid_otp = pending_registrations[self.test_email_1]["otp"]
        res = self.client.post(f"/verify-otp?email={self.test_email_1}", data={"otp": valid_otp}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Account created successfully", res.data)
        self.assertNotIn(self.test_email_1, pending_registrations)

        # Confirm user in DB
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, name, email FROM users WHERE email = %s", (self.test_email_1,))
        user = cursor.fetchone()
        cursor.close()
        self.assertIsNotNone(user)
        self.created_user_ids.append(user["id"])

    @patch("app.send_otp_email")
    def test_registration_otp_expiration(self, mock_send):
        mock_send.return_value = True
        self.client.post("/register", data={
            "name": "Expired User",
            "email": self.test_email_1,
            "password": self.test_password,
            "confirm_password": self.test_password
        })
        self.assertIn(self.test_email_1, pending_registrations)

        # Simulate expiration by setting expires_at to the past
        pending_registrations[self.test_email_1]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=10)
        valid_otp = pending_registrations[self.test_email_1]["otp"]

        res = self.client.post(f"/verify-otp?email={self.test_email_1}", data={"otp": valid_otp}, follow_redirects=True)
        self.assertIn(b"Your verification code has expired", res.data)
        self.assertNotIn(self.test_email_1, pending_registrations)

    @patch("app.send_otp_email")
    def test_registration_otp_attempt_limits(self, mock_send):
        mock_send.return_value = True
        self.client.post("/register", data={
            "name": "Limit User",
            "email": self.test_email_1,
            "password": self.test_password,
            "confirm_password": self.test_password
        })

        for i in range(4):
            res = self.client.post(f"/verify-otp?email={self.test_email_1}", data={"otp": "999999"})
            self.assertEqual(res.status_code, 200)

        # 5th failed attempt should invalidate
        res = self.client.post(f"/verify-otp?email={self.test_email_1}", data={"otp": "999999"}, follow_redirects=True)
        self.assertIn(b"Too many incorrect codes", res.data)
        self.assertNotIn(self.test_email_1, pending_registrations)

    @patch("app.send_otp_email")
    def test_resend_registration_otp(self, mock_send):
        mock_send.return_value = True
        self.client.post("/register", data={
            "name": "Resend User",
            "email": self.test_email_1,
            "password": self.test_password,
            "confirm_password": self.test_password
        })
        initial_otp = pending_registrations[self.test_email_1]["otp"]
        pending_registrations[self.test_email_1]["attempts"] = 3

        res = self.client.get(f"/resend-otp?email={self.test_email_1}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"A new verification code has been sent", res.data)

        new_otp = pending_registrations[self.test_email_1]["otp"]
        self.assertEqual(pending_registrations[self.test_email_1]["attempts"], 0)
        self.assertEqual(len(new_otp), 6)

    # -------------------------------------------------------------
    # 2. LOGIN, SESSIONS, AND PROTECTED ROUTES
    # -------------------------------------------------------------
    def test_login_logout_and_protected_routes(self):
        user_id = self.create_user_direct("Login User", self.test_email_1, self.test_password)

        # Access protected route unauthenticated
        res = self.client.get("/dashboard", follow_redirects=True)
        self.assertIn(b"Please log in to access your dashboard", res.data)

        # Invalid login
        res = self.client.post("/login", data={"email": self.test_email_1, "password": "WrongPassword"})
        self.assertIn(b"Invalid email or password", res.data)

        # Valid login
        res = self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password}, follow_redirects=True)
        self.assertIn(b"Welcome back, Login User!", res.data)
        self.assertIn(b"Good to see you, Login User", res.data)

        # Access protected route authenticated
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)

        # Logout
        res = self.client.post("/logout", follow_redirects=True)
        self.assertIn(b"You have been logged out successfully", res.data)

        # Access protected route again after logout
        res = self.client.get("/dashboard", follow_redirects=True)
        self.assertIn(b"Please log in to access your dashboard", res.data)

    # -------------------------------------------------------------
    # 3. FORGOT PASSWORD AND RESET PASSWORD
    # -------------------------------------------------------------
    @patch("app.send_password_reset_otp_email")
    def test_forgot_and_reset_password_flow(self, mock_send):
        mock_send.return_value = True
        user_id = self.create_user_direct("Reset User", self.test_email_1, self.test_password)

        res = self.client.post("/forgot-password", data={"email": self.test_email_1}, follow_redirects=True)
        self.assertIn(b"a password reset code has been sent", res.data)
        mock_send.assert_called_once()

        with self.client.session_transaction() as sess:
            reset_token = sess.get("password_reset_token")
        self.assertIsNotNone(reset_token)
        self.assertIn(reset_token, password_reset_requests)

        # Test wrong OTP for reset
        res = self.client.post("/verify-reset-otp", data={"otp": "000000"})
        self.assertIn(b"Incorrect code. 4 attempt(s) remaining.", res.data)

        # We can extract the sent OTP from mock call arguments
        call_args = mock_send.call_args[0]
        actual_otp = call_args[1]

        # Verify correct OTP
        res = self.client.post("/verify-reset-otp", data={"otp": actual_otp}, follow_redirects=True)
        self.assertIn(b"Code verified. Please create your new password.", res.data)

        # Reset password
        new_pass = "NewPassword456"
        res = self.client.post("/reset-password", data={
            "password": new_pass,
            "confirm_password": new_pass
        }, follow_redirects=True)
        self.assertIn(b"Your password has been reset", res.data)

        # Verify login with new password
        res = self.client.post("/login", data={"email": self.test_email_1, "password": new_pass}, follow_redirects=True)
        self.assertIn(b"Welcome back", res.data)

    # -------------------------------------------------------------
    # 4. EXPENSE CRUD, SEARCH, FILTERS, PAGINATION, AND USER ISOLATION
    # -------------------------------------------------------------
    def test_expenses_crud_and_isolation(self):
        user_a = self.create_user_direct("User A", self.test_email_1, self.test_password)
        user_b = self.create_user_direct("User B", self.test_email_2, self.test_password)

        # Log in as User A
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        # Add Expense for User A
        res = self.client.post("/expenses/add", data={
            "amount": "450.50",
            "category": "Food",
            "expense_date": date.today().isoformat(),
            "payment_method": "UPI",
            "description": "Lunch with team"
        }, follow_redirects=True)
        self.assertIn(b"Expense added successfully", res.data)

        # Retrieve expense ID
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expenses WHERE user_id = %s", (user_a,))
        expense_a = cursor.fetchone()
        cursor.close()
        self.assertIsNotNone(expense_a)
        expense_id = expense_a["id"]
        self.assertEqual(Decimal(str(expense_a["amount"])), Decimal("450.50"))

        # Edit Expense
        res = self.client.post(f"/expenses/{expense_id}/edit", data={
            "amount": "500.00",
            "category": "Food",
            "expense_date": date.today().isoformat(),
            "payment_method": "Credit Card",
            "description": "Lunch updated"
        }, follow_redirects=True)
        self.assertIn(b"Expense updated successfully", res.data)

        # Verify update in DB
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expenses WHERE id = %s", (expense_id,))
        updated_a = cursor.fetchone()
        cursor.close()
        self.assertEqual(Decimal(str(updated_a["amount"])), Decimal("500.00"))
        self.assertEqual(updated_a["payment_method"], "Credit Card")

        # Log out User A, log in as User B
        self.client.post("/logout")
        self.client.post("/login", data={"email": self.test_email_2, "password": self.test_password})

        # User B should NOT see User A's expense
        res = self.client.get("/expenses")
        self.assertNotIn(b"Lunch updated", res.data)

        # User B cannot edit User A's expense
        res = self.client.get(f"/expenses/{expense_id}/edit", follow_redirects=True)
        self.assertIn(b"Expense not found", res.data)

        # User B cannot delete User A's expense
        res = self.client.post(f"/expenses/{expense_id}/delete", follow_redirects=True)
        self.assertIn(b"Expense not found", res.data)

        # Switch back to User A to delete
        self.client.post("/logout")
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})
        res = self.client.post(f"/expenses/{expense_id}/delete", follow_redirects=True)
        self.assertIn(b"Expense deleted successfully", res.data)

    def test_search_filters_and_pagination(self):
        user_id = self.create_user_direct("Filter User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        # Insert 15 expenses to test pagination
        cursor = db.cursor()
        today = date.today()
        for i in range(15):
            cat = "Food" if i % 2 == 0 else "Transportation"
            method = "UPI" if i % 3 == 0 else "Cash"
            cursor.execute(
                "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, (i + 1) * 10, cat, today, method, f"Item number {i}")
            )
        db.commit()
        cursor.close()

        # Page 1
        res = self.client.get("/expenses?page=1")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Page 1 of 2", res.data)

        # Page 2
        res = self.client.get("/expenses?page=2")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Page 2 of 2", res.data)

        # Search filter
        res = self.client.get("/expenses?search=number 14")
        self.assertIn(b"Item number 14", res.data)
        self.assertNotIn(b"Item number 13", res.data)

        # Category filter
        res = self.client.get("/expenses?category=Transportation")
        self.assertIn(b"Transportation", res.data)

        # Sorting: highest
        res = self.client.get("/expenses?sort=highest")
        self.assertEqual(res.status_code, 200)

    # -------------------------------------------------------------
    # 5. DASHBOARD AND BUDGET TESTS
    # -------------------------------------------------------------
    def test_dashboard_and_budget_lifecycle(self):
        user_id = self.create_user_direct("Budget User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        # Dashboard when empty
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Not set", res.data)

        # Set Budget (1000)
        res = self.client.post("/budget", data={"budget_amount": "1000.00"}, follow_redirects=True)
        self.assertIn(b"Monthly budget saved successfully", res.data)

        # Add an expense of 850 (triggers warning state >= 80%)
        self.client.post("/expenses/add", data={
            "amount": "850.00",
            "category": "Shopping",
            "expense_date": date.today().isoformat(),
            "payment_method": "Credit Card",
            "description": "New jacket"
        })

        res = self.client.get("/dashboard")
        self.assertIn(b"85% used", res.data)
        self.assertIn(b"warning", res.data)

        # Add another expense of 200 (total 1050, triggers over budget)
        self.client.post("/expenses/add", data={
            "amount": "200.00",
            "category": "Food",
            "expense_date": date.today().isoformat(),
            "payment_method": "Cash",
            "description": "Dinner"
        })

        res = self.client.get("/dashboard")
        self.assertIn(b"Budget exceeded", res.data)
        self.assertIn(b"over", res.data)

    # -------------------------------------------------------------
    # 6. REPORTS TESTS
    # -------------------------------------------------------------
    def test_reports_calculations(self):
        user_id = self.create_user_direct("Report User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        today = date.today()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (user_id, 300, "Bills", today, "Bank Transfer", "Electricity")
        )
        db.commit()
        cursor.close()

        # Current period
        res = self.client.get("/reports?period=current")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Bills", res.data)
        self.assertIn(b"Category spending", res.data)
        self.assertIn(b"TOTAL SPENT", res.data)

        # Previous period
        res = self.client.get("/reports?period=previous")
        self.assertEqual(res.status_code, 200)

        # Custom period
        res = self.client.get(f"/reports?period=custom&date_from={today.isoformat()}&date_to={today.isoformat()}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Bills", res.data)

    # -------------------------------------------------------------
    # 7. PROFILE TESTS
    # -------------------------------------------------------------
    def test_profile_update_and_password_change(self):
        user_id = self.create_user_direct("Initial Name", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        # Update Name
        res = self.client.post("/profile", data={"action": "name", "name": "Updated Name"}, follow_redirects=True)
        self.assertIn(b"Profile updated successfully", res.data)
        self.assertIn(b"Updated Name", res.data)

        # Change Password
        new_pass = "BrandNewPass999"
        res = self.client.post("/profile", data={
            "action": "password",
            "current_password": self.test_password,
            "new_password": new_pass,
            "confirm_password": new_pass
        }, follow_redirects=True)
        self.assertIn(b"Password changed successfully", res.data)

        # Verify logout and login with new password
        self.client.post("/logout")
        res = self.client.post("/login", data={"email": self.test_email_1, "password": new_pass}, follow_redirects=True)
        self.assertIn(b"Welcome back, Updated Name!", res.data)

    # -------------------------------------------------------------
    # 8. ERROR HANDLERS (404 & 500)
    # -------------------------------------------------------------
    def test_error_handlers(self):
        # 404
        res = self.client.get("/non-existent-page-12345")
        self.assertEqual(res.status_code, 404)
        self.assertIn(b"Page not found", res.data)

    # -------------------------------------------------------------
    # 9. VALIDATION EDGE CASES & UI RENDERING
    # -------------------------------------------------------------
    def test_expense_form_validation_edge_cases(self):
        user_id = self.create_user_direct("Validation User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        # Negative amount
        res = self.client.post("/expenses/add", data={
            "amount": "-50", "category": "Food", "expense_date": date.today().isoformat(),
            "payment_method": "Cash", "description": "Invalid"
        })
        self.assertIn(b"Amount must be greater than zero", res.data)

        # Excess decimal places
        res = self.client.post("/expenses/add", data={
            "amount": "10.555", "category": "Food", "expense_date": date.today().isoformat(),
            "payment_method": "Cash", "description": "Invalid"
        })
        self.assertIn(b"Amount can have at most two decimal places", res.data)

        # Invalid category
        res = self.client.post("/expenses/add", data={
            "amount": "100.00", "category": "Cryptocurrency", "expense_date": date.today().isoformat(),
            "payment_method": "Cash", "description": "Invalid"
        })
        self.assertIn(b"Choose a valid category", res.data)

        # Invalid payment method
        res = self.client.post("/expenses/add", data={
            "amount": "100.00", "category": "Food", "expense_date": date.today().isoformat(),
            "payment_method": "Bitcoin", "description": "Invalid"
        })
        self.assertIn(b"Choose a valid payment method", res.data)

        # Invalid date
        res = self.client.post("/expenses/add", data={
            "amount": "100.00", "category": "Food", "expense_date": "invalid-date",
            "payment_method": "Cash", "description": "Invalid"
        })
        self.assertIn(b"Choose a valid expense date", res.data)

    def test_budget_and_profile_validation_edge_cases(self):
        user_id = self.create_user_direct("Edge User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        # Budget zero or negative
        res = self.client.post("/budget", data={"budget_amount": "0"}, follow_redirects=True)
        self.assertIn(b"Enter a valid monthly budget greater than zero", res.data)

        # Profile short name
        res = self.client.post("/profile", data={"action": "name", "name": "A"}, follow_redirects=True)
        self.assertIn(b"Name must be between 2 and 120 characters", res.data)

        # Profile wrong current password
        res = self.client.post("/profile", data={
            "action": "password", "current_password": "WrongPassword123",
            "new_password": "NewPassword123", "confirm_password": "NewPassword123"
        }, follow_redirects=True)
        self.assertIn(b"Your current password is incorrect", res.data)

        # Profile password mismatch
        res = self.client.post("/profile", data={
            "action": "password", "current_password": self.test_password,
            "new_password": "NewPassword123", "confirm_password": "DifferentPassword123"
        }, follow_redirects=True)
        self.assertIn(b"New passwords do not match", res.data)

    def test_all_pages_render_with_utf8_currency(self):
        user_id = self.create_user_direct("UI User", self.test_email_1, self.test_password)

        # Public pages
        for path in ["/", "/login", "/register", "/forgot-password"]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Expense", res.data)
            self.assertIn(b"charset=\"UTF-8\"", res.data)

        # Authenticated pages
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})
        for path in ["/dashboard", "/expenses", "/expenses/add", "/budget", "/reports", "/profile"]:
            res = self.client.get(path)
            self.assertEqual(res.status_code, 200)
            # Check rupee symbol or entity is present
            self.assertTrue(b"\xe2\x82\xb9" in res.data or b"&#8377;" in res.data)

    # -------------------------------------------------------------
    # 10. EXPORT EXPENSES TESTS (FEATURE 1)
    # -------------------------------------------------------------
    def test_export_expenses_unauthenticated(self):
        res = self.client.get("/expenses/export")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_export_expenses_basic(self):
        user_id = self.create_user_direct("Export User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        # Add expenses
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES "
            "(%s, 150.00, 'Food', %s, 'UPI', 'Lunch at cafe'), "
            "(%s, 1200.50, 'Bills', %s, 'Credit Card', 'Electricity bill')",
            (user_id, date.today(), user_id, date.today())
        )
        db.commit()
        cursor.close()

        res = self.client.get("/expenses/export")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.content_type.startswith("text/csv"))
        self.assertIn("attachment; filename=\"ExpenseFlow_Expenses_", res.headers.get("Content-Disposition", ""))

        csv_text = res.data.decode("utf-8")
        lines = [line.strip() for line in csv_text.strip().splitlines()]
        self.assertEqual(lines[0], "Date,Category,Payment Method,Description,Amount")
        self.assertEqual(len(lines), 3) # Header + 2 rows
        self.assertIn("Food,UPI,Lunch at cafe,150.00", csv_text)
        self.assertIn("Bills,Credit Card,Electricity bill,1200.50", csv_text)

    def test_export_expenses_with_filters_and_search(self):
        user_id = self.create_user_direct("Filter Export User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES "
            "(%s, 200.00, 'Food', %s, 'UPI', 'Food delivery pizza'), "
            "(%s, 500.00, 'Shopping', %s, 'Debit Card', 'Books from store'), "
            "(%s, 800.00, 'Entertainment', %s, 'UPI', 'Movie tickets')",
            (user_id, date.today(), user_id, date.today(), user_id, date.today())
        )
        db.commit()
        cursor.close()

        # Filter by category Food
        res = self.client.get("/expenses/export?category=Food")
        self.assertEqual(res.status_code, 200)
        csv_text = res.data.decode("utf-8")
        self.assertIn("Food delivery pizza", csv_text)
        self.assertNotIn("Books from store", csv_text)
        self.assertNotIn("Movie tickets", csv_text)

        # Filter by search term "Books"
        res = self.client.get("/expenses/export?search=Books")
        self.assertEqual(res.status_code, 200)
        csv_text = res.data.decode("utf-8")
        self.assertIn("Books from store", csv_text)
        self.assertNotIn("Food delivery pizza", csv_text)

    def test_export_expenses_empty(self):
        user_id = self.create_user_direct("Empty Export User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        res = self.client.get("/expenses/export")
        self.assertEqual(res.status_code, 200)
        csv_text = res.data.decode("utf-8").strip()
        self.assertEqual(csv_text, "Date,Category,Payment Method,Description,Amount")

    def test_export_expenses_cross_user_isolation(self):
        user1_id = self.create_user_direct("User One", self.test_email_1, self.test_password)
        user2_id = self.create_user_direct("User Two", self.test_email_2, self.test_password)

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES "
            "(%s, 350.00, 'Food', %s, 'Cash', 'User1 Private Secret Expense'), "
            "(%s, 950.00, 'Shopping', %s, 'Credit Card', 'User2 Private Secret Expense')",
            (user1_id, date.today(), user2_id, date.today())
        )
        db.commit()
        cursor.close()

        # Login as User 1 and export
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})
        res = self.client.get("/expenses/export")
        csv_text = res.data.decode("utf-8")
        self.assertIn("User1 Private Secret Expense", csv_text)
        self.assertNotIn("User2 Private Secret Expense", csv_text)

    # -------------------------------------------------------------
    # 11. SMART FINANCIAL INSIGHTS TESTS (FEATURE 2)
    # -------------------------------------------------------------
    def test_financial_insights_empty_state_for_new_user(self):
        user_id = self.create_user_direct("New Insights User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Smart Financial Insights", res.data)
        self.assertIn(b"Welcome to Financial Insights!", res.data)

    def test_financial_insights_monthly_spending_trends(self):
        user_id = self.create_user_direct("Trend User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        today = date.today()
        # Month start and previous month date
        curr_start = today.replace(day=1)
        prev_month_date = (curr_start - timedelta(days=5)).replace(day=15)

        cursor = db.cursor()
        # Add previous month expense: ₹1,000
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
            "VALUES (%s, 1000.00, 'Food', %s, 'Cash', 'Prev month groceries')",
            (user_id, prev_month_date)
        )
        # Add current month expense: ₹1,500
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
            "VALUES (%s, 1500.00, 'Shopping', %s, 'UPI', 'Current month clothes')",
            (user_id, today)
        )
        db.commit()
        cursor.close()

        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Smart Financial Insights", res.data)
        self.assertIn(b"Monthly Trend", res.data)
        # Spent ₹500 more than last month
        self.assertIn(b"more than last month", res.data)
        self.assertIn(b"Shopping was your highest spending category", res.data)

    def test_financial_insights_budget_health_states(self):
        user_id = self.create_user_direct("Budget Insights User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})
        today = date.today()

        # Set budget to ₹10,000
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO budgets (user_id, month, year, budget_amount) VALUES (%s, %s, %s, 10000.00)",
            (user_id, today.month, today.year)
        )
        # Add ₹4,000 expense (40% used -> On track)
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
            "VALUES (%s, 4000.00, 'Food', %s, 'UPI', 'Food')",
            (user_id, today)
        )
        db.commit()
        cursor.close()

        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Safe and on track", res.data)

        # Update expense to ₹8,500 (85% used -> Warning approaching limit)
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
            "VALUES (%s, 4500.00, 'Bills', %s, 'UPI', 'Bills')",
            (user_id, today)
        )
        db.commit()
        cursor.close()

        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"approaching your limit", res.data)

        # Add more expenses to exceed budget: ₹11,000 total (> 100%)
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
            "VALUES (%s, 2500.00, 'Shopping', %s, 'UPI', 'Extra shopping')",
            (user_id, today)
        )
        db.commit()
        cursor.close()

        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"budget has been exceeded", res.data)

    # -------------------------------------------------------------
    # 7. SMART NOTIFICATIONS & ALERTS TESTS
    # -------------------------------------------------------------
    def test_notifications_generation_and_threshold_alerts(self):
        user_id = self.create_user_direct("Notif User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})
        today = date.today()

        # Set budget to ₹10,000
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO budgets (user_id, month, year, budget_amount) VALUES (%s, %s, %s, 10000.00)",
            (user_id, today.month, today.year)
        )
        # Add expense ₹8,200 (82% of budget -> triggers budget_80 alert)
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
            "VALUES (%s, 8200.00, 'Shopping', %s, 'UPI', 'Laptop purchase')",
            (user_id, today)
        )
        db.commit()
        cursor.close()

        # Request dashboard - generates notification
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Budget Alert (80%)", res.data)
        self.assertIn(b"Large Expense Logged", res.data)

        # Verify notifications in DB
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM notifications WHERE user_id = %s", (user_id,))
        notifs = cursor.fetchall()
        cursor.close()
        notif_types = [n["type"] for n in notifs]
        self.assertIn("budget_80", notif_types)
        self.assertIn("large_expense", notif_types)

        # Re-request dashboard to ensure deduplication prevents duplicate entries
        self.client.get("/dashboard")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS count FROM notifications WHERE user_id = %s", (user_id,))
        count_after = cursor.fetchone()["count"]
        cursor.close()
        self.assertEqual(len(notifs), count_after)

    def test_notifications_actions_and_isolation(self):
        user1_id = self.create_user_direct("Notif User 1", self.test_email_1, self.test_password)
        user2_id = self.create_user_direct("Notif User 2", self.test_email_2, self.test_password)

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO notifications (user_id, type, title, message, is_read) VALUES (%s, 'budget_80', 'Test 1', 'Msg 1', FALSE)",
            (user1_id,)
        )
        notif1_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO notifications (user_id, type, title, message, is_read) VALUES (%s, 'budget_90', 'Test 2', 'Msg 2', FALSE)",
            (user1_id,)
        )
        notif2_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO notifications (user_id, type, title, message, is_read) VALUES (%s, 'budget_exceeded', 'Test User 2', 'Msg', FALSE)",
            (user2_id,)
        )
        notif_user2_id = cursor.lastrowid
        db.commit()
        cursor.close()

        # Log in as user 1
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})

        # Mark single notification as read
        res = self.client.post(f"/notifications/{notif1_id}/read")
        self.assertEqual(res.status_code, 302)
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT is_read FROM notifications WHERE id = %s", (notif1_id,))
        self.assertTrue(cursor.fetchone()["is_read"])
        cursor.close()

        # User 1 cannot mark or dismiss user 2's notification
        self.client.post(f"/notifications/{notif_user2_id}/dismiss")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM notifications WHERE id = %s", (notif_user2_id,))
        self.assertIsNotNone(cursor.fetchone())
        cursor.close()

        # User 1 marks all as read
        self.client.post("/notifications/read-all")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT is_read FROM notifications WHERE user_id = %s", (user1_id,))
        for row in cursor.fetchall():
            self.assertTrue(row["is_read"])
        cursor.close()

        # Dismiss notification 1
        self.client.post(f"/notifications/{notif1_id}/dismiss")
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM notifications WHERE id = %s", (notif1_id,))
        self.assertIsNone(cursor.fetchone())
        cursor.close()

    # -------------------------------------------------------------
    # 8. ADVANCED SEARCH & BETTER FILTERS TESTS
    # -------------------------------------------------------------
    def test_advanced_search_min_max_amount_filters(self):
        user_id = self.create_user_direct("Filter User", self.test_email_1, self.test_password)
        self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})
        today = date.today()

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) VALUES "
            "(%s, 150.00, 'Food', %s, 'Cash', 'Coffee and Snack'), "
            "(%s, 650.00, 'Food', %s, 'UPI', 'Dinner with family'), "
            "(%s, 3200.00, 'Shopping', %s, 'Credit Card', 'New Shoes'), "
            "(%s, 12000.00, 'Bills', %s, 'Bank Transfer', 'Electricity Bill')",
            (user_id, today, user_id, today, user_id, today, user_id, today)
        )
        db.commit()
        cursor.close()

        # Test Min Amount filter >= 500
        res = self.client.get("/expenses?min_amount=500")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Dinner with family", res.data)
        self.assertIn(b"New Shoes", res.data)
        self.assertIn(b"Electricity Bill", res.data)
        self.assertNotIn(b"Coffee and Snack", res.data)

        # Test Max Amount filter <= 1000
        res = self.client.get("/expenses?max_amount=1000")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Coffee and Snack", res.data)
        self.assertIn(b"Dinner with family", res.data)
        self.assertNotIn(b"New Shoes", res.data)
        self.assertNotIn(b"Electricity Bill", res.data)

        # Test Combined Min and Max Amount range (500 to 4000)
        res = self.client.get("/expenses?min_amount=500&max_amount=4000")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"Coffee and Snack", res.data)
        self.assertIn(b"Dinner with family", res.data)
        self.assertIn(b"New Shoes", res.data)
        self.assertNotIn(b"Electricity Bill", res.data)

        # Test CSV Export with Min/Max amount
        export_res = self.client.get("/expenses/export?min_amount=500&max_amount=4000")
        self.assertEqual(export_res.status_code, 200)
        csv_text = export_res.data.decode("utf-8")
        self.assertIn("Dinner with family", csv_text)
        self.assertIn("New Shoes", csv_text)
        self.assertNotIn("Coffee and Snack", csv_text)
        self.assertNotIn("Electricity Bill", csv_text)

    # -------------------------------------------------------------
    # 9. SECURITY & CSRF PROTECTION TESTS
    # -------------------------------------------------------------
    def test_security_csrf_protection_and_headers(self):
        user_id = self.create_user_direct("Security User", self.test_email_1, self.test_password)
        
        # Test security headers on GET request
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

        # Temporarily enable CSRF validation in test client
        flask_app.config["WTF_CSRF_ENABLED"] = True
        try:
            # Login without CSRF token must fail with 400
            res = self.client.post("/login", data={"email": self.test_email_1, "password": self.test_password})
            self.assertEqual(res.status_code, 400)
            self.assertIn(b"CSRF Verification Failed", res.data)

            # Get login page to establish session CSRF token
            get_res = self.client.get("/login")
            with self.client.session_transaction() as sess:
                valid_csrf = sess.get("csrf_token")

            # Login WITH valid CSRF token succeeds
            login_res = self.client.post(
                "/login",
                data={"email": self.test_email_1, "password": self.test_password, "csrf_token": valid_csrf},
                follow_redirects=True
            )
            self.assertEqual(login_res.status_code, 200)
            self.assertIn(b"Dashboard", login_res.data)
        finally:
            flask_app.config["WTF_CSRF_ENABLED"] = False

    # -------------------------------------------------------------
    # 10. GOOGLE OAUTH AUTHENTICATION TESTS
    # -------------------------------------------------------------
    def test_google_auth_buttons_rendered_on_login_and_register(self):
        # Verify /login renders the Google button and divider
        res_login = self.client.get("/login")
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"Continue with Google", res_login.data)
        self.assertIn(b"google-login-btn", res_login.data)
        self.assertIn(b"auth-divider", res_login.data)

        # Verify /register renders the Google button and divider
        res_reg = self.client.get("/register")
        self.assertEqual(res_reg.status_code, 200)
        self.assertIn(b"Continue with Google", res_reg.data)
        self.assertIn(b"google-register-btn", res_reg.data)
        self.assertIn(b"auth-divider", res_reg.data)

    def test_google_login_not_configured(self):
        with patch.object(app, "GOOGLE_CLIENT_ID", None), patch.object(app, "GOOGLE_CLIENT_SECRET", None):
            res = self.client.get("/login/google", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Google Sign-In is not currently configured", res.data)

    def test_google_login_redirect_and_state(self):
        with patch.object(app, "GOOGLE_CLIENT_ID", "mock_client_id_123"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "mock_secret_456"):
            res = self.client.get("/login/google")
            self.assertEqual(res.status_code, 302)
            self.assertIn("accounts.google.com/o/oauth2/v2/auth", res.headers["Location"])
            self.assertIn("client_id=mock_client_id_123", res.headers["Location"])
            self.assertIn("scope=openid+email+profile", res.headers["Location"])
            with self.client.session_transaction() as sess:
                self.assertIn("google_oauth_state", sess)
                self.assertTrue(len(sess["google_oauth_state"]) > 20)

    def test_google_callback_user_cancelled(self):
        res = self.client.get("/login/google/callback?error=access_denied", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Google Sign-In was cancelled or denied", res.data)

    def test_google_callback_state_mismatch(self):
        with self.client.session_transaction() as sess:
            sess["google_oauth_state"] = "expected_state_abc"

        res = self.client.get("/login/google/callback?code=some_code&state=wrong_state", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"invalid session state", res.data)

    @patch("requests.get")
    @patch("requests.post")
    def test_google_callback_new_user_creation(self, mock_post, mock_get):
        new_google_email = f"google_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@gmail.com"
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token_123"}

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": "google_sub_987654",
            "email": new_google_email,
            "email_verified": True,
            "name": "Google Explorer",
        }

        with patch.object(app, "GOOGLE_CLIENT_ID", "mock_client_id_123"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "mock_secret_456"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "valid_state_token"

            res = self.client.get("/login/google/callback?code=mock_code&state=valid_state_token", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Account created successfully with Google", res.data)

            # Confirm user in DB
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, name, email, auth_provider, google_id FROM users WHERE email = %s", (new_google_email,))
            created = cursor.fetchone()
            cursor.close()

            self.assertIsNotNone(created)
            self.assertEqual(created["name"], "Google Explorer")
            self.assertEqual(created["auth_provider"], "google")
            self.assertEqual(created["google_id"], "google_sub_987654")
            self.created_user_ids.append(created["id"])

            # Verify session
            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get("user_id"), created["id"])
                self.assertEqual(sess.get("user_email"), new_google_email)

    @patch("requests.get")
    @patch("requests.post")
    def test_google_callback_existing_local_user_linking(self, mock_post, mock_get):
        # Create an existing local password user
        local_email = f"local_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@gmail.com"
        user_id = self.create_user_direct("Local User", local_email, self.test_password)

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token_123"}

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": "google_sub_linked_123",
            "email": local_email,
            "email_verified": True,
            "name": "Local User Linked",
        }

        with patch.object(app, "GOOGLE_CLIENT_ID", "mock_client_id_123"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "mock_secret_456"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "valid_state_token"

            res = self.client.get("/login/google/callback?code=mock_code&state=valid_state_token", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Your Google account has been securely linked", res.data)

            # Confirm session was established with the existing user ID
            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get("user_id"), user_id)
                self.assertEqual(sess.get("user_email"), local_email)

            # Confirm google_id and auth_provider updated in DB
            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, google_id, auth_provider FROM users WHERE id = %s", (user_id,))
            updated_user = cursor.fetchone()
            cursor.close()
            self.assertEqual(updated_user["google_id"], "google_sub_linked_123")
            self.assertEqual(updated_user["auth_provider"], "google")

    @patch("requests.get")
    @patch("requests.post")
    def test_google_callback_existing_google_user_relogin(self, mock_post, mock_get):
        # Create an existing Google user
        google_email = f"existing_google_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@gmail.com"
        google_sub = "google_sub_existing_111"
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password, google_id, auth_provider) VALUES (%s, %s, %s, %s, 'google')",
            ("Existing Google", google_email, generate_password_hash("random_dummy"), google_sub)
        )
        db.commit()
        user_id = cursor.lastrowid
        cursor.close()
        self.created_user_ids.append(user_id)

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token_123"}

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": google_sub,
            "email": google_email,
            "email_verified": True,
            "name": "Existing Google",
        }

        with patch.object(app, "GOOGLE_CLIENT_ID", "mock_client_id_123"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "mock_secret_456"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "valid_state_token"

            res = self.client.get("/login/google/callback?code=mock_code&state=valid_state_token", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Welcome back, Existing Google!", res.data)

            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get("user_id"), user_id)
                self.assertEqual(sess.get("user_email"), google_email)

    def test_duplicate_email_registration_rejected(self):
        # Create user
        existing_email = f"duplicate_test_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@example.com"
        self.create_user_direct("Existing User", existing_email, self.test_password)

        # Attempt to register with the same email
        res = self.client.post("/register", data={
            "name": "Another Person",
            "email": existing_email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"An account with this email already exists. Please log in instead.", res.data)

    def test_google_only_account_password_login_shows_guidance(self):
        google_email = f"google_only_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@example.com"
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password, google_id, auth_provider) VALUES (%s, %s, %s, %s, 'google')",
            ("Google Only", google_email, generate_password_hash("unguessable_hash"), "google_id_777")
        )
        db.commit()
        user_id = cursor.lastrowid
        cursor.close()
        self.created_user_ids.append(user_id)

        # Attempt password login
        res = self.client.post("/login", data={
            "email": google_email,
            "password": "WrongPassword123"
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"This account uses Google sign-in. Please continue with Google.", res.data)

    @patch("requests.post")
    def test_google_callback_invalid_client_secret_error(self, mock_post):
        mock_post.return_value.status_code = 401
        mock_post.return_value.json.return_value = {
            "error": "invalid_client",
            "error_description": "The provided client secret is invalid."
        }
        with patch.object(app, "GOOGLE_CLIENT_ID", "mock_client_id_123"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "mock_secret_456"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "valid_state_token"

            res = self.client.get("/login/google/callback?code=mock_code&state=valid_state_token", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"The provided Google Client Secret is invalid", res.data)

    @patch("requests.post")
    def test_google_callback_redirect_uri_mismatch_error(self, mock_post):
        mock_post.return_value.status_code = 400
        mock_post.return_value.json.return_value = {
            "error": "redirect_uri_mismatch",
            "error_description": "Bad Request"
        }
        with patch.object(app, "GOOGLE_CLIENT_ID", "mock_client_id_123"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "mock_secret_456"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "valid_state_token"

            res = self.client.get("/login/google/callback?code=mock_code&state=valid_state_token", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"The redirect URI does not match Google Cloud Console settings", res.data)

    @patch("requests.get")
    @patch("requests.post")
    def test_google_logout_and_relogin_flow(self, mock_post, mock_get):
        google_email = f"google_logout_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@gmail.com"
        google_sub = f"google_sub_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token_abc"}

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": google_sub,
            "email": google_email,
            "email_verified": True,
            "name": "Logout Relogin Tester",
        }

        with patch.object(app, "GOOGLE_CLIENT_ID", "mock_client_id_123"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "mock_secret_456"):
            # Step 1: Initial Login / Registration with Google
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "state_flow_1"

            res1 = self.client.get("/login/google/callback?code=code_1&state=state_flow_1", follow_redirects=True)
            self.assertEqual(res1.status_code, 200)
            self.assertIn(b"Account created successfully with Google", res1.data)
            with self.client.session_transaction() as sess:
                user_id = sess.get("user_id")
                self.assertIsNotNone(user_id)
                self.created_user_ids.append(user_id)

            # Step 2: Logout
            res_logout = self.client.post("/logout", follow_redirects=True)
            self.assertEqual(res_logout.status_code, 200)
            with self.client.session_transaction() as sess:
                self.assertNotIn("user_id", sess)

            # Step 3: Login again with Google
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "state_flow_2"

            res2 = self.client.get("/login/google/callback?code=code_2&state=state_flow_2", follow_redirects=True)
            self.assertEqual(res2.status_code, 200)
            self.assertIn(b"Welcome back, Logout Relogin Tester!", res2.data)
            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get("user_id"), user_id)


if __name__ == "__main__":
    unittest.main()



