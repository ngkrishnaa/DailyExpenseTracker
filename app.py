from flask import Flask, flash, redirect, render_template, request, session, url_for, Response
from functools import wraps
import re
import csv
import io
import hmac
import urllib.parse as urlparse
import mysql.connector
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
import os
import random
import secrets
import smtplib
import resend
import requests
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

# Load values from .env
load_dotenv()

raw_resend_key = os.getenv("RESEND_API_KEY")
RESEND_API_KEY = raw_resend_key.strip().strip('"\'') if raw_resend_key else None
raw_resend_from = os.getenv("RESEND_FROM_EMAIL", "ExpenseFlow <onboarding@resend.dev>")
RESEND_FROM_EMAIL = raw_resend_from.strip().strip('"\'') if raw_resend_from else "ExpenseFlow <onboarding@resend.dev>"
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

raw_google_client_id = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_ID = raw_google_client_id.strip().strip('"\'') if raw_google_client_id else None
raw_google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_CLIENT_SECRET = raw_google_client_secret.strip().strip('"\'') if raw_google_client_secret else None
raw_google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_REDIRECT_URI = raw_google_redirect_uri.strip().strip('"\'') if raw_google_redirect_uri else None

MAIL_EMAIL = os.getenv("MAIL_EMAIL")
# Sanitize spaces if present in Gmail App Password for SMTP fallback
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "").replace(" ", "").strip() if os.getenv("MAIL_PASSWORD") else None

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY"),
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(os.getenv("FLASK_ENV") == "production" or os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"),
)

# Support reverse proxy headers (e.g. Railway HTTPS termination)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

if not app.config["SECRET_KEY"]:
    raise RuntimeError("FLASK_SECRET_KEY must be set in the .env file.")

# Temporary storage for registrations waiting for OTP verification
pending_registrations = {}
REGISTRATION_OTP_EXPIRY_MINUTES = 10
REGISTRATION_OTP_MAX_ATTEMPTS = 5

# Temporary password-reset requests are separate from registration OTPs.
password_reset_requests = {}
RESET_OTP_EXPIRY_MINUTES = 10
RESET_OTP_MAX_ATTEMPTS = 5

CATEGORIES = (
    "Food", "Transportation", "Shopping", "Bills", "Entertainment",
    "Health", "Education", "Travel", "Groceries", "Rent", "Other",
)
PAYMENT_METHODS = (
    "Cash", "Credit Card", "Debit Card", "UPI", "Bank Transfer", "Other",
)
EXPENSES_PER_PAGE = 10


def format_resend_error(exc):
    """Safely extract error code, type, and message from exceptions without exposing secrets."""
    err_code = getattr(exc, "code", "N/A")
    err_type = getattr(exc, "error_type", type(exc).__name__)
    err_msg = getattr(exc, "message", str(exc))
    return f"[{err_code} - {err_type}] {err_msg}"


def format_resend_user_error(exc):
    """Produce a clear, helpful user-facing error message without exposing secrets."""
    err_code = getattr(exc, "code", None)
    err_msg = getattr(exc, "message", str(exc))
    if err_code in (403, "403") or "only send testing emails" in err_msg.lower() or "verify a domain" in err_msg.lower():
        return (
            "Resend Sandbox Restriction: In testing mode (onboarding@resend.dev), "
            "emails can only be delivered to your verified Resend account owner email. "
            "To send verification emails to any recipient, verify a custom domain at resend.com/domains."
        )
    return "We could not send the verification email. Please try again."


# -----------------------------------
# SEND OTP EMAIL
# -----------------------------------

def send_otp_email(receiver_email, otp):
    subject = "Your ExpenseFlow Verification Code"
    plain_text = f"""Hello,

Your ExpenseFlow verification code is:

{otp}

This OTP is valid for this registration attempt.

If you did not request this code, you can safely ignore this email.

Regards,
ExpenseFlow Team
"""
    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #0f172a; margin: 0; font-size: 22px; font-weight: 700;">ExpenseFlow</h2>
            <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Smart Personal Expense Tracking</p>
        </div>
        <div style="background: #f8fafc; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 24px; border: 1px dashed #cbd5e1;">
            <span style="font-size: 13px; color: #475569; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Verification Code</span>
            <div style="font-size: 36px; font-weight: 800; letter-spacing: 6px; color: #2563eb; margin: 12px 0;">{otp}</div>
            <p style="color: #64748b; font-size: 13px; margin: 0;">Valid for 10 minutes</p>
        </div>
        <p style="color: #334155; font-size: 14px; line-height: 1.5; margin: 0 0 16px 0;">
            Enter this 6-digit code on the registration screen to verify your email address and activate your account.
        </p>
        <p style="color: #94a3b8; font-size: 12px; line-height: 1.4; margin: 0; border-top: 1px solid #f1f5f9; padding-top: 16px;">
            If you did not attempt to register on ExpenseFlow, you can safely ignore this email.
        </p>
    </div>
    """

    if RESEND_API_KEY:
        try:
            resend.api_key = RESEND_API_KEY
            params = {
                "from": RESEND_FROM_EMAIL,
                "to": [receiver_email],
                "subject": subject,
                "text": plain_text,
                "html": html_content,
            }
            resp = resend.Emails.send(params)
            email_id = getattr(resp, "id", None) or (resp.get("id") if isinstance(resp, dict) else str(resp))
            app.logger.info("OTP verification email sent via Resend HTTPS API. ID: %s", email_id)
            return
        except Exception as exc:
            app.logger.error("Resend API delivery error in send_otp_email: %s", format_resend_error(exc))
            raise

    # Fallback to Gmail SMTP if RESEND_API_KEY is not configured
    if not MAIL_EMAIL or not MAIL_PASSWORD:
        app.logger.error("Email Config Error: Neither RESEND_API_KEY nor MAIL_EMAIL/MAIL_PASSWORD is configured.")
        raise smtplib.SMTPException("Email delivery service is not configured.")

    email_message = f"Subject: {subject}\n\n{plain_text}"
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls()
            server.login(
                MAIL_EMAIL,
                MAIL_PASSWORD
            )
            server.sendmail(
                MAIL_EMAIL,
                receiver_email,
                email_message
            )
    except Exception as exc:
        app.logger.error("SMTP error in send_otp_email: %s: %s", type(exc).__name__, exc)
        raise


def send_password_reset_otp_email(receiver_email, otp):
    subject = "Your ExpenseFlow Password Reset Code"
    plain_text = f"""Hello,

Your ExpenseFlow password reset code is:

{otp}

This code expires in {RESET_OTP_EXPIRY_MINUTES} minutes.
If you did not request a password reset, you can safely ignore this email.

Regards,
ExpenseFlow Team
"""
    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 24px; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #0f172a; margin: 0; font-size: 22px; font-weight: 700;">ExpenseFlow</h2>
            <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Password Reset Request</p>
        </div>
        <div style="background: #f8fafc; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 24px; border: 1px dashed #cbd5e1;">
            <span style="font-size: 13px; color: #475569; text-transform: uppercase; letter-spacing: 1px; font-weight: 600;">Reset Code</span>
            <div style="font-size: 36px; font-weight: 800; letter-spacing: 6px; color: #dc2626; margin: 12px 0;">{otp}</div>
            <p style="color: #64748b; font-size: 13px; margin: 0;">Expires in {RESET_OTP_EXPIRY_MINUTES} minutes</p>
        </div>
        <p style="color: #334155; font-size: 14px; line-height: 1.5; margin: 0 0 16px 0;">
            Use this code to reset your account password. If you did not request a password reset, you can safely ignore this email.
        </p>
        <p style="color: #94a3b8; font-size: 12px; line-height: 1.4; margin: 0; border-top: 1px solid #f1f5f9; padding-top: 16px;">
            If you did not request a password reset, you can safely ignore this email.
        </p>
    </div>
    """

    if RESEND_API_KEY:
        try:
            resend.api_key = RESEND_API_KEY
            params = {
                "from": RESEND_FROM_EMAIL,
                "to": [receiver_email],
                "subject": subject,
                "text": plain_text,
                "html": html_content,
            }
            resp = resend.Emails.send(params)
            email_id = getattr(resp, "id", None) or (resp.get("id") if isinstance(resp, dict) else str(resp))
            app.logger.info("Password reset OTP email sent via Resend HTTPS API. ID: %s", email_id)
            return
        except Exception as exc:
            app.logger.error("Resend API delivery error in send_password_reset_otp_email: %s", format_resend_error(exc))
            raise

    # Fallback to Gmail SMTP if RESEND_API_KEY is not configured
    if not MAIL_EMAIL or not MAIL_PASSWORD:
        app.logger.error("Email Config Error: Neither RESEND_API_KEY nor MAIL_EMAIL/MAIL_PASSWORD is configured.")
        raise smtplib.SMTPException("Email delivery service is not configured.")

    email_message = f"Subject: {subject}\n\n{plain_text}"
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.starttls()
            server.login(MAIL_EMAIL, MAIL_PASSWORD)
            server.sendmail(MAIL_EMAIL, receiver_email, email_message)
    except Exception as exc:
        app.logger.error("SMTP error in send_password_reset_otp_email: %s: %s", type(exc).__name__, exc)
        raise


