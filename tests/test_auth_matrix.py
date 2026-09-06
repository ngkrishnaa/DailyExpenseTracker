"""
Comprehensive Authentication Matrix Test Suite
=============================================
Tests all 27 authentication requirements from Requirement 7:
1. New email registration
2. Duplicate email registration
3. Registration OTP correct
4. Registration OTP incorrect
5. Registration OTP expired
6. Registration OTP reused
7. Normal login
8. Wrong password
9. Logout
10. Forgot password
11. Password-reset OTP correct
12. Password-reset OTP incorrect
13. Password-reset OTP expired
14. Password-reset OTP reused
15. Successful password reset
16. Login using new password
17. New Google account
18. New Google account -> set application password
19. Google login after password setup
20. Email/password login after Google password setup
21. Existing local account -> Google login/linking
22. Google account without password -> email/password behavior
23. OAuth invalid state
24. OAuth failure
25. Protected route without login
26. User A cannot access User B's data
27. Logout invalidates session
"""

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


class AuthMatrixTestSuite(unittest.TestCase):
    def setUp(self):
        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False
        self.client = flask_app.test_client()
        pending_registrations.clear()
        password_reset_requests.clear()
        self.ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.test_email = f"auth_matrix_{self.ts}@example.com"
        self.test_password = "Password123"
        self.created_user_ids = []

    def tearDown(self):
        if self.created_user_ids:
            cursor = db.cursor()
            fmt = ",".join(["%s"] * len(self.created_user_ids))
            for tbl in ("notifications", "expenses", "budgets", "auth_otps"):
                try:
                    if tbl == "auth_otps":
                        cursor.execute(f"DELETE FROM {tbl} WHERE email LIKE %s", (f"%{self.ts}%",))
                    else:
                        cursor.execute(f"DELETE FROM {tbl} WHERE user_id IN ({fmt})", tuple(self.created_user_ids))
                except Exception:
                    pass
            cursor.execute(f"DELETE FROM users WHERE id IN ({fmt})", tuple(self.created_user_ids))
            db.commit()
            cursor.close()
        pending_registrations.clear()
        password_reset_requests.clear()

    def create_user_direct(self, name, email, password="Password123", auth_provider="local", google_id=None, has_set_password=True):
        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO users (name, email, password, auth_provider, google_id, has_set_password)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (name, email.lower(), generate_password_hash(password) if password else None, auth_provider, google_id, has_set_password),
        )
        db.commit()
        uid = cursor.lastrowid
        cursor.close()
        self.created_user_ids.append(uid)
        return uid

    # 1. New email registration
    @patch("app.send_otp_email")
    def test_01_new_email_registration(self, mock_send):
        mock_send.return_value = True
        res = self.client.post("/register", data={
            "name": "New User",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password,
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(self.test_email, pending_registrations)
        self.assertEqual(len(pending_registrations[self.test_email]["otp"]), 6)
        mock_send.assert_called_once()

    # 2. Duplicate email registration
    @patch("app.send_otp_email")
    def test_02_duplicate_email_registration(self, mock_send):
        mock_send.return_value = True
        self.create_user_direct("Existing User", self.test_email, self.test_password)
        res = self.client.post("/register", data={
            "name": "Duplicate Person",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password,
        })
        self.assertIn(b"An account with this email already exists. Please log in instead.", res.data)
        self.assertFalse(mock_send.called)

    # 3. Registration OTP correct
    @patch("app.send_otp_email")
    def test_03_registration_otp_correct(self, mock_send):
        mock_send.return_value = True
        self.client.post("/register", data={
            "name": "Verified User",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password,
        })
        otp = pending_registrations[self.test_email]["otp"]
        res = self.client.post(f"/verify-otp?email={self.test_email}", data={"otp": otp}, follow_redirects=True)
        self.assertIn(b"Account created successfully", res.data)
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, name, email, has_set_password FROM users WHERE email = %s", (self.test_email,))
        user = cursor.fetchone()
        cursor.close()
        self.assertIsNotNone(user)
        self.assertTrue(user["has_set_password"])
        self.created_user_ids.append(user["id"])

    # 4. Registration OTP incorrect
    @patch("app.send_otp_email")
    def test_04_registration_otp_incorrect(self, mock_send):
        mock_send.return_value = True
        self.client.post("/register", data={
            "name": "Retry User",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password,
        })
        res = self.client.post(f"/verify-otp?email={self.test_email}", data={"otp": "000000"})
        self.assertIn(b"Incorrect OTP. 4 attempt(s) remaining.", res.data)
        self.assertEqual(pending_registrations[self.test_email]["attempts"], 1)

    # 5. Registration OTP expired
    @patch("app.send_otp_email")
    def test_05_registration_otp_expired(self, mock_send):
        mock_send.return_value = True
        self.client.post("/register", data={
            "name": "Expired Reg User",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password,
        })
        pending_registrations[self.test_email]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=5)
        otp = pending_registrations[self.test_email]["otp"]
        res = self.client.post(f"/verify-otp?email={self.test_email}", data={"otp": otp}, follow_redirects=True)
        self.assertIn(b"Your verification code has expired", res.data)
        self.assertNotIn(self.test_email, pending_registrations)

    # 6. Registration OTP reused
    @patch("app.send_otp_email")
    def test_06_registration_otp_reused(self, mock_send):
        mock_send.return_value = True
        self.client.post("/register", data={
            "name": "Reuse Reg User",
            "email": self.test_email,
            "password": self.test_password,
            "confirm_password": self.test_password,
        })
        otp = pending_registrations[self.test_email]["otp"]
        # First verification succeeds
        res1 = self.client.post(f"/verify-otp?email={self.test_email}", data={"otp": otp}, follow_redirects=True)
        self.assertIn(b"Account created successfully", res1.data)
        with self.client.session_transaction() as sess:
            self.created_user_ids.append(sess.get("user_id"))

        # Second verification attempt with the same OTP should be rejected
        res2 = self.client.post(f"/verify-otp?email={self.test_email}", data={"otp": otp}, follow_redirects=True)
        self.assertIn(b"Registration session expired or invalid", res2.data)

    # 7. Normal login
    def test_07_normal_login(self):
        uid = self.create_user_direct("Normal Login User", self.test_email, self.test_password)
        res = self.client.post("/login", data={"email": self.test_email, "password": self.test_password}, follow_redirects=True)
        self.assertIn(b"Welcome back, Normal Login User!", res.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_id"), uid)

    # 8. Wrong password
    def test_08_wrong_password(self):
        self.create_user_direct("Wrong Pass User", self.test_email, self.test_password)
        res = self.client.post("/login", data={"email": self.test_email, "password": "WrongPassword999"})
        self.assertIn(b"Invalid email or password.", res.data)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    # 9. Logout
    def test_09_logout(self):
        self.create_user_direct("Logout User", self.test_email, self.test_password)
        self.client.post("/login", data={"email": self.test_email, "password": self.test_password})
        res = self.client.post("/logout", follow_redirects=True)
        self.assertIn(b"You have been logged out successfully.", res.data)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    # 10. Forgot password
    @patch("app.send_password_reset_otp_email")
    def test_10_forgot_password(self, mock_send):
        mock_send.return_value = True
        self.create_user_direct("Forgot User", self.test_email, self.test_password)
        res = self.client.post("/forgot-password", data={"email": self.test_email}, follow_redirects=True)
        self.assertIn(b"If an account exists for that email, a password reset code has been sent.", res.data)
        mock_send.assert_called_once()
        with self.client.session_transaction() as sess:
            self.assertIsNotNone(sess.get("password_reset_token"))

    # 11. Password-reset OTP correct
    @patch("app.send_password_reset_otp_email")
    def test_11_password_reset_otp_correct(self, mock_send):
        mock_send.return_value = True
        self.create_user_direct("Reset OTP User", self.test_email, self.test_password)
        self.client.post("/forgot-password", data={"email": self.test_email})
        otp = mock_send.call_args[0][1]
        res = self.client.post("/verify-reset-otp", data={"otp": otp}, follow_redirects=True)
        self.assertIn(b"Code verified. Please create your new password.", res.data)

    # 12. Password-reset OTP incorrect
    @patch("app.send_password_reset_otp_email")
    def test_12_password_reset_otp_incorrect(self, mock_send):
        mock_send.return_value = True
        self.create_user_direct("Reset Incorrect User", self.test_email, self.test_password)
        self.client.post("/forgot-password", data={"email": self.test_email})
        res = self.client.post("/verify-reset-otp", data={"otp": "999999"})
        self.assertIn(b"Incorrect code. 4 attempt(s) remaining.", res.data)

    # 13. Password-reset OTP expired
    @patch("app.send_password_reset_otp_email")
    def test_13_password_reset_otp_expired(self, mock_send):
        mock_send.return_value = True
        self.create_user_direct("Reset Expired User", self.test_email, self.test_password)
        self.client.post("/forgot-password", data={"email": self.test_email})
        with self.client.session_transaction() as sess:
            token = sess["password_reset_token"]
        password_reset_requests[token]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=5)
        otp = mock_send.call_args[0][1]
        res = self.client.post("/verify-reset-otp", data={"otp": otp}, follow_redirects=True)
        self.assertIn(b"Your password reset request is invalid or has expired.", res.data)

    # 14. Password-reset OTP reused
    @patch("app.send_password_reset_otp_email")
    def test_14_password_reset_otp_reused(self, mock_send):
        mock_send.return_value = True
        self.create_user_direct("Reset Reuse User", self.test_email, self.test_password)
        self.client.post("/forgot-password", data={"email": self.test_email})
        otp = mock_send.call_args[0][1]
        # Step 1: Verify OTP and reset password
        self.client.post("/verify-reset-otp", data={"otp": otp}, follow_redirects=True)
        new_pass = "BrandNewPass123"
        self.client.post("/reset-password", data={"password": new_pass, "confirm_password": new_pass}, follow_redirects=True)

        # Step 2: Try to reuse the reset flow or token without new request
        res = self.client.post("/reset-password", data={"password": "AnotherPass123", "confirm_password": "AnotherPass123"}, follow_redirects=True)
        self.assertIn(b"Please verify a valid password reset code first.", res.data)

    # 15. Successful password reset
    @patch("app.send_password_reset_otp_email")
    def test_15_successful_password_reset(self, mock_send):
        mock_send.return_value = True
        uid = self.create_user_direct("Reset Success User", self.test_email, self.test_password)
        self.client.post("/forgot-password", data={"email": self.test_email})
        otp = mock_send.call_args[0][1]
        self.client.post("/verify-reset-otp", data={"otp": otp})
        new_pass = "UpdatedPass789"
        res = self.client.post("/reset-password", data={"password": new_pass, "confirm_password": new_pass}, follow_redirects=True)
        self.assertIn(b"Your password has been reset and updated successfully. You can now log in.", res.data)
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT password, has_set_password FROM users WHERE id = %s", (uid,))
        row = cursor.fetchone()
        cursor.close()
        self.assertTrue(check_password_hash(row["password"], new_pass))
        self.assertTrue(row["has_set_password"])

    # 16. Login using new password
    @patch("app.send_password_reset_otp_email")
    def test_16_login_using_new_password(self, mock_send):
        mock_send.return_value = True
        uid = self.create_user_direct("New Pass Login User", self.test_email, self.test_password)
        self.client.post("/forgot-password", data={"email": self.test_email})
        otp = mock_send.call_args[0][1]
        self.client.post("/verify-reset-otp", data={"otp": otp})
        new_pass = "UpdatedPass789"
        self.client.post("/reset-password", data={"password": new_pass, "confirm_password": new_pass})

        # Old password fails
        res_old = self.client.post("/login", data={"email": self.test_email, "password": self.test_password})
        self.assertIn(b"Invalid email or password.", res_old.data)

        # New password succeeds
        res_new = self.client.post("/login", data={"email": self.test_email, "password": new_pass}, follow_redirects=True)
        self.assertIn(b"Welcome back", res_new.data)

    # 17. New Google account
    @patch("requests.get")
    @patch("requests.post")
    def test_17_new_google_account(self, mock_post, mock_get):
        google_email = f"new_google_{self.ts}@gmail.com"
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": f"google_sub_{self.ts}",
            "email": google_email,
            "email_verified": True,
            "name": "New Google Explorer",
        }

        with patch.object(app, "GOOGLE_CLIENT_ID", "client_id_mock"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "client_sec_mock"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "state_17"

            res = self.client.get("/login/google/callback?code=mock_code&state=state_17", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Account created successfully with Google", res.data)
            self.assertIn(b"Set your application password", res.data)

            cursor = db.cursor(dictionary=True)
            cursor.execute("SELECT id, name, email, password, google_id, has_set_password FROM users WHERE email = %s", (google_email,))
            user = cursor.fetchone()
            cursor.close()
            self.assertIsNotNone(user)
            self.assertIsNone(user["password"])
            self.assertFalse(user["has_set_password"])
            self.created_user_ids.append(user["id"])

            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get("user_id"), user["id"])
                self.assertTrue(sess.get("pending_password_setup"))

    # 18. New Google account -> set application password
    @patch("requests.get")
    @patch("requests.post")
    def test_18_new_google_account_set_application_password(self, mock_post, mock_get):
        google_email = f"set_pass_google_{self.ts}@gmail.com"
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": f"google_sub_setpass_{self.ts}",
            "email": google_email,
            "email_verified": True,
            "name": "Set Password Google User",
        }

        with patch.object(app, "GOOGLE_CLIENT_ID", "client_id_mock"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "client_sec_mock"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "state_18"
            self.client.get("/login/google/callback?code=mock_code&state=state_18")

        with self.client.session_transaction() as sess:
            uid = sess["user_id"]
            self.created_user_ids.append(uid)

        # Post application password
        app_pass = "SecureAppPassword123"
        res = self.client.post("/set-password", data={
            "password": app_pass,
            "confirm_password": app_pass,
        }, follow_redirects=True)
        self.assertIn(b"Your application password has been set successfully!", res.data)
        self.assertIn(b"Good to see you", res.data)

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT password, has_set_password FROM users WHERE id = %s", (uid,))
        user = cursor.fetchone()
        cursor.close()
        self.assertTrue(check_password_hash(user["password"], app_pass))
        self.assertTrue(user["has_set_password"])

        with self.client.session_transaction() as sess:
            self.assertNotIn("pending_password_setup", sess)

    # 19. Google login after password setup
    @patch("requests.get")
    @patch("requests.post")
    def test_19_google_login_after_password_setup(self, mock_post, mock_get):
        google_email = f"dual_login_{self.ts}@gmail.com"
        google_sub = f"google_sub_dual_{self.ts}"
        uid = self.create_user_direct("Dual User", google_email, "AppPass123", auth_provider="google", google_id=google_sub, has_set_password=True)

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": google_sub,
            "email": google_email,
            "email_verified": True,
            "name": "Dual User",
        }

        with patch.object(app, "GOOGLE_CLIENT_ID", "client_id_mock"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "client_sec_mock"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "state_19"
            res = self.client.get("/login/google/callback?code=mock_code&state=state_19", follow_redirects=True)
            self.assertIn(b"Welcome back, Dual User!", res.data)
            with self.client.session_transaction() as sess:
                self.assertEqual(sess.get("user_id"), uid)

    # 20. Email/password login after Google password setup
    def test_20_email_password_login_after_google_password_setup(self):
        google_email = f"google_with_pw_{self.ts}@gmail.com"
        google_sub = f"sub_google_pw_{self.ts}"
        app_pw = "CustomPassword123"
        uid = self.create_user_direct("App Password User", google_email, app_pw, auth_provider="google", google_id=google_sub, has_set_password=True)

        res = self.client.post("/login", data={"email": google_email, "password": app_pw}, follow_redirects=True)
        self.assertIn(b"Welcome back, App Password User!", res.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("user_id"), uid)

    # 21. Existing local account -> Google login/linking
    @patch("requests.get")
    @patch("requests.post")
    def test_21_existing_local_account_google_linking(self, mock_post, mock_get):
        local_email = f"existing_local_{self.ts}@gmail.com"
        local_pw = "LocalOriginalPass123"
        uid = self.create_user_direct("Original Local", local_email, local_pw, auth_provider="local", google_id=None, has_set_password=True)

        google_sub = f"google_linked_sub_{self.ts}"
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "mock_token"}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "sub": google_sub,
            "email": local_email,
            "email_verified": True,
            "name": "Original Local",
        }

        with patch.object(app, "GOOGLE_CLIENT_ID", "client_id_mock"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "client_sec_mock"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "state_21"
            res = self.client.get("/login/google/callback?code=mock_code&state=state_21", follow_redirects=True)
            self.assertIn(b"Your Google account has been securely linked", res.data)

        # Verify Google sub was linked and password remains intact
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT password, google_id, has_set_password FROM users WHERE id = %s", (uid,))
        user = cursor.fetchone()
        cursor.close()
        self.assertEqual(user["google_id"], google_sub)
        self.assertTrue(check_password_hash(user["password"], local_pw))

        # Can still log in via email & password!
        self.client.post("/logout")
        res_login = self.client.post("/login", data={"email": local_email, "password": local_pw}, follow_redirects=True)
        self.assertIn(b"Welcome back", res_login.data)

    # 22. Google account without password -> email/password behavior
    def test_22_google_account_without_password_email_login_behavior(self):
        google_only_email = f"google_only_nopass_{self.ts}@gmail.com"
        self.create_user_direct("Google No Pass", google_only_email, password=None, auth_provider="google", google_id="gid_nopass_123", has_set_password=False)

        res = self.client.post("/login", data={"email": google_only_email, "password": "AnyPassword123"})
        self.assertIn(b"This account uses Google sign-in. Please continue with Google.", res.data)
        self.assertIn(b"Please set an application password before using email/password login.", res.data)

    # 23. OAuth invalid state
    def test_23_oauth_invalid_state(self):
        with self.client.session_transaction() as sess:
            sess["google_oauth_state"] = "legitimate_state"

        res = self.client.get("/login/google/callback?code=mock_code&state=tampered_state", follow_redirects=True)
        self.assertIn(b"Authentication failed: invalid session state.", res.data)

    # 24. OAuth failure
    @patch("requests.post")
    def test_24_oauth_failure(self, mock_post):
        mock_post.return_value.status_code = 500
        with patch.object(app, "GOOGLE_CLIENT_ID", "client_id_mock"), \
             patch.object(app, "GOOGLE_CLIENT_SECRET", "client_sec_mock"):
            with self.client.session_transaction() as sess:
                sess["google_oauth_state"] = "state_24"

            res = self.client.get("/login/google/callback?code=mock_code&state=state_24", follow_redirects=True)
            self.assertIn(b"Google sign-in could not be completed. Please try again.", res.data)

    # 25. Protected route without login
    def test_25_protected_route_without_login(self):
        for endpoint in ["/dashboard", "/expenses", "/expenses/add", "/budget", "/reports", "/profile"]:
            res = self.client.get(endpoint, follow_redirects=True)
            self.assertIn(b"Please log in to access your dashboard.", res.data)

    # 26. User A cannot access User B's data
    def test_26_user_a_cannot_access_user_b_data(self):
        user_a_email = f"user_a_{self.ts}@example.com"
        user_b_email = f"user_b_{self.ts}@example.com"
        user_a_id = self.create_user_direct("User A", user_a_email, self.test_password)
        user_b_id = self.create_user_direct("User B", user_b_email, self.test_password)

        # Add expense for User A
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
            "VALUES (%s, 999.00, 'Food', %s, 'UPI', 'Secret A Expense')",
            (user_a_id, date.today()),
        )
        db.commit()
        expense_a_id = cursor.lastrowid
        cursor.close()

        # Log in as User B
        self.client.post("/login", data={"email": user_b_email, "password": self.test_password})

        # User B cannot see User A's expense
        res_list = self.client.get("/expenses")
        self.assertNotIn(b"Secret A Expense", res_list.data)

        # User B cannot edit User A's expense
        res_edit = self.client.get(f"/expenses/{expense_a_id}/edit", follow_redirects=True)
        self.assertIn(b"Expense not found.", res_edit.data)

        # User B cannot delete User A's expense
        res_del = self.client.post(f"/expenses/{expense_a_id}/delete", follow_redirects=True)
        self.assertIn(b"Expense not found.", res_del.data)

    # 27. Logout invalidates session
    def test_27_logout_invalidates_session(self):
        self.create_user_direct("Session Invalidate User", self.test_email, self.test_password)
        self.client.post("/login", data={"email": self.test_email, "password": self.test_password})
        res_dash = self.client.get("/dashboard")
        self.assertEqual(res_dash.status_code, 200)

        # Logout
        self.client.post("/logout")

        # Accessing dashboard after logout redirects to login
        res_post = self.client.get("/dashboard", follow_redirects=True)
        self.assertIn(b"Please log in to access your dashboard.", res_post.data)


if __name__ == "__main__":
    unittest.main()
