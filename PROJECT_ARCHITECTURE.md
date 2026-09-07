# ExpenseFlow (DailyExpenseTracker) — System Architecture & Flow Diagrams

This document contains high-precision architectural diagrams, entity relationships, sequence flows, and network topologies representing the final implementation of the ExpenseFlow web application.

---

## 1. Overall System Architecture Topology

```
+-------------------------------------------------------------------------------------------------------+
|                                        CLIENT TIER (User Device)                                      |
|                                                                                                       |
|    +------------------------------------+             +------------------------------------+          |
|    |      Desktop Web Browser           |             |       Mobile Web Browser           |          |
|    |   (Chrome, Edge, Firefox, Safari)  |             |   (Mobile Safari, Chrome Mobile)   |          |
|    +-----------------+------------------+             +-----------------+------------------+          |
+----------------------|--------------------------------------------------|-----------------------------+
                       |                                                  |
                       +------------------------+-------------------------+
                                                |
                                                | HTTPS (Port 443 / TLS 1.3)
                                                v
+-------------------------------------------------------------------------------------------------------+
|                                    EDGE / CLOUD INFRASTRUCTURE (Railway)                              |
|                                                                                                       |
|                 +-------------------------------------------------------------+                       |
|                 |          Railway Ingress & Cloudflare SSL Termination       |                       |
|                 |    (Terminates public HTTPS, passes X-Forwarded-Proto)      |                       |
|                 +------------------------------+------------------------------+                       |
|                                                | Forward via localhost socket                         |
|                                                v                                                      |
|                 +-------------------------------------------------------------+                       |
|                 |          Gunicorn WSGI Application Server (Port $PORT)      |                       |
|                 |     (--workers 1 --threads 8, Werkzeug ProxyFix enabled)    |                       |
|                 +------------------------------+------------------------------+                       |
+------------------------------------------------|------------------------------------------------------+
                                                 |
                                                 v
+-------------------------------------------------------------------------------------------------------+
|                                     APPLICATION TIER (Flask app.py)                                   |
|                                                                                                       |
|    +---------------------------------------------------------------------------------------------+    |
|    |                                Security & Context Middleware                                |    |
|    |   - @app.before_request: CSRF Token Verification (secrets.token_hex / hmac.compare_digest)  |    |
|    |   - @app.after_request: Security Headers (X-Frame-Options, X-Content-Type, Referrer-Policy)  |    |
|    |   - @app.teardown_request: Database Transaction Cleanup (commit/rollback)                   |    |
|    |   - @login_required: Session & Authentication Barrier + Google Password Setup Guard         |    |
|    +---------------------------------------------------------------------------------------------+    |
|                                                |                                                      |
|         +--------------------------------------+--------------------------------------+               |
|         |                                      |                                      |               |
|         v                                      v                                      v               |
|  +------------------+                +-------------------+                 +---------------------+    |
|  |  Authentication  |                | Expense & Budget  |                 | Analytics & Reports |    |
|  |     Engine       |                |     Services      |                 |       Engine        |    |
|  | - Email/Pass Auth|                | - Expenses CRUD   |                 | - Category Doughnut |    |
|  | - Google OAuth   |                | - Multi-filtering |                 | - Daily Trend Line  |    |
|  | - OTP Validation |                | - Budget Watchdog |                 | - Monthly Bar Chart |    |
|  | - Session Manager|                | - CSV Exporter    |                 | - Financial Insights|    |
|  +--------+---------+                +---------+---------+                 +----------+----------+    |
|           |                                    |                                      |               |
+-----------|------------------------------------|--------------------------------------|---------------+
            |                                    |                                      |
            +-----------------+------------------+--------------------------------------+
                              |
                              +---------------------------------------+
                              |                                       |
                              v                                       v
+---------------------------------------------+   +-----------------------------------------------------+
|        DATA TIER (Railway Cloud MySQL)      |   |        EXTERNAL EMAIL & AUTH SERVICES (Port 443)    |
|                                             |   |                                                     |
|  +---------------------------------------+  |   |  1. Google Apps Script Webhook (Priority Active)    |
|  | Database: daily_expense_tracker       |  |   |     `https://script.google.com/macros/s/.../exec`   |
|  |                                       |  |   |     -> Sends via native Google MailApp API          |
|  | Tables:                               |  |   |                                                     |
|  |  * users (Credentials & OAuth IDs)    |  |   |  2. Gmail REST API (Standby OAuth2)                 |
|  |  * auth_otps (Hashed OTP Codes)       |  |   |     `https://gmail.googleapis.com/v1/users/me/...`  |
|  |  * expenses (User Transactions)       |  |   |                                                     |
|  |  * budgets (Monthly Spending Limits)  |  |   |  3. Brevo REST API (Standby HTTPS)                  |
|  |  * notifications (Alert History)      |  |   |     `https://api.brevo.com/v3/smtp/email`           |
|  |  * app_settings (Persistent Configs)  |  |   |                                                     |
|  +---------------------------------------+  |   |  4. Google Identity Services (OAuth 2.0)            |
|                                             |   |     `https://accounts.google.com/o/oauth2/v2/auth`  |
+---------------------------------------------+   +-----------------------------------------------------+
```

---

## 2. Entity-Relationship (ER) Model

```
+---------------------------+             1:N             +------------------------------------+
|           users           |----------------------------<|              expenses              |
+---------------------------+                             +------------------------------------+
| id (PK, INT, AutoInc)     |                             | id (PK, INT, AutoInc)              |
| name (VARCHAR 120)        |                             | user_id (FK, INT)                  |
| email (VARCHAR 255, UNIQUE|                             | amount (DECIMAL 12,2)              |
| password (VARCHAR 255)    |                             | category (VARCHAR 50)              |
| google_id (VARCHAR 255)   |                             | expense_date (DATE)                |
| auth_provider (VARCHAR 50)|                             | payment_method (VARCHAR 50)        |
| has_set_password (BOOLEAN)|                             | description (VARCHAR 255)          |
| created_at (TIMESTAMP)    |                             | created_at (TIMESTAMP)             |
+---------------------------+                             | updated_at (TIMESTAMP)             |
       |             |                                    +------------------------------------+
       | 1:N         | 1:N (Unique per month/year)
       |             v
       |      +------------------------------------+
       |      |              budgets               |
       |      +------------------------------------+
       |      | id (PK, INT, AutoInc)              |
       |      | user_id (FK, INT)                  |
       |      | budget_amount (DECIMAL 12,2)       |
       |      | month (TINYINT 1-12)               |
       |      | year (SMALLINT)                    |
       |      | created_at (TIMESTAMP)             |
       |      | updated_at (TIMESTAMP)             |
       |      | UNIQUE(user_id, month, year)       |
       |      +------------------------------------+
       |
       | 1:N
       v
+------------------------------------+
|           notifications            |
+------------------------------------+
| id (PK, INT, AutoInc)              |
| user_id (FK, INT)                  |
| type (VARCHAR 50)                  |
| title (VARCHAR 120)                |
| message (VARCHAR 255)              |
| is_read (BOOLEAN, default FALSE)   |
| action_url (VARCHAR 255)           |
| created_at (TIMESTAMP)             |
+------------------------------------+

+------------------------------------+                    +------------------------------------+
|             auth_otps              |                    |            app_settings            |
+------------------------------------+                    +------------------------------------+
| id (PK, INT, AutoInc)              |                    | setting_key (PK, VARCHAR 100)      |
| email (VARCHAR 255)                |                    | setting_value (TEXT)               |
| otp_hash (VARCHAR 255)             |                    | updated_at (TIMESTAMP)             |
| purpose (VARCHAR 50)               |                    +------------------------------------+
| token (VARCHAR 255, NULL)          |                    (Stores persistent configurations    |
| metadata (JSON, NULL)              |                     such as gas_webapp_url,             |
| attempts (INT, default 0)          |                     gmail_refresh_token, etc.)          |
| max_attempts (INT, default 5)      |
| is_verified (BOOLEAN, default 0)   |
| is_used (BOOLEAN, default 0)       |
| expires_at (DATETIME)              |
| created_at (TIMESTAMP)             |
+------------------------------------+
(Decoupled from users to support unverified registrations)
```

---

## 3. User Registration & OTP Verification Sequence

```
User (Browser)          Flask Controller           MySQL Database          Google Apps Script Webhook
      |                        |                          |                             |
      | 1. POST /register      |                          |                             |
      | (name, email, pass)    |                          |                             |
      |----------------------->|                          |                             |
      |                        | 2. Validate format       |                             |
      |                        |    & Check duplicate     |                             |
      |                        |------------------------->|                             |
      |                        |    (SELECT id FROM users)|                             |
      |                        |<-------------------------|                             |
      |                        |                          |                             |
      |                        | 3. Generate 6-digit OTP  |                             |
      |                        |    Hash OTP (PBKDF2)     |                             |
      |                        |                          |                             |
      |                        | 4. INSERT into auth_otps |                             |
      |                        |------------------------->|                             |
      |                        |                          |                             |
      |                        | 5. POST Webhook Payload (to, subject, text, html)      |
      |                        |------------------------------------------------------->|
      |                        |                                                        | 6. MailApp.sendEmail()
      |                        | 7. HTTP 200 {"status": "success"}                      |    to User Inbox
      |                        |<-------------------------------------------------------|
      |                        |                          |                             |
      | 8. Redirect /verify-otp|                          |                             |
      |<-----------------------|                          |                             |
      |                        |                          |                             |
      | 9. POST /verify-otp    |                          |                             |
      | (email, 6-digit code)  |                          |                             |
      |----------------------->|                          |                             |
      |                        | 10. Fetch active OTP     |                             |
      |                        |------------------------->|                             |
      |                        |<-------------------------|                             |
      |                        |                          |                             |
      |                        | 11. Check:               |                             |
      |                        |     - Expiry < 10 mins   |                             |
      |                        |     - Attempts < 5       |                             |
      |                        |     - check_password_hash|                             |
      |                        |                          |                             |
      |                        | 12. INSERT new user      |                             |
      |                        |     UPDATE is_used=TRUE  |                             |
      |                        |------------------------->|                             |
      |                        |                          |                             |
      | 13. Redirect /login    |                          |                             |
      |     "Registration OK"  |                          |                             |
      |<-----------------------|                          |                             |
```

---

## 4. Google OAuth 2.0 Authentication & Linking Sequence

```
User Browser              Flask Application             Google Accounts            Google API
     |                            |                            |                        |
     | 1. Click "Sign in w/ Google"|                           |                        |
     |--------------------------->|                            |                        |
     |                            | 2. Generate CSPRNG state   |                        |
     |                            |    session['state'] = st   |                        |
     | 3. 302 Redirect to Google  |                            |                        |
     |    with client_id, state   |                            |                        |
     |<---------------------------|                            |                        |
     |                                                         |                        |
     | 4. Authenticate & Grant Consent                         |                        |
     |-------------------------------------------------------->|                        |
     |                                                         |                        |
     | 5. 302 Redirect to /login/google/callback?code=X&state=st                        |
     |<--------------------------------------------------------|                        |
     |                                                         |                        |
     | 6. GET /login/google/callback?code=X&state=st           |                        |
     |--------------------------->|                            |                        |
     |                            | 7. Validate state with hmac.compare_digest          |
     |                            |    (Mismatch = Abort 400)                           |
     |                            |                                                     |
     |                            | 8. POST /token (code, client_id, client_secret)     |
     |                            |---------------------------------------------------->|
     |                            |<----------------------------------------------------|
     |                            |    Return: access_token, id_token                   |
     |                            |                                                     |
     |                            | 9. GET /userinfo (Bearer access_token)              |
     |                            |---------------------------------------------------->|
     |                            |<----------------------------------------------------|
     |                            |    Return: {email, name, id}                        |
     |                            |                                                     |
     |                            | 10. Database Account Resolution:                    |
     |                            |     CASE A: google_id exists -> Log in              |
     |                            |     CASE B: email exists -> Link google_id & Log in |
     |                            |     CASE C: new user -> INSERT user & flag          |
     |                            |             session['pending_password_setup'] = True|
     |                            |                                                     |
     | 11. 302 Redirect:          |                                                     |
     |     /dashboard (Existing)  |                                                     |
     |     /set-password (New)    |                                                     |
     |<---------------------------|                                                     |
```

---

## 5. Password Reset & Account Recovery Sequence

```
User (Browser)               Flask Controller               MySQL (auth_otps)        Google Apps Script
      |                              |                              |                        |
      | 1. POST /forgot-password     |                              |                        |
      |    (registered email)        |                              |                        |
      |----------------------------->|                              |                        |
      |                              | 2. Lookup user in DB         |                        |
      |                              |    (Prevents user discovery) |                        |
      |                              |                              |                        |
      |                              | 3. Generate 6-digit OTP      |                        |
      |                              |    Generate reset_token      |                        |
      |                              |    Hash OTP via PBKDF2       |                        |
      |                              |                              |                        |
      |                              | 4. INSERT into auth_otps     |                        |
      |                              |    (purpose='password_reset')|                        |
      |                              |----------------------------->|                        |
      |                              |                              |                        |
      |                              | 5. Dispatch Reset Email                               |
      |                              |------------------------------------------------------>|
      |                              |                                                       | 6. Deliver to
      |                              | 7. Response OK                                        |    User Inbox
      |                              |<------------------------------------------------------|
      |                              |                              |                        |
      | 8. 302 /verify-reset-otp     |                              |                        |
      |<-----------------------------|                              |                        |
      |                              |                              |                        |
      | 9. POST /verify-reset-otp    |                              |                        |
      |    (enter 6-digit OTP)       |                              |                        |
      |----------------------------->|                              |                        |
      |                              | 10. Verify Hash & Expiry     |                        |
      |                              |----------------------------->|                        |
      |                              |                              |                        |
      | 11. 302 /reset-password      |                              |                        |
      |<-----------------------------|                              |                        |
      |                              |                              |                        |
      | 12. POST /reset-password     |                              |                        |
      |     (new_pass, confirm_pass) |                              |                        |
      |----------------------------->|                              |                        |
      |                              | 13. UPDATE users             |                        |
      |                              |     SET password = hash      |                        |
      |                              |     UPDATE auth_otps is_used |                        |
      |                              |----------------------------->|                        |
      |                              |                              |                        |
      | 14. 302 /login ("Success")   |                              |                        |
      |<-----------------------------|                              |                        |
```

---

## 6. Multi-Provider Email Delivery Pipeline

```
                              dispatch_email() Call
                                        |
                                        v
                            Is MOCK_EMAIL == "1"?
                               /             \
                             YES              NO
                             /                 \
                    Log test OTP & Return       v
                                       1. Gmail REST API
                                     (GMAIL_REFRESH_TOKEN)
                                        /             \
                                     SUCCESS         FAILED / MISSING
                                       |                      \
                                    [Return]                   v
                                                     2. Google Apps Script
                                                       (GAS_WEBAPP_URL)
                                                        /             \
                                                     SUCCESS         FAILED / MISSING
                                                       |                      \
                                                    [Return]                   v
                                                                        3. Brevo REST API
                                                                        (BREVO_API_KEY)
                                                                          /             \
                                                                       SUCCESS         FAILED / MISSING
                                                                         |                      \
                                                                      [Return]                   v
                                                                                          4. EmailJS REST API
                                                                                          (EMAILJS_SERVICE_ID)
                                                                                            /             \
                                                                                         SUCCESS         FAILED / MISSING
                                                                                           |                      \
                                                                                        [Return]                   v
                                                                                                            5. Resend Custom Domain
                                                                                                            (RESEND_API_KEY + domain)
                                                                                                              /             \
                                                                                                           SUCCESS         FAILED / MISSING
                                                                                                             |                      \
                                                                                                          [Return]                   v
                                                                                                                              6. Raw SMTP
                                                                                                                          (Port 587 Local Only)
                                                                                                                                /             \
                                                                                                                             SUCCESS         FAILED / BLOCKED
                                                                                                                               |                      \
                                                                                                                            [Return]                   v
                                                                                                                                                7. Resend Sandbox
                                                                                                                                              (onboarding@resend.dev)
                                                                                                                                                  /             \
                                                                                                                                               SUCCESS         FAILED (Raise)
```

---

## 7. Budget Watchdog & Alert Generation Flow

```
                      User Adds / Edits / Views Expenses
                                      |
                                      v
                        generate_user_notifications(user_id)
                                      |
       +------------------------------+------------------------------+
       |                                                             |
       v                                                             v
Fetch Current Month Total Spend                       Fetch Current Month Target Budget
`SELECT SUM(amount) FROM expenses`                    `SELECT budget_amount FROM budgets`
       |                                                             |
       +------------------------------+------------------------------+
                                      |
                                      v
                           Calculate: used_pct = (Total / Budget) * 100
                                      |
      +-------------------------------+-------------------------------+
      |                               |                               |
      v                               v                               v
used_pct >= 100%               90% <= used_pct < 100%          80% <= used_pct < 90%
(Exceeded Limit)               (Critical Warning)              (Warning Approaching)
      |                               |                               |
      v                               v                               v
Check if 'budget_exceeded'     Check if 'budget_90'            Check if 'budget_80'
already notified this month    already notified this month     already notified this month
      |                               |                               |
      +-------------------------------+-------------------------------+
                                      | (If not already sent)
                                      v
                   INSERT INTO notifications table
                   - type: 'budget_exceeded' / 'budget_90' / 'budget_80'
                   - title: 'Budget Exceeded' / 'Critical Warning'
                   - is_read: FALSE
                                      |
                                      v
           Injected into every page navbar via inject_global_context()
           (Displays real-time bell badge count and notification modal)
```

---

## 8. Continuous Deployment Pipeline (Local to Live)

```
[ Developer Terminal ]
       |
       | 1. git add .
       | 2. git commit -m "feat/fix..."
       | 3. git push origin main
       v
[ GitHub Repository ]
  (https://github.com/ngkrishnaa/DailyExpenseTracker)
       |
       | 4. Webhook Trigger on push
       v
[ Railway Cloud PaaS ]
       |
       +---> 5. Fetch code from 'main' branch
       +---> 6. Detect Python runtime & build environment
       +---> 7. Execute: pip install -r requirements.txt
       +---> 8. Read Procfile: `web: gunicorn --workers 1 --threads 8 --bind 0.0.0.0:$PORT app:app`
       +---> 9. Inject encrypted environment variables (MYSQL_URL, GAS_WEBAPP_URL, etc.)
       +---> 10. Start application container on allocated internal $PORT
       +---> 11. Run health checks: Confirm HTTP socket responds with 200
       +---> 12. Atomic Traffic Cutover: Route public domain to new container
       +---> 13. Terminate old container (Zero Downtime)
       v
[ Live Production URL ]
  https://dailyexpensetracker-production-bf76.up.railway.app
```