# -----------------------------------
# MYSQL CONNECTION & INITIALIZATION
# -----------------------------------

def get_db_connection_params():
    """Build database connection parameters supporting local .env and Railway MySQL."""
    database_url = os.getenv("MYSQL_URL") or os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("mysql"):
        parsed = urlparse.urlparse(database_url)
        return {
            "host": parsed.hostname or "localhost",
            "port": int(parsed.port or 3306),
            "user": parsed.username or None,
            "password": parsed.password or None,
            "database": parsed.path.lstrip("/") or None,
            "autocommit": False,
            "connection_timeout": 10,
        }
    return {
        "host": os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or "localhost",
        "port": int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT") or 3306),
        "user": os.getenv("DB_USER") or os.getenv("MYSQLUSER"),
        "password": os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD"),
        "database": os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE"),
        "autocommit": False,
        "connection_timeout": 10,
    }


db = mysql.connector.connect(**get_db_connection_params())


def ensure_db_connection():
    """Reconnect to MySQL if the connection has been lost (e.g. idle timeout)."""
    global db
    try:
        db.ping(reconnect=True, attempts=3, delay=1)
    except mysql.connector.Error:
        db = mysql.connector.connect(**get_db_connection_params())


def initialize_tracker_tables():
    """Create all required tables in order, ensuring users exists before foreign keys."""
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password VARCHAR(255) NULL,
            google_id VARCHAR(255) NULL,
            auth_provider VARCHAR(50) NOT NULL DEFAULT 'local',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_users_google_id (google_id)
        )
    """)

    # Backward-compatible migrations for existing users table
    cursor.execute("SHOW COLUMNS FROM users LIKE 'google_id'")
    if not cursor.fetchone():
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN google_id VARCHAR(255) NULL AFTER password")
            cursor.execute("ALTER TABLE users ADD INDEX idx_users_google_id (google_id)")
        except Exception as mig_err:
            app.logger.warning("Migration note for google_id: %s", mig_err)

    cursor.execute("SHOW COLUMNS FROM users LIKE 'auth_provider'")
    if not cursor.fetchone():
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(50) NOT NULL DEFAULT 'local' AFTER google_id")
        except Exception as mig_err:
            app.logger.warning("Migration note for auth_provider: %s", mig_err)

    try:
        cursor.execute("ALTER TABLE users MODIFY COLUMN password VARCHAR(255) NULL")
    except Exception as mig_err:
        app.logger.warning("Migration note for password column: %s", mig_err)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            amount DECIMAL(12, 2) NOT NULL,
            category VARCHAR(50) NOT NULL,
            expense_date DATE NOT NULL,
            payment_method VARCHAR(50) NOT NULL,
            description VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT fk_expenses_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_expenses_user_date (user_id, expense_date),
            INDEX idx_expenses_user_category (user_id, category)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            budget_amount DECIMAL(12, 2) NOT NULL,
            month TINYINT NOT NULL,
            year SMALLINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT fk_budgets_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE KEY unique_user_month_budget (user_id, month, year)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(120) NOT NULL,
            message VARCHAR(255) NOT NULL,
            is_read BOOLEAN DEFAULT FALSE,
            action_url VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_notifications_user_read (user_id, is_read, created_at)
        )
    """)
    db.commit()
    cursor.close()


initialize_tracker_tables()


# -----------------------------------
# SECURITY MIDDLEWARE & CONTEXT HOOKS
# -----------------------------------

@app.before_request
def csrf_protect():
    ensure_db_connection()
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)

    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        if app.config.get("TESTING") and not app.config.get("WTF_CSRF_ENABLED", False):
            return None

        token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
        expected = session.get("csrf_token")

        if not token or not expected or not hmac.compare_digest(str(token), str(expected)):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                return {"error": "Invalid or expired CSRF token"}, 400
            flash("Session expired or invalid CSRF token. Please try again.", "error")
            return render_template("error.html", title="CSRF Verification Failed", message="Invalid or missing CSRF token. Please refresh and try again."), 400


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.context_processor
def inject_global_context():
    def get_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return session["csrf_token"]

    user_id = session.get("user_id")
    user_notifications = []
    unread_notification_count = 0

    if user_id:
        try:
            generate_user_notifications(user_id)
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT 8",
                (user_id,)
            )
            user_notifications = cursor.fetchall()
            cursor.execute(
                "SELECT COUNT(*) AS count FROM notifications WHERE user_id = %s AND is_read = FALSE",
                (user_id,)
            )
            unread_notification_count = cursor.fetchone()["count"]
            cursor.close()
        except Exception:
            pass

    return {
        "csrf_token": get_csrf_token,
        "user_notifications": user_notifications,
        "unread_notification_count": unread_notification_count,
    }


# -----------------------------------
# AUTHENTICATION HELPERS
# -----------------------------------

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access your dashboard.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def get_active_password_reset_request():
    """Return the active reset request for this browser, if it is still valid."""
    reset_token = session.get("password_reset_token")
    reset_request = password_reset_requests.get(reset_token)

    if not reset_request:
        return None

    if datetime.now(timezone.utc) > reset_request["expires_at"]:
        password_reset_requests.pop(reset_token, None)
        session.pop("password_reset_token", None)
        return None

    return reset_request


def clear_password_reset_request():
    reset_token = session.pop("password_reset_token", None)
    if reset_token:
        password_reset_requests.pop(reset_token, None)


@app.template_filter("inr")
def format_inr(value):
    amount = Decimal(value or 0)
    return f"₹{amount:,.2f}"


def current_user_id():
    return session["user_id"]


def month_bounds(selected_date=None):
    selected_date = selected_date or date.today()
    start = selected_date.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def get_monthly_budget(user_id, selected_date=None):
    selected_date = selected_date or date.today()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT budget_amount FROM budgets WHERE user_id = %s AND month = %s AND year = %s",
        (user_id, selected_date.month, selected_date.year),
    )
    budget = cursor.fetchone()
    cursor.close()
    return Decimal(budget["budget_amount"]) if budget else Decimal("0")


def parse_expense_form(form):
    try:
        amount = Decimal(form.get("amount", "").strip())
    except (InvalidOperation, AttributeError):
        return None, "Enter a valid amount."

    if amount <= 0:
        return None, "Amount must be greater than zero."
    if amount.as_tuple().exponent < -2:
        return None, "Amount can have at most two decimal places."

    category = form.get("category", "")
    payment_method = form.get("payment_method", "")
    description = form.get("description", "").strip()
    date_text = form.get("expense_date", "")

    if category not in CATEGORIES:
        return None, "Choose a valid category."
    if payment_method not in PAYMENT_METHODS:
        return None, "Choose a valid payment method."
    if len(description) > 255:
        return None, "Description must be 255 characters or fewer."

    try:
        expense_date = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        return None, "Choose a valid expense date."

    return {
        "amount": amount,
        "category": category,
        "expense_date": expense_date,
        "payment_method": payment_method,
        "description": description or None,
    }, None


