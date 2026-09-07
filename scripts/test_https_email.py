"""
Diagnostic script for HTTPS email delivery.
Tests the dispatch_email flow safely without leaking credentials.
"""
import os
import sys

# Ensure root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import (
    app as flask_app,
    get_app_setting,
    send_via_gmail_api,
    send_via_emailjs,
    dispatch_email,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    MAIL_EMAIL,
    RESEND_API_KEY,
)

def run_diagnostics(target_email):
    print("==========================================")
    print(" ExpenseFlow HTTPS Email Diagnostics")
    print("==========================================")
    print(f"Target recipient: {target_email}")
    print("------------------------------------------")

    with flask_app.app_context():
        gmail_refresh = os.getenv("GMAIL_REFRESH_TOKEN") or get_app_setting("gmail_refresh_token")
        emailjs_svc = os.getenv("EMAILJS_SERVICE_ID") or get_app_setting("emailjs_service_id")

        gas_url = os.getenv("GAS_WEBAPP_URL") or get_app_setting("gas_webapp_url")
        brevo_key = os.getenv("BREVO_API_KEY") or get_app_setting("brevo_api_key")

        print("Configuration Status:")
        print(f"  Google Client ID: {'CONFIGURED' if GOOGLE_CLIENT_ID else 'MISSING'}")
        print(f"  Google Client Secret: {'CONFIGURED' if GOOGLE_CLIENT_SECRET else 'MISSING'}")
        print(f"  Gmail Refresh Token: {'CONFIGURED' if gmail_refresh else 'NOT YET CONNECTED'}")
        print(f"  Google Apps Script URL: {'CONFIGURED' if gas_url else 'NOT CONFIGURED'}")
        print(f"  Brevo API Key: {'CONFIGURED' if brevo_key else 'NOT CONFIGURED'}")
        print(f"  EmailJS Service ID: {'CONFIGURED' if emailjs_svc else 'NOT CONFIGURED'}")
        print(f"  Mail Email (Sender): {MAIL_EMAIL or 'NOT CONFIGURED'}")
        print(f"  Resend API Key: {'CONFIGURED' if RESEND_API_KEY else 'MISSING'}")
        print("------------------------------------------")

        print("Testing dispatch_email...")
        try:
            dispatch_email(
                target_email,
                "ExpenseFlow Diagnostic Test",
                "Hello! This is an automated test message from ExpenseFlow HTTPS dispatcher.",
                "<h3>ExpenseFlow Diagnostic Test</h3><p>This is an automated test message from ExpenseFlow HTTPS dispatcher.</p>",
                otp="123456"
            )
            print("[SUCCESS] Email dispatch completed successfully!")
        except Exception as exc:
            print(f"[ERROR] Email dispatch failed: {type(exc).__name__}: {exc}")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "test@example.com"
    run_diagnostics(target)