def get_owned_expense(expense_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM expenses WHERE id = %s AND user_id = %s",
        (expense_id, current_user_id()),
    )
    expense = cursor.fetchone()
    cursor.close()
    return expense


# -----------------------------------
# HOME PAGE
# -----------------------------------

@app.route("/")
def home():
    return render_template("home.html")


# -----------------------------------
# REGISTRATION
# -----------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]


        # -----------------------------------
        # PASSWORD VALIDATION
        # -----------------------------------

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        if not re.search(r"[A-Za-z]", password):
            flash("Password must contain at least one letter.", "error")
            return render_template("register.html")

        if not re.search(r"[0-9]", password):
            flash("Password must contain at least one number.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")


        # -----------------------------------
        # CHECK EMAIL
        # -----------------------------------

        cursor = db.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email = %s",
            (email,)
        )

        existing_user = cursor.fetchone()

        cursor.close()


        if existing_user:
            flash("An account with this email already exists. Please log in instead.", "error")
            return render_template("register.html")


        # -----------------------------------
        # HASH PASSWORD
        # -----------------------------------

        hashed_password = generate_password_hash(password)


        # -----------------------------------
        # GENERATE OTP
        # -----------------------------------

        otp = str(secrets.randbelow(900000) + 100000)


        # -----------------------------------
        # STORE TEMPORARY REGISTRATION
        # -----------------------------------

        pending_registrations[email] = {
            "name": name,
            "password": hashed_password,
            "otp": otp,
            "expires_at": datetime.now(timezone.utc) + timedelta(
                minutes=REGISTRATION_OTP_EXPIRY_MINUTES
            ),
            "attempts": 0,
        }


        # -----------------------------------
        # SEND OTP
        # -----------------------------------

        try:
            send_otp_email(email, otp)
        except Exception as err:
            app.logger.error("Registration OTP dispatch error: %s", format_resend_error(err))
            pending_registrations.pop(email, None)
            flash(format_resend_user_error(err), "error")
            return render_template("register.html")

        # -----------------------------------
        # OPEN OTP PAGE
        # -----------------------------------

        return render_template(
            "verify_otp.html",
            email=email
        )

    return render_template("register.html")


# -----------------------------------
# VERIFY OTP
# -----------------------------------

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    email = request.args.get("email", "").strip().lower()

    # Check registration exists
    if not email or email not in pending_registrations:
        flash("Registration session expired or invalid. Please register again.", "error")
        return redirect(url_for("register"))

    registration = pending_registrations[email]

    # Check OTP expiration
    if datetime.now(timezone.utc) > registration["expires_at"]:
        pending_registrations.pop(email, None)
        flash("Your verification code has expired. Please register again.", "error")
        return redirect(url_for("register"))

    if request.method == "POST":
        otp_entered = request.form.get("otp", "").strip()

        # Check maximum attempts
        if registration["attempts"] >= REGISTRATION_OTP_MAX_ATTEMPTS:
            pending_registrations.pop(email, None)
            flash("Too many incorrect codes. Please register again.", "error")
            return redirect(url_for("register"))

        # Check OTP
        if otp_entered != registration["otp"]:
            registration["attempts"] += 1
            remaining_attempts = REGISTRATION_OTP_MAX_ATTEMPTS - registration["attempts"]

            if remaining_attempts <= 0:
                pending_registrations.pop(email, None)
                flash("Too many incorrect codes. Please register again.", "error")
                return redirect(url_for("register"))

            flash(f"Incorrect OTP. {remaining_attempts} attempt(s) remaining.", "error")
            return render_template("verify_otp.html", email=email)

        # -----------------------------------
        # OTP CORRECT - CREATE ACCOUNT
        # -----------------------------------

        cursor = db.cursor()
        cursor.execute(
            """
            INSERT INTO users (name, email, password)
            VALUES (%s, %s, %s)
            """,
            (
                registration["name"],
                email,
                registration["password"]
            )
        )
        db.commit()
        user_id = cursor.lastrowid
        cursor.close()

        # Remove temporary registration
        del pending_registrations[email]

        # Start a logged-in session for the newly verified user.
        session.clear()
        session.permanent = True
        session["user_id"] = user_id
        session["user_name"] = registration["name"]
        session["user_email"] = email

        flash("Account created successfully. Welcome to ExpenseFlow!", "success")
        return redirect(url_for("dashboard"))

    return render_template("verify_otp.html", email=email)


# -----------------------------------
# RESEND OTP
# -----------------------------------

@app.route("/resend-otp", methods=["GET", "POST"])
def resend_otp():
    email = (request.args.get("email") or request.form.get("email", "")).strip().lower()

    if not email or email not in pending_registrations:
        flash("Registration session expired or invalid. Please register again.", "error")
        return redirect(url_for("register"))

    new_otp = str(secrets.randbelow(900000) + 100000)
    pending_registrations[email]["otp"] = new_otp
    pending_registrations[email]["expires_at"] = datetime.now(timezone.utc) + timedelta(
        minutes=REGISTRATION_OTP_EXPIRY_MINUTES
    )
    pending_registrations[email]["attempts"] = 0

    try:
        send_otp_email(email, new_otp)
        flash("A new verification code has been sent to your email.", "success")
    except Exception as err:
        app.logger.error("Resend OTP dispatch error: %s", format_resend_error(err))
        flash(format_resend_user_error(err), "error")

    return redirect(url_for("verify_otp", email=email))


# -----------------------------------
# GOOGLE OAUTH AUTHENTICATION
# -----------------------------------

def get_google_redirect_uri():
    """Build the OAuth redirect URI, prioritizing environment override or public production domain."""
    if GOOGLE_REDIRECT_URI:
        return GOOGLE_REDIRECT_URI
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")
    if railway_domain:
        return f"https://{railway_domain}/login/google/callback"
    return url_for("google_callback", _external=True)


@app.route("/login/google")
def google_login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        app.logger.warning("Google Sign-In attempted but GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is missing.")
        flash("Google Sign-In is not currently configured. Please check server settings.", "error")
        return redirect(url_for("login"))

    oauth_state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = oauth_state

    redirect_uri = get_google_redirect_uri()
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": oauth_state,
        "access_type": "online",
        "prompt": "select_account",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlparse.urlencode(params)}"
    return redirect(auth_url)


@app.route("/login/google/callback")
def google_callback():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    # 1. Check for user cancellation or Google error
    error = request.args.get("error")
    if error:
        app.logger.info("Google OAuth returned error or user cancelled: %s", error)
        flash("Google Sign-In was cancelled or denied.", "error")
        return redirect(url_for("login"))

    # 2. Validate OAuth state parameter
    state = request.args.get("state")
    expected_state = session.pop("google_oauth_state", None)
    if not state or not expected_state or not hmac.compare_digest(str(state), str(expected_state)):
        app.logger.warning("Google OAuth state verification mismatch.")
        flash("Authentication failed: invalid session state. Please try again.", "error")
        return redirect(url_for("login"))

    # 3. Verify code presence
    code = request.args.get("code")
    if not code:
        flash("Authorization code missing from Google. Please try again.", "error")
        return redirect(url_for("login"))

    # 4. Exchange code for access token via secure server-to-server POST
    redirect_uri = get_google_redirect_uri()
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        token_resp = requests.post(token_url, data=token_data, timeout=10)
        token_json = token_resp.json()
    except Exception as exc:
        app.logger.error("Failed to connect to Google token exchange endpoint: %s", type(exc).__name__)
        flash("Could not connect to Google authentication service. Please try again.", "error")
        return redirect(url_for("login"))

    if token_resp.status_code != 200 or "access_token" not in token_json:
        app.logger.error("Google token exchange failed with HTTP status %s", token_resp.status_code)
        flash("Failed to authenticate with Google. Please try again.", "error")
        return redirect(url_for("login"))

    access_token = token_json["access_token"]

    # 5. Retrieve verified identity from Google UserInfo endpoint
    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    try:
        userinfo_resp = requests.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        userinfo = userinfo_resp.json()
    except Exception as exc:
        app.logger.error("Failed to connect to Google userinfo endpoint: %s", type(exc).__name__)
        flash("Could not retrieve user profile from Google. Please try again.", "error")
        return redirect(url_for("login"))

    if userinfo_resp.status_code != 200:
        app.logger.error("Google userinfo request failed with HTTP status %s", userinfo_resp.status_code)
        flash("Failed to retrieve your Google profile. Please try again.", "error")
        return redirect(url_for("login"))

    google_id = str(userinfo.get("sub", "")).strip()
    email = str(userinfo.get("email", "")).strip().lower()
    email_verified = userinfo.get("email_verified", False)
    is_verified = (email_verified is True or str(email_verified).lower() == "true")
    name = str(userinfo.get("name") or email.split("@")[0]).strip()[:100]

    if not email:
        flash("Google did not return a valid email address. Please check your account permissions.", "error")
        return redirect(url_for("login"))

    if not is_verified:
        flash("Your Google email address is not verified by Google. Please verify your email with Google first.", "error")
        return redirect(url_for("login"))

    # 6. Check whether google_id already exists in the database
    user_by_google_id = None
    if google_id:
        try:
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, name, email, password, auth_provider, google_id FROM users WHERE google_id = %s",
                (google_id,),
            )
            user_by_google_id = cursor.fetchone()
            cursor.close()
        except Exception as exc:
            app.logger.error("Database error querying user by google_id: %s", type(exc).__name__)
            flash("A database error occurred. Please try again.", "error")
            return redirect(url_for("login"))

    if user_by_google_id:
        session.clear()
        session.permanent = True
        session["user_id"] = user_by_google_id["id"]
        session["user_name"] = user_by_google_id["name"]
        session["user_email"] = user_by_google_id["email"]
        flash(f"Welcome back, {user_by_google_id['name']}!", "success")
        return redirect(url_for("dashboard"))

    # 7. Check whether the email already exists in the database
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, name, email, password, auth_provider, google_id FROM users WHERE email = %s",
            (email,),
        )
        existing_email_user = cursor.fetchone()
        cursor.close()
    except Exception as exc:
        app.logger.error("Database error querying user by email: %s", type(exc).__name__)
        flash("A database error occurred. Please try again.", "error")
        return redirect(url_for("login"))

    if existing_email_user:
        # CASE A & B: Email exists - safely link Google authentication to existing account
        try:
            update_cursor = db.cursor()
            update_cursor.execute(
                "UPDATE users SET google_id = %s, auth_provider = 'google' WHERE id = %s",
                (google_id, existing_email_user["id"]),
            )
            db.commit()
            update_cursor.close()
        except Exception as exc:
            app.logger.error("Database error linking Google account: %s", type(exc).__name__)

        session.clear()
        session.permanent = True
        session["user_id"] = existing_email_user["id"]
        session["user_name"] = existing_email_user["name"]
        session["user_email"] = existing_email_user["email"]

        if existing_email_user.get("google_id"):
            flash(f"Welcome back, {existing_email_user['name']}!", "success")
        else:
            flash("Your Google account has been securely linked. Welcome to ExpenseFlow!", "success")
        return redirect(url_for("dashboard"))

    # CASE C: Email does not exist - create new Google account (no password required)
    random_pw_hash = generate_password_hash(secrets.token_urlsafe(32))
    try:
        insert_cursor = db.cursor()
        insert_cursor.execute(
            """
            INSERT INTO users (name, email, password, google_id, auth_provider)
            VALUES (%s, %s, %s, %s, 'google')
            """,
            (name, email, random_pw_hash, google_id or None),
        )
        db.commit()
        user_id = insert_cursor.lastrowid
        insert_cursor.close()
    except mysql.connector.Error as err:
        if err.errno == 1062 or "Duplicate entry" in str(err):
            flash("An account with this email already exists. Please log in instead.", "error")
            return redirect(url_for("login"))
        app.logger.error("Database error inserting new Google user: %s", type(err).__name__)
        flash("Could not create account. Please try again.", "error")
        return redirect(url_for("register"))

    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    session["user_name"] = name
    session["user_email"] = email

    flash("Account created successfully with Google. Welcome to ExpenseFlow!", "success")
    return redirect(url_for("dashboard"))


# -----------------------------------
# LOGIN / LOGOUT
# -----------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, name, email, password, auth_provider, google_id FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()
        cursor.close()

        if not user or not user["password"] or not check_password_hash(user["password"], password):
            if user and user.get("google_id"):
                flash("This account uses Google sign-in. Please continue with Google.", "error")
            else:
                flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")




# -----------------------------------
# PASSWORD RESET
# -----------------------------------

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()

        # Always show the same message so an email address cannot be confirmed.
        success_message = (
            "If an account exists for that email, a password reset code has been sent."
        )

        clear_password_reset_request()
        reset_token = secrets.token_urlsafe(32)
        otp = str(secrets.randbelow(900000) + 100000)

        # A reset state is created for every request to avoid exposing whether
        # an address belongs to an account. Only registered users receive email.
        password_reset_requests[reset_token] = {
            "user_id": user["id"] if user else None,
            "otp_hash": generate_password_hash(otp),
            "expires_at": datetime.now(timezone.utc) + timedelta(
                minutes=RESET_OTP_EXPIRY_MINUTES
            ),
            "attempts": 0,
            "verified": False,
        }
        session["password_reset_token"] = reset_token

        if user:
            try:
                send_password_reset_otp_email(user["email"], otp)
            except Exception as err:
                app.logger.error("Password reset OTP dispatch error: %s", format_resend_error(err))
                clear_password_reset_request()
                flash(format_resend_user_error(err), "error")
                return render_template("forgot_password.html")

        flash(success_message, "success")
        return redirect(url_for("verify_reset_otp"))

    return render_template("forgot_password.html")


@app.route("/verify-reset-otp", methods=["GET", "POST"])
def verify_reset_otp():
    reset_request = get_active_password_reset_request()
    if not reset_request:
        flash("Your password reset request is invalid or has expired. Please try again.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        otp_entered = request.form["otp"].strip()

        if reset_request["attempts"] >= RESET_OTP_MAX_ATTEMPTS:
            clear_password_reset_request()
            flash("Too many incorrect codes. Please request a new password reset code.", "error")
            return redirect(url_for("forgot_password"))

        if not check_password_hash(reset_request["otp_hash"], otp_entered):
            reset_request["attempts"] += 1
            remaining_attempts = RESET_OTP_MAX_ATTEMPTS - reset_request["attempts"]

            if remaining_attempts == 0:
                clear_password_reset_request()
                flash("Too many incorrect codes. Please request a new password reset code.", "error")
                return redirect(url_for("forgot_password"))

            flash(
                f"Incorrect code. {remaining_attempts} attempt(s) remaining.",
                "error",
            )
            return render_template("verify_reset_otp.html")

        reset_request["verified"] = True
        flash("Code verified. Please create your new password.", "success")
        return redirect(url_for("reset_password"))

    return render_template("verify_reset_otp.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    reset_request = get_active_password_reset_request()
    if not reset_request or not reset_request["verified"]:
        flash("Please verify a valid password reset code first.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("reset_password.html")

        if not re.search(r"[A-Za-z]", password):
            flash("Password must contain at least one letter.", "error")
            return render_template("reset_password.html")

        if not re.search(r"[0-9]", password):
            flash("Password must contain at least one number.", "error")
            return render_template("reset_password.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html")

        cursor = db.cursor()
        cursor.execute(
            "UPDATE users SET password = %s WHERE id = %s",
            (generate_password_hash(password), reset_request["user_id"]),
        )
        db.commit()
        cursor.close()

        clear_password_reset_request()
        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("home"))


# -----------------------------------
# DASHBOARD & FINANCIAL INSIGHTS
# -----------------------------------

def get_financial_insights(user_id, selected_date=None):
    selected_date = selected_date or date.today()
    curr_start, next_month = month_bounds(selected_date)
    prev_month_date = (curr_start - timedelta(days=1)).replace(day=1)
    prev_start, prev_next = month_bounds(prev_month_date)

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS count FROM expenses WHERE user_id = %s", (user_id,))
    total_lifetime_count = cursor.fetchone()["count"]

    cursor.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s",
        (user_id, curr_start, next_month),
    )
    curr_data = cursor.fetchone()
    curr_total = Decimal(curr_data["total"])

    cursor.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s",
        (user_id, prev_start, prev_next),
    )
    prev_data = cursor.fetchone()
    prev_total = Decimal(prev_data["total"])

    cursor.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date = %s",
        (user_id, selected_date),
    )
    today_data = cursor.fetchone()
    today_total = Decimal(today_data["total"])
    today_count = today_data["count"]

    cursor.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s "
        "GROUP BY category ORDER BY total DESC LIMIT 1",
        (user_id, curr_start, next_month),
    )
    top_cat = cursor.fetchone()
    cursor.close()

    budget = get_monthly_budget(user_id, selected_date)
    prev_month_name = prev_month_date.strftime("%B")
    curr_month_name = selected_date.strftime("%B")

    insights = []

    # 1. Monthly Spending Comparison
    if curr_total == 0 and prev_total == 0:
        comp_text = f"No expenses recorded in {curr_month_name} or {prev_month_name} yet."
        comp_type = "neutral"
        comp_badge = "No Activity"
        comp_icon = "fa-solid fa-calendar-check"
    elif prev_total == 0 and curr_total > 0:
        comp_text = f"You have spent ₹{curr_total:,.2f} this month. (No spending was recorded in {prev_month_name})."
        comp_type = "blue"
        comp_badge = "Active Tracking"
        comp_icon = "fa-solid fa-chart-line"
    elif curr_total > prev_total:
        diff = curr_total - prev_total
        pct = (diff / prev_total * 100) if prev_total else Decimal("0")
        comp_text = f"You spent ₹{diff:,.2f} more than last month ({prev_month_name}) — an increase of {pct:.0f}%."
        comp_type = "rose"
        comp_badge = f"+{pct:.0f}% vs Last Month"
        comp_icon = "fa-solid fa-arrow-trend-up"
    elif curr_total < prev_total:
        diff = prev_total - curr_total
        pct = (diff / prev_total * 100) if prev_total else Decimal("0")
        comp_text = f"You spent ₹{diff:,.2f} less than last month ({prev_month_name}) — saving {pct:.0f}% so far!"
        comp_type = "emerald"
        comp_badge = f"-{pct:.0f}% Savings"
        comp_icon = "fa-solid fa-arrow-trend-down"
    else:
        comp_text = f"Your current spending matches {prev_month_name} exactly at ₹{curr_total:,.2f}."
        comp_type = "cyan"
        comp_badge = "Equal Pace"
        comp_icon = "fa-solid fa-equals"

    insights.append({
        "id": "monthly_comparison",
        "title": "Monthly Trend",
        "text": comp_text,
        "type": comp_type,
        "badge": comp_badge,
        "icon": comp_icon,
    })

    # 2. Highest Spending Category
    if top_cat and curr_total > 0:
        cat_name = top_cat["category"]
        cat_total = Decimal(top_cat["total"])
        cat_pct = (cat_total / curr_total * 100) if curr_total else Decimal("0")
        cat_text = f"{cat_name} was your highest spending category this month at ₹{cat_total:,.2f} ({cat_pct:.0f}% of monthly spend)."
        cat_type = "purple"
        cat_badge = f"Top: {cat_name}"
        cat_icon = "fa-solid fa-shapes"
    else:
        cat_text = "No category spending recorded for this month yet."
        cat_type = "neutral"
        cat_badge = "No Data"
        cat_icon = "fa-solid fa-shapes"

    insights.append({
        "id": "top_category",
        "title": "Top Spending Category",
        "text": cat_text,
        "type": cat_type,
        "badge": cat_badge,
        "icon": cat_icon,
    })

    # 3. Budget Status Insight
    if budget > 0:
        used_pct = float(curr_total / budget * 100)
        remaining = budget - curr_total
        if curr_total > budget:
            over_amt = curr_total - budget
            budget_text = f"Your monthly budget has been exceeded by ₹{over_amt:,.2f} ({used_pct:.0f}% utilized). Review discretionary expenses."
            budget_type = "rose"
            budget_badge = "Budget Exceeded"
            budget_icon = "fa-solid fa-triangle-exclamation"
        elif used_pct >= 80:
            budget_text = f"You have used {used_pct:.0f}% of your monthly budget. You are approaching your limit with ₹{remaining:,.2f} remaining."
            budget_type = "amber"
            budget_badge = f"{used_pct:.0f}% Utilized"
            budget_icon = "fa-solid fa-circle-exclamation"
        else:
            budget_text = f"You have used {used_pct:.0f}% of your monthly budget. Safe and on track with ₹{remaining:,.2f} remaining."
            budget_type = "emerald"
            budget_badge = f"On Track ({used_pct:.0f}%)"
            budget_icon = "fa-solid fa-shield-halved"
    else:
        budget_text = "No monthly budget limit configured for this month. Set a budget to track savings goals."
        budget_type = "neutral"
        budget_badge = "Not Set"
        budget_icon = "fa-solid fa-wallet"

    insights.append({
        "id": "budget_status",
        "title": "Budget Health",
        "text": budget_text,
        "type": budget_type,
        "badge": budget_badge,
        "icon": budget_icon,
    })

    # 4. Daily Spending Insight
    if today_count > 0:
        daily_text = f"You spent ₹{today_total:,.2f} across {today_count} transaction{'s' if today_count > 1 else ''} today."
        daily_type = "cyan"
        daily_badge = f"₹{today_total:,.2f} Today"
        daily_icon = "fa-solid fa-clock"
    else:
        daily_text = "No expenses recorded today. Zero spend recorded so far!"
        daily_type = "neutral"
        daily_badge = "₹0.00 Today"
        daily_icon = "fa-solid fa-check-double"

    insights.append({
        "id": "daily_spending",
        "title": "Daily Spending",
        "text": daily_text,
        "type": daily_type,
        "badge": daily_badge,
        "icon": daily_icon,
    })

    return insights, total_lifetime_count


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = current_user_id()
    month_start, next_month = month_bounds()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s",
        (user_id, month_start, next_month),
    )
    monthly_expenses = Decimal(cursor.fetchone()["total"])
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date = %s",
        (user_id, date.today()),
    )
    today_expenses = Decimal(cursor.fetchone()["total"])
    cursor.execute("SELECT COUNT(*) AS count FROM expenses WHERE user_id = %s", (user_id,))
    expense_count = cursor.fetchone()["count"]
    cursor.execute(
        "SELECT id, amount, category, expense_date, payment_method, description "
        "FROM expenses WHERE user_id = %s ORDER BY expense_date DESC, id DESC LIMIT 5",
        (user_id,),
    )
    recent_expenses = cursor.fetchall()
    cursor.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s "
        "GROUP BY category ORDER BY total DESC",
        (user_id, month_start, next_month),
    )
    category_spending = cursor.fetchall()
    cursor.close()

    budget = get_monthly_budget(user_id)
    remaining = budget - monthly_expenses if budget else Decimal("0")
    budget_percentage = min(float(monthly_expenses / budget * 100), 100) if budget else 0
    budget_status = "normal"
    if budget and monthly_expenses > budget:
        budget_status = "over"
    elif budget and monthly_expenses / budget >= Decimal("0.8"):
        budget_status = "warning"

    financial_insights, total_lifetime_count = get_financial_insights(user_id)

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        monthly_expenses=monthly_expenses,
        today_expenses=today_expenses,
        budget=budget,
        remaining=remaining,
        budget_percentage=budget_percentage,
        budget_status=budget_status,
        expense_count=expense_count,
        recent_expenses=recent_expenses,
        category_spending=category_spending,
        financial_insights=financial_insights,
        total_lifetime_count=total_lifetime_count,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        expense, error = parse_expense_form(request.form)
        if error:
            flash(error, "error")
            return render_template(
                "expense_form.html", active_page="add_expense", expense=request.form,
                categories=CATEGORIES, payment_methods=PAYMENT_METHODS, form_title="Add expense",
            )
        try:
            cursor = db.cursor()
            cursor.execute(
                "INSERT INTO expenses (user_id, amount, category, expense_date, payment_method, description) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (current_user_id(), expense["amount"], expense["category"], expense["expense_date"],
                 expense["payment_method"], expense["description"]),
            )
            db.commit()
            cursor.close()
        except mysql.connector.Error:
            db.rollback()
            flash("Unable to save the expense. Please try again.", "error")
            return render_template(
                "expense_form.html", active_page="add_expense", expense=request.form,
                categories=CATEGORIES, payment_methods=PAYMENT_METHODS, form_title="Add expense",
            )
        flash("Expense added successfully.", "success")
        return redirect(url_for("expenses"))

    return render_template(
        "expense_form.html", active_page="add_expense", expense={"expense_date": date.today().isoformat()},
        categories=CATEGORIES, payment_methods=PAYMENT_METHODS, form_title="Add expense",
    )


# -----------------------------------
# NOTIFICATIONS ENGINE & ROUTES
# -----------------------------------

def generate_user_notifications(user_id):
    """Generate threshold-based smart notifications for user_id without duplicates."""
    today = date.today()
    curr_start, next_month = month_bounds(today)
    prev_month_date = (curr_start - timedelta(days=1)).replace(day=1)
    prev_start, prev_next = month_bounds(prev_month_date)

    cursor = db.cursor(dictionary=True)

    # 1. Current month spend
    cursor.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s",
        (user_id, curr_start, next_month),
    )
    curr_total = Decimal(cursor.fetchone()["total"])

    # 2. Monthly Budget
    budget = get_monthly_budget(user_id, today)

    # 3. Previous month spend
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s",
        (user_id, prev_start, prev_next),
    )
    prev_total = Decimal(cursor.fetchone()["total"])

    # Check existing notification types for this month to avoid duplicates
    cursor.execute(
        "SELECT type FROM notifications WHERE user_id = %s AND created_at >= %s",
        (user_id, curr_start),
    )
    existing_types = {row["type"] for row in cursor.fetchall()}

    new_notifs = []

    # Budget Alerts
    if budget > 0:
        used_pct = float(curr_total / budget * 100)
        remaining = budget - curr_total

        if curr_total > budget and "budget_exceeded" not in existing_types:
            over = curr_total - budget
            new_notifs.append((
                user_id,
                "budget_exceeded",
                "Budget Exceeded",
                f"Budget exceeded. You spent ₹{curr_total:,.2f} exceeding your ₹{budget:,.2f} budget by ₹{over:,.2f}.",
                "/budget"
            ))
        elif used_pct >= 90 and "budget_90" not in existing_types and "budget_exceeded" not in existing_types:
            new_notifs.append((
                user_id,
                "budget_90",
                "Critical Budget Warning",
                f"Warning: You are very close to your monthly budget limit ({used_pct:.0f}% used, ₹{remaining:,.2f} remaining).",
                "/budget"
            ))
        elif used_pct >= 80 and "budget_80" not in existing_types and "budget_90" not in existing_types and "budget_exceeded" not in existing_types:
            new_notifs.append((
                user_id,
                "budget_80",
                "Budget Alert (80%)",
                f"You have used 80% of your monthly budget ({used_pct:.0f}% utilized, ₹{remaining:,.2f} remaining).",
                "/budget"
            ))

    # Spending Spike Alert
    if prev_total >= Decimal("1000") and curr_total >= Decimal("1500") and curr_total > (prev_total * Decimal("1.5")) and "spending_spike" not in existing_types:
        spike_pct = ((curr_total - prev_total) / prev_total * 100)
        new_notifs.append((
            user_id,
            "spending_spike",
            "High Spending Detected",
            f"Unusually high spending detected: {spike_pct:.0f}% higher than last month. Review your transactions.",
            "/reports"
        ))

    # Large Single Expense Alert
    threshold = (budget * Decimal("0.4")) if budget > 0 else Decimal("5000.00")
    cursor.execute(
        "SELECT id, amount, category, expense_date FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s AND amount >= %s "
        "ORDER BY amount DESC LIMIT 1",
        (user_id, curr_start, next_month, threshold)
    )
    large_exp = cursor.fetchone()
    if large_exp and "large_expense" not in existing_types:
        new_notifs.append((
            user_id,
            "large_expense",
            "Large Expense Logged",
            f"A large single expense of ₹{Decimal(large_exp['amount']):,.2f} ({large_exp['category']}) was recorded.",
            "/expenses"
        ))

    for notif in new_notifs:
        cursor.execute(
            "INSERT INTO notifications (user_id, type, title, message, action_url, is_read) "
            "VALUES (%s, %s, %s, %s, %s, FALSE)",
            notif
        )
    if new_notifs:
        db.commit()

    cursor.close()


@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    cursor = db.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s",
        (notification_id, current_user_id())
    )
    db.commit()
    cursor.close()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return {"success": True}
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    cursor = db.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read = TRUE WHERE user_id = %s",
        (current_user_id(),)
    )
    db.commit()
    cursor.close()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return {"success": True}
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/notifications/<int:notification_id>/dismiss", methods=["POST"])
@login_required
def dismiss_notification(notification_id):
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM notifications WHERE id = %s AND user_id = %s",
        (notification_id, current_user_id())
    )
    db.commit()
    cursor.close()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return {"success": True}
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/expenses")
@login_required
def expenses():
    user_id = current_user_id()
    filters = {
        "search": request.args.get("search", "").strip(),
        "category": request.args.get("category", ""),
        "payment_method": request.args.get("payment_method", ""),
        "date_from": request.args.get("date_from", ""),
        "date_to": request.args.get("date_to", ""),
        "min_amount": request.args.get("min_amount", "").strip(),
        "max_amount": request.args.get("max_amount", "").strip(),
        "sort": request.args.get("sort", "newest"),
    }
    page = max(request.args.get("page", 1, type=int), 1)
    clauses, parameters = ["user_id = %s"], [user_id]

    if filters["search"]:
        clauses.append("(description LIKE %s OR category LIKE %s OR payment_method LIKE %s)")
        search_value = f"%{filters['search']}%"
        parameters.extend([search_value, search_value, search_value])
    if filters["category"] in CATEGORIES:
        clauses.append("category = %s")
        parameters.append(filters["category"])
    if filters["payment_method"] in PAYMENT_METHODS:
        clauses.append("payment_method = %s")
        parameters.append(filters["payment_method"])
    for field, operator in (("date_from", ">="), ("date_to", "<=")):
        if filters[field]:
            try:
                parsed = datetime.strptime(filters[field], "%Y-%m-%d").date()
                clauses.append(f"expense_date {operator} %s")
                parameters.append(parsed)
            except ValueError:
                filters[field] = ""
                flash("Invalid date filter was ignored.", "warning")

    if filters["min_amount"]:
        try:
            min_val = Decimal(filters["min_amount"])
            if min_val >= 0:
                clauses.append("amount >= %s")
                parameters.append(min_val)
            else:
                filters["min_amount"] = ""
        except (InvalidOperation, ValueError):
            filters["min_amount"] = ""
            flash("Invalid minimum amount was ignored.", "warning")

    if filters["max_amount"]:
        try:
            max_val = Decimal(filters["max_amount"])
            if max_val >= 0:
                clauses.append("amount <= %s")
                parameters.append(max_val)
            else:
                filters["max_amount"] = ""
        except (InvalidOperation, ValueError):
            filters["max_amount"] = ""
            flash("Invalid maximum amount was ignored.", "warning")

    order_by = {
        "newest": "expense_date DESC, id DESC",
        "oldest": "expense_date ASC, id ASC",
        "highest": "amount DESC, expense_date DESC",
        "lowest": "amount ASC, expense_date DESC",
    }.get(filters["sort"], "expense_date DESC, id DESC")
    where_clause = " AND ".join(clauses)
    cursor = db.cursor(dictionary=True)
    cursor.execute(f"SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total FROM expenses WHERE {where_clause}", parameters)
    summary = cursor.fetchone()
    cursor.execute(
        f"SELECT * FROM expenses WHERE {where_clause} ORDER BY {order_by} LIMIT %s OFFSET %s",
        parameters + [EXPENSES_PER_PAGE, (page - 1) * EXPENSES_PER_PAGE],
    )
    expense_rows = cursor.fetchall()
    cursor.close()
    total_pages = max((summary["count"] + EXPENSES_PER_PAGE - 1) // EXPENSES_PER_PAGE, 1)
    if page > total_pages:
        return redirect(url_for("expenses", **{**filters, "page": total_pages}))
    return render_template(
        "expenses.html", active_page="expenses", expenses=expense_rows, filters=filters,
        categories=CATEGORIES, payment_methods=PAYMENT_METHODS, total=Decimal(summary["total"]),
        total_count=summary["count"], page=page, total_pages=total_pages,
    )


@app.route("/expenses/export")
@login_required
def export_expenses():
    user_id = current_user_id()
    filters = {
        "search": request.args.get("search", "").strip(),
        "category": request.args.get("category", ""),
        "payment_method": request.args.get("payment_method", ""),
        "date_from": request.args.get("date_from", ""),
        "date_to": request.args.get("date_to", ""),
        "min_amount": request.args.get("min_amount", "").strip(),
        "max_amount": request.args.get("max_amount", "").strip(),
        "sort": request.args.get("sort", "newest"),
    }
    clauses, parameters = ["user_id = %s"], [user_id]

    if filters["search"]:
        clauses.append("(description LIKE %s OR category LIKE %s OR payment_method LIKE %s)")
        search_value = f"%{filters['search']}%"
        parameters.extend([search_value, search_value, search_value])
    if filters["category"] in CATEGORIES:
        clauses.append("category = %s")
        parameters.append(filters["category"])
    if filters["payment_method"] in PAYMENT_METHODS:
        clauses.append("payment_method = %s")
        parameters.append(filters["payment_method"])
    for field, operator in (("date_from", ">="), ("date_to", "<=")):
        if filters[field]:
            try:
                parsed = datetime.strptime(filters[field], "%Y-%m-%d").date()
                clauses.append(f"expense_date {operator} %s")
                parameters.append(parsed)
            except ValueError:
                pass

    if filters["min_amount"]:
        try:
            min_val = Decimal(filters["min_amount"])
            if min_val >= 0:
                clauses.append("amount >= %s")
                parameters.append(min_val)
        except (InvalidOperation, ValueError):
            pass

    if filters["max_amount"]:
        try:
            max_val = Decimal(filters["max_amount"])
            if max_val >= 0:
                clauses.append("amount <= %s")
                parameters.append(max_val)
        except (InvalidOperation, ValueError):
            pass

    order_by = {
        "newest": "expense_date DESC, id DESC",
        "oldest": "expense_date ASC, id ASC",
        "highest": "amount DESC, expense_date DESC",
        "lowest": "amount ASC, expense_date DESC",
    }.get(filters["sort"], "expense_date DESC, id DESC")
    where_clause = " AND ".join(clauses)

    cursor = db.cursor(dictionary=True)
    cursor.execute(
        f"SELECT expense_date, category, payment_method, description, amount "
        f"FROM expenses WHERE {where_clause} ORDER BY {order_by}",
        parameters,
    )
    rows = cursor.fetchall()
    cursor.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Payment Method", "Description", "Amount"])

    for row in rows:
        formatted_date = row["expense_date"].strftime("%Y-%m-%d") if isinstance(row["expense_date"], (date, datetime)) else str(row["expense_date"])
        writer.writerow([
            formatted_date,
            row["category"] or "",
            row["payment_method"] or "",
            row["description"] or "",
            f"{Decimal(row['amount']):.2f}",
        ])

    csv_data = output.getvalue()
    filename = f"ExpenseFlow_Expenses_{date.today().isoformat()}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    existing = get_owned_expense(expense_id)
    if not existing:
        flash("Expense not found.", "error")
        return redirect(url_for("expenses"))
    if request.method == "POST":
        expense, error = parse_expense_form(request.form)
        if error:
            flash(error, "error")
            return render_template("expense_form.html", active_page="expenses", expense=request.form,
                                   categories=CATEGORIES, payment_methods=PAYMENT_METHODS, form_title="Edit expense")
        cursor = db.cursor()
        cursor.execute(
            "UPDATE expenses SET amount = %s, category = %s, expense_date = %s, payment_method = %s, "
            "description = %s WHERE id = %s AND user_id = %s",
            (expense["amount"], expense["category"], expense["expense_date"], expense["payment_method"],
             expense["description"], expense_id, current_user_id()),
        )
        db.commit()
        cursor.close()
        flash("Expense updated successfully.", "success")
        return redirect(url_for("expenses"))
    return render_template("expense_form.html", active_page="expenses", expense=existing,
                           categories=CATEGORIES, payment_methods=PAYMENT_METHODS, form_title="Edit expense")


@app.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    cursor = db.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s", (expense_id, current_user_id()))
    db.commit()
    deleted = cursor.rowcount
    cursor.close()
    flash("Expense deleted successfully." if deleted else "Expense not found.", "success" if deleted else "error")
    return redirect(url_for("expenses"))


@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    user_id = current_user_id()
    today = date.today()
    if request.method == "POST":
        try:
            budget_amount = Decimal(request.form.get("budget_amount", "").strip())
            if budget_amount <= 0 or budget_amount.as_tuple().exponent < -2:
                raise InvalidOperation
        except (InvalidOperation, AttributeError):
            flash("Enter a valid monthly budget greater than zero.", "error")
            return redirect(url_for("budget"))
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO budgets (user_id, budget_amount, month, year) VALUES (%s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE budget_amount = VALUES(budget_amount)",
            (user_id, budget_amount, today.month, today.year),
        )
        db.commit()
        cursor.close()
        flash("Monthly budget saved successfully.", "success")
        return redirect(url_for("budget"))

    start, end = month_bounds(today)
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s",
        (user_id, start, end),
    )
    spent = Decimal(cursor.fetchone()["total"])
    cursor.close()
    budget_amount = get_monthly_budget(user_id, today)
    remaining = budget_amount - spent if budget_amount else Decimal("0")
    percentage = min(float(spent / budget_amount * 100), 100) if budget_amount else 0
    status = "normal"
    if budget_amount and spent > budget_amount:
        status = "over"
    elif budget_amount and spent / budget_amount >= Decimal("0.8"):
        status = "warning"
    return render_template(
        "budget.html", active_page="budget", budget=budget_amount, spent=spent, remaining=remaining,
        percentage=percentage, status=status, month_label=today.strftime("%B %Y"),
    )


@app.route("/reports")
@login_required
def reports():
    user_id = current_user_id()
    period = request.args.get("period", "current")
    today = date.today()
    if period == "previous":
        selected = (today.replace(day=1) - timedelta(days=1))
        start, end = month_bounds(selected)
    elif period == "custom":
        try:
            start = datetime.strptime(request.args.get("date_from", ""), "%Y-%m-%d").date()
            end = datetime.strptime(request.args.get("date_to", ""), "%Y-%m-%d").date() + timedelta(days=1)
            if end <= start:
                raise ValueError
        except ValueError:
            flash("Choose a valid custom date range.", "error")
            return redirect(url_for("reports"))
    else:
        period = "current"
        start, end = month_bounds(today)

    cursor = db.cursor(dictionary=True)
    date_parameters = (user_id, start, end)
    cursor.execute(
        "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = %s "
        "AND expense_date >= %s AND expense_date < %s GROUP BY category ORDER BY total DESC",
        date_parameters,
    )
    categories = cursor.fetchall()
    cursor.execute(
        "SELECT expense_date, SUM(amount) AS total FROM expenses WHERE user_id = %s "
        "AND expense_date >= %s AND expense_date < %s GROUP BY expense_date ORDER BY expense_date",
        date_parameters,
    )
    daily = cursor.fetchall()
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count FROM expenses "
        "WHERE user_id = %s AND expense_date >= %s AND expense_date < %s",
        date_parameters,
    )
    summary = cursor.fetchone()
    cursor.execute(
        "SELECT DATE_FORMAT(expense_date, '%Y-%m') AS month_key, "
        "DATE_FORMAT(expense_date, '%b %Y') AS month_label, SUM(amount) AS total "
        "FROM expenses WHERE user_id = %s AND expense_date >= DATE_SUB(%s, INTERVAL 5 MONTH) "
        "AND expense_date < %s GROUP BY month_key, month_label ORDER BY month_key",
        (user_id, end, end),
    )
    monthly = cursor.fetchall()
    cursor.close()
    category_chart = {"labels": [item["category"] for item in categories], "values": [float(item["total"]) for item in categories]}
    daily_chart = {"labels": [item["expense_date"].strftime("%d %b") for item in daily], "values": [float(item["total"]) for item in daily]}
    monthly_chart = {"labels": [item["month_label"] for item in monthly], "values": [float(item["total"]) for item in monthly]}
    return render_template(
        "reports.html", active_page="reports", period=period, date_from=start.isoformat(),
        date_to=(end - timedelta(days=1)).isoformat(), total=Decimal(summary["total"]),
        count=summary["count"], highest_category=categories[0] if categories else None,
        category_chart=category_chart, daily_chart=daily_chart, monthly_chart=monthly_chart,
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = current_user_id()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, password FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    if not user:
        session.clear()
        flash("Your account is no longer available. Please log in again.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "name":
            name = request.form.get("name", "").strip()
            if not 2 <= len(name) <= 120:
                flash("Name must be between 2 and 120 characters.", "error")
            else:
                cursor = db.cursor()
                cursor.execute("UPDATE users SET name = %s WHERE id = %s", (name, user_id))
                db.commit()
                cursor.close()
                session["user_name"] = name
                flash("Profile updated successfully.", "success")
            return redirect(url_for("profile"))
        if action == "password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            if not check_password_hash(user["password"], current_password):
                flash("Your current password is incorrect.", "error")
            elif len(new_password) < 8 or not re.search(r"[A-Za-z]", new_password) or not re.search(r"[0-9]", new_password):
                flash("New password must contain 8 characters, a letter, and a number.", "error")
            elif new_password != confirm_password:
                flash("New passwords do not match.", "error")
            else:
                cursor = db.cursor()
                cursor.execute("UPDATE users SET password = %s WHERE id = %s", (generate_password_hash(new_password), user_id))
                db.commit()
                cursor.close()
                flash("Password changed successfully.", "success")
            return redirect(url_for("profile"))
    return render_template("profile.html", active_page="profile", user=user)


@app.errorhandler(404)
def not_found_error(error):
    return render_template("error.html", title="Page not found", message="The page you requested could not be found."), 404


@app.errorhandler(500)
def internal_error(error):
    try:
        db.rollback()
    except mysql.connector.Error:
        pass
    return render_template("error.html", title="Something went wrong", message="Please try again in a moment."), 500


# -----------------------------------
# TEST DATABASE & SMTP
# -----------------------------------

@app.route("/test-db")
def test_db():

    return "Database connected successfully!"


@app.route("/test-email")
@app.route("/test-smtp")
def test_email():
    if RESEND_API_KEY:
        # Diagnostic check for obviously truncated or masked placeholder keys
        if len(RESEND_API_KEY) < 20 or RESEND_API_KEY.endswith(".."):
            err_msg = (
                f"RESEND_API_KEY appears to be a truncated or masked preview ({len(RESEND_API_KEY)} chars, ending with '..'). "
                "Resend API keys are ~36 characters long and start with 're_'. "
                "Please copy the full API key generated in the Resend dashboard dialog and configure it in Railway."
            )
            app.logger.error("Resend API Key Error: %s", err_msg)
            return f"Resend API Configuration Error: {err_msg}", 500

        to_email = request.args.get("to", "").strip().lower()
        if to_email:
            try:
                resend.api_key = RESEND_API_KEY
                params = {
                    "from": RESEND_FROM_EMAIL,
                    "to": [to_email],
                    "subject": "ExpenseFlow Diagnostic Test Email",
                    "text": "Hello, this is a diagnostic test email from ExpenseFlow via Resend HTTPS API.",
                    "html": "<p>Hello,<br><br>This is a diagnostic test email from <strong>ExpenseFlow</strong> via Resend HTTPS API.</p>",
                }
                resp = resend.Emails.send(params)
                email_id = getattr(resp, "id", None) or (resp.get("id") if isinstance(resp, dict) else str(resp))
                app.logger.info("Diagnostic test email delivered to %s: ID %s", to_email, email_id)
                return (
                    f"Resend Test Email SUCCESS! Sent from '{RESEND_FROM_EMAIL}' to '{to_email}'. "
                    f"Resend Email ID: {email_id}",
                    200,
                )
            except Exception as exc:
                formatted_err = format_resend_error(exc)
                app.logger.error("Resend Test Email Dispatch Failure: %s", formatted_err)
                return f"Resend Test Email FAILED ({formatted_err})", 500

        # Live probe when no ?to parameter is provided
        try:
            resend.api_key = RESEND_API_KEY
            dom_summary = "API key active with sending permissions."
            try:
                domains_resp = resend.Domains.list()
                if domains_resp:
                    dom_list = domains_resp.get("data", []) if isinstance(domains_resp, dict) else getattr(domains_resp, "data", [])
                    dom_names = [d.get("name", "") if isinstance(d, dict) else getattr(d, "name", "") for d in dom_list]
                    if dom_names:
                        dom_summary = f"Configured domain(s): {', '.join(dom_names)}"
            except Exception as dom_exc:
                err_code = getattr(dom_exc, "code", None)
                err_msg_lower = getattr(dom_exc, "message", str(dom_exc)).lower()
                if err_code in (401, "401") or "malformed" in err_msg_lower or "unauthorized" in err_msg_lower:
                    formatted_err = format_resend_error(dom_exc)
                    app.logger.error("Resend API Authentication Failed: %s", formatted_err)
                    return f"Resend API Authentication Failed ({formatted_err}). Please verify your RESEND_API_KEY in Railway.", 500
                app.logger.info("Resend Domains probe info: %s", format_resend_error(dom_exc))

            return (
                f"Resend API is connected and verified! "
                f"Sender: {RESEND_FROM_EMAIL}. {dom_summary}. "
                f"To test actual email delivery, visit: /test-email?to=your_resend_account_email@gmail.com",
                200,
            )
        except Exception as exc:
            formatted_err = format_resend_error(exc)
            app.logger.error("Resend API Diagnostic Error: %s", formatted_err)
            return f"Resend API Error ({formatted_err})", 500

    if not MAIL_EMAIL or not MAIL_PASSWORD:
        msg = "Neither RESEND_API_KEY nor MAIL_EMAIL/MAIL_PASSWORD is configured in environment variables."
        app.logger.error("Email Diagnostic Failure: %s", msg)
        return f"Configuration Error: {msg}", 500
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(MAIL_EMAIL, MAIL_PASSWORD)
            return "SMTP connected and authenticated successfully!", 200
    except Exception as exc:
        app.logger.error("SMTP Diagnostic Error: %s: %s", type(exc).__name__, exc)
        return f"SMTP Error ({type(exc).__name__}): {exc}", 500


# -----------------------------------
# RUN APPLICATION
# -----------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    is_debug = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1") or (
        os.getenv("FLASK_ENV") == "development"
    )
    app.run(host="0.0.0.0", port=port, debug=is_debug)
