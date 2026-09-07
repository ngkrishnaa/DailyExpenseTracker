# ExpenseFlow (DailyExpenseTracker) — Complete Technical Documentation Manual

---

## Document Overview
* **Project Name:** ExpenseFlow (Repository: `DailyExpenseTracker`)
* **Author / Developer:** Nanda Gopala Krishna (`ngkrishna72@gmail.com`)
* **Institution:** Alliance University
* **Live Production URL:** [https://dailyexpensetracker-production-bf76.up.railway.app](https://dailyexpensetracker-production-bf76.up.railway.app)
* **GitHub Repository:** [https://github.com/ngkrishnaa/DailyExpenseTracker](https://github.com/ngkrishnaa/DailyExpenseTracker)
* **Document Purpose:** Complete technical reference, viva defense handbook, system architecture guide, and codebase documentation.

---

# CHAPTER 1 — PROJECT OVERVIEW & EXECUTIVE SUMMARY

### 1.1 Beginner-Friendly Explanation
ExpenseFlow is a smart, secure website where anyone can track their daily spending, set a monthly spending limit (budget), and see visual charts that show where their money goes. 

Imagine you spend money on tea, food, auto-rickshaws, shopping, and mobile recharges using cash, UPI, or credit cards. At the end of the month, you wonder: *"Where did all my money go?"* 
ExpenseFlow solves this:
1. You can log in with your email or with one click using your Google account.
2. Every time you spend money, you record it with the amount, category (like Food or Travel), payment method (like UPI or Cash), and date.
3. You set a monthly budget (for example, ₹15,000).
4. If you reach 80% or 90% of your budget, the website sends you a smart alert so you don't overspend.
5. You can view colorful pie charts and bar charts to understand your spending habits, and you can download an Excel/CSV sheet of all your transactions at any time.

---

### 1.2 Technical Explanation
ExpenseFlow is a multi-tenant, cloud-deployed, Model-View-Controller (MVC) architecture personal finance platform built with Python 3, Flask 3.1.3, and an ACID-compliant MySQL 8.0 relational database running on Railway PaaS infrastructure. 

The application implements defense-in-depth security:
- **Authentication:** Dual authentication supporting local salted PBKDF2-SHA256 password credentials and Google OAuth 2.0 Authorization Code grant with cryptographic CSRF `state` tokens and automatic account linking.
- **Verification Engine:** Cryptographically secure 6-digit One-Time Password (OTP) verification for account creation and password recovery, hashed in MySQL with a 10-minute time-to-live (TTL) and a 5-attempt rate-limiting lockout.
- **Relational Integrity:** Six relational tables with composite B-tree indexes, strict `ON DELETE CASCADE` foreign key constraints, and exact `DECIMAL(12, 2)` fixed-point arithmetic preventing floating-point currency drift.
- **Network Resilience:** Overcomes cloud host SMTP port firewalls (ports 25, 465, 587) via a zero-cost HTTPS transactional email pipeline powered by an authenticated Google Apps Script Webhook.

---

### 1.3 Problem Statement & Why It Matters
Personal financial mismanagement is a major contributor to economic stress among students, freelancers, and early-career professionals. Traditional tracking approaches suffer from severe shortcomings:
1. **Spreadsheet Abandonment:** Manual Excel or Google Sheets require significant setup, lack automated input validation, have awkward mobile interfaces, and provide no automated alert notifications.
2. **Privacy Risks of Commercial Apps:** Commercial fintech apps (like Cred, Walnut, or YNAB) demand access to SMS messages, bank APIs, or credit report data, exposing users to aggressive data mining, credit card promotions, and third-party tracking.
3. **Data Loss & Portability:** Many mobile apps store data locally on a single phone with no cloud sync or charge expensive monthly subscription fees to export basic CSV reports.

---

### 1.4 Objectives & Requirements
* **Primary Objectives:** Deliver an accessible, completely free, privacy-focused, cross-platform expense tracker with institutional-grade security and zero third-party data tracking.
* **Functional Requirements:**
  - Secure user registration with email OTP verification.
  - Social authentication via Google OAuth 2.0.
  - Expense CRUD (Create, Read, Update, Delete) with validation.
  - Multi-parameter transaction search, category/date filtering, and pagination.
  - In-memory streaming CSV transaction export.
  - Monthly budget limit creation and real-time threshold monitoring (80%, 90%, 100%).
  - In-app notification queue with read/unread state management.
  - Interactive Chart.js analytics for category, daily, and monthly spending distributions.
  - Profile update and self-service password recovery via OTP.
* **Non-Functional Requirements:**
  - **Security:** Zero plaintext credentials; protection against SQL Injection, XSS, CSRF, IDOR, and timing attacks.
  - **Performance:** Sub-200ms database response times using composite B-tree indexes.
  - **Reliability:** Automatic MySQL reconnect on idle timeouts; multi-provider email fallback pipeline.
  - **Responsiveness:** 100% fluid mobile and desktop UI via custom CSS (zero framework dependencies).

---

# CHAPTER 2 — TECHNOLOGY INVENTORY & ARCHITECTURAL STACK

```
+---------------------------------------------------------------------------------------+
|                               EXPENSEFLOW TECHNOLOGY STACK                            |
+------------------------------------+--------------------------------------------------+
| LAYER                              | TECHNOLOGIES IMPLEMENTED                         |
+------------------------------------+--------------------------------------------------+
| Frontend Layer                     | Jinja2 Templates, Vanilla ES6+ JS, Custom CSS    |
| Visualization                      | Chart.js 4.4.1 (Canvas-based via CDN)            |
| Application Server                 | Gunicorn 23.0.0 (1 Worker, 8 Threads)            |
| Web Framework                      | Python 3.11+ / Flask 3.1.3                       |
| Security & Middleware              | Werkzeug Security, Werkzeug ProxyFix, HMAC, CSP  |
| Database Engine                    | MySQL 8.0 (Railway Cloud Managed)                |
| Database Connector                 | mysql-connector-python 26.7.0                    |
| Primary Email Webhook              | Google Apps Script (HTTPS Webhook / MailApp API) |
| Secondary Email Dispatchers        | Gmail REST API, Brevo REST API, EmailJS, Resend  |
| Identity Provider                  | Google Identity Services (OAuth 2.0 Auth Code)   |
| Cloud Infrastructure               | Railway PaaS (Docker/Nixpacks container runtime) |
| Version Control & CI/CD            | Git & GitHub (Automated Railway build triggers)  |
| Automated Test Suite               | Python standard unittest (56 Automated Tests)    |
+------------------------------------+--------------------------------------------------+
```

---

# CHAPTER 3 — FRONTEND ARCHITECTURE & USER INTERFACE

### 3.1 Template Hierarchy & Jinja2 Inheritance
The application utilizes Jinja2 server-side rendering. To prevent code duplication, templates inherit from `templates/dashboard_base.html`:

```
               +----------------------------------+
               |   templates/dashboard_base.html  |
               |  (Navbar, Sidebar, Flash Banners,|
               |   CSRF Meta, CSS, JS Scripts)    |
               +-----------------+----------------+
                                 |
         +-----------------------+-----------------------+
         |                       |                       |
         v                       v                       v
+------------------+   +-------------------+   +--------------------+
|  dashboard.html  |   |   expenses.html   |   |    reports.html    |
+------------------+   +-------------------+   +--------------------+
|   budget.html    |   | expense_form.html |   |    profile.html    |
+------------------+   +-------------------+   +--------------------+
```

Public authentication views (`login.html`, `register.html`, `forgot_password.html`, `verify_otp.html`) use focused, distraction-free cards centered on a dark canvas with glassmorphic cards.

---

### 3.2 Page-by-Page Inventory & Specifications

| Template | Route | Purpose | Inputs | Outputs | Auth Required? | Security & Backend Interaction |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| `home.html` | `/` | Public landing page explaining features and value proposition. | None | Interactive UI, CTA buttons to `/register` and `/login`. | No | Publicly cached; redirects authenticated users to `/dashboard`. |
| `login.html` | `/login` | User authentication via password or Google. | Email, password, CSRF token. | Session cookie (`session['user_id']`), flash messages. | No | Rate-limit resilient; timing-safe password hash check; Google button. |
| `register.html` | `/register` | User account creation. | Name, email, password, confirm_password, CSRF token. | OTP dispatch email, redirects to `/verify-otp`. | No | Email regex validation; password strength check; duplicate rejection. |
| `verify_otp.html` | `/verify-otp` | Validates 6-digit registration OTP. | 6-digit OTP code, email, CSRF token. | Account creation in `users`, redirect to `/login`. | No | 10-minute expiry; 5-attempt lockout; single-use OTP invalidation. |
| `forgot_password.html` | `/forgot-password` | Initiates password reset request. | Registered email, CSRF token. | Reset token in session, OTP email dispatch. | No | Masks account existence; prevents user discovery; generates reset token. |
| `verify_reset_otp.html` | `/verify-reset-otp` | Validates password reset code. | 6-digit OTP code, CSRF token. | Session reset authorization, redirect to `/reset-password`. | No | Matches `purpose='password_reset'`; checks attempt limits. |
| `reset_password.html` | `/reset-password` | Sets new account password. | New password, confirm password, CSRF token. | Updates `users.password`, clears reset session. | No | Validates active authorized reset session; updates password hash. |
| `set_password.html` | `/set-password` | Allows Google-only users to create local password. | New password, confirm password, CSRF token. | Updates `users.password`, flips `has_set_password=TRUE`. | Yes | Required for Google users before accessing dashboard. |
| `dashboard.html` | `/dashboard` | Primary overview: KPI cards, budget bar, recent activity. | Month/Year filter. | Spent total, budget progress, top categories, notification modal. | Yes | Aggregated SQL queries; computes budget progress percentage. |
| `expenses.html` | `/expenses` | Paginated transaction ledger with multi-filters. | Search keyword, category, date range, min/max amount, page. | Paginated expense rows, summary badge, CSV download link. | Yes | Strict `user_id` filtering; SQL parameter binding; pagination math. |
| `expense_form.html` | `/expenses/add`, `/expenses/<id>/edit` | Create or update expense. | Amount, category, payment method, date, description, CSRF. | Database write in `expenses`, redirect to `/expenses`. | Yes | Form validation; verifies record ownership before editing (no IDOR). |
| `budget.html` | `/budget` | Manage monthly budget targets. | Budget amount, month, year, CSRF token. | Upserts into `budgets`, computes health state. | Yes | Unique constraint `(user_id, month, year)` prevents duplicate budgets. |
| `reports.html` | `/reports` | Visual analytics and charts. | Month/Year selector. | Category Doughnut, Daily Trend Line, Monthly Comparison Bar. | Yes | SQL `GROUP BY` aggregations; JSON injection into Chart.js canvas. |
| `profile.html` | `/profile` | User settings, name update, password change. | Name, current password, new password, CSRF token. | Updates `users.name` and/or password hash. | Yes | Verifies current password before allowing password modification. |
| `error.html` | 400, 404, 500 handlers | Sanitized error pages for clients. | None | User-friendly error message, back to safety button. | No | Completely masks stack traces, SQL queries, and environment secrets. |

---

### 3.3 CSS Architecture & Design System
The entire interface is styled by `/static/css/style.css` (78,359 bytes) with zero CSS framework bloat:
- **Color Palette & Glassmorphism:** Deep navy backgrounds (`#0a0f1d`), glass translucent cards (`rgba(16, 24, 40, 0.75)` with `backdrop-filter: blur(16px)`), electric blue accents (`#3b82f6`), and semantic alert colors (Green `#10b981`, Amber `#f59e0b`, Red `#ef4444`).
- **Responsive Layout:** CSS Grid with `repeat(auto-fit, minmax(260px, 1fr))` for metric cards; Flexbox for header and navigation; `@media (max-width: 768px)` transforming sidebar into a slide-over mobile drawer.
- **Accessibility:** High contrast ratios on dark backgrounds, clear focus indicators (`outline: 2px solid var(--accent-blue)`), and full keyboard tab navigation.

---

# CHAPTER 4 — BACKEND CONTROLLERS & ROUTING ARCHITECTURE

### 4.1 Complete Route Inventory (30 Registered Routes)

```
+--------------------------------------------------------------------------------------------------------+
|                                    FLASK APPLICATION ROUTE BLUEPRINT                                   |
+----------------------------------------------+------------------+------------------+-------------------+
| ROUTE URL PATTERN                            | HTTP METHODS     | ENDPOINT NAME    | AUTH REQUIRED?    |
+----------------------------------------------+------------------+------------------+-------------------+
| /                                            | GET              | home             | Public            |
| /register                                    | GET, POST        | register         | Public            |
| /verify-otp                                  | GET, POST        | verify_otp       | Public            |
| /resend-otp                                  | GET, POST        | resend_otp       | Public            |
| /login                                       | GET, POST        | login            | Public            |
| /login/google                                | GET              | google_login     | Public            |
| /login/google/callback                       | GET              | google_callback  | Public            |
| /logout                                      | POST             | logout           | Authenticated     |
| /forgot-password                             | GET, POST        | forgot_password  | Public            |
| /verify-reset-otp                            | GET, POST        | verify_reset_otp | Public            |
| /reset-password                              | GET, POST        | reset_password   | Public            |
| /set-password                                | GET, POST        | set_password     | Authenticated     |
| /dashboard                                   | GET              | dashboard        | Authenticated     |
| /expenses                                    | GET              | expenses         | Authenticated     |
| /expenses/add                                | GET, POST        | add_expense      | Authenticated     |
| /expenses/<int:expense_id>/edit              | GET, POST        | edit_expense     | Authenticated     |
| /expenses/<int:expense_id>/delete            | POST             | delete_expense   | Authenticated     |
| /expenses/export                             | GET              | export_expenses  | Authenticated     |
| /budget                                      | GET, POST        | budget           | Authenticated     |
| /reports                                     | GET              | reports          | Authenticated     |
| /profile                                     | GET, POST        | profile          | Authenticated     |
| /notifications/<int:notification_id>/read    | POST             | mark_read        | Authenticated     |
| /notifications/<int:notification_id>/dismiss | POST             | dismiss_notif    | Authenticated     |
| /notifications/read-all                      | POST             | mark_all_read    | Authenticated     |
| /admin/connect-gmail                         | GET              | admin_connect    | Public / Admin    |
| /test-db                                     | GET              | test_db          | Public (Health)   |
| /test-email                                  | GET              | test_email       | Public (Diag)     |
| /test-smtp                                   | GET              | test_email       | Public (Diag)     |
| /test-auth-login-google                      | GET              | test_auth_google | Public (Test)     |
| /static/<path:filename>                      | GET              | static           | Public (Assets)   |
+----------------------------------------------+------------------+------------------+-------------------+
```

---

### 4.2 Key Function Deep Dives in `app.py`

#### 1. `ensure_db_connection()`
* **What it does:** Verifies that the MySQL TCP connection is alive; if dead or timed out, it re-establishes a fresh socket.
* **Why it exists:** Cloud databases terminate idle connections after periods of inactivity. Without active pinging, morning requests crash.
* **Called by:** `@app.before_request`, `get_app_setting()`, `set_app_setting()`.
* **Mechanism:** Executes `db.ping(reconnect=True, attempts=3, delay=1)`. If an exception occurs, re-instantiates `mysql.connector.connect(**get_db_connection_params())`.

#### 2. `csrf_protect()`
* **What it does:** Enforces CSRF tokens on all modifying HTTP methods (`POST`, `PUT`, `DELETE`, `PATCH`).
* **Why it exists:** Protects authenticated users from Cross-Site Request Forgery attacks.
* **Mechanism:** Compares `request.form.get("csrf_token")` or `X-CSRFToken` header with `session.get("csrf_token")` using `hmac.compare_digest`. Rejects invalid tokens with HTTP 400.

#### 3. `login_required(view)`
* **What it does:** Decorator protecting private views.
* **Why it exists:** Enforces authentication and blocks unauthenticated requests.
* **Mechanism:** Checks if `"user_id" in session`. If absent, flashes error and redirects to `/login`. If the user is flagged with `session.get("pending_password_setup")`, redirects them to `/set-password`.

#### 4. `db_create_otp(email, otp, purpose, token, metadata, expiry_minutes, max_attempts)`
* **What it does:** Persists a newly generated OTP into the MySQL `auth_otps` table.
* **Why it exists:** Provides durable, restart-safe OTP storage separate from process memory.
* **Mechanism:** Marks prior active OTPs for this email and purpose as used (`is_used = TRUE`). Hashes the new OTP via `generate_password_hash(otp)`. Computes UTC expiry timestamp and inserts record into `auth_otps`.

#### 5. `dispatch_email(receiver_email, subject, plain_text, html_content, otp)`
* **What it does:** Central multi-provider email router.
* **Why it exists:** Routes emails through whichever provider is active, bypassing Railway's SMTP firewall blocks.
* **Mechanism:** Tries Gmail REST API -> Google Apps Script Webhook -> Brevo API -> EmailJS -> Resend API -> Raw SMTP.

#### 6. `generate_user_notifications(user_id)`
* **What it does:** Scans current month expenditure against monthly budget and inserts alerts into `notifications`.
* **Why it exists:** Keeps users informed of budget overruns in real-time.
* **Mechanism:** Computes current month spend; checks budget; verifies existing notifications to avoid duplicates; inserts `budget_80`, `budget_90`, or `budget_exceeded` alerts.

---

# CHAPTER 5 — DATABASE ARCHITECTURE & RELATIONAL SCHEMA

### 5.1 Relational Schema Definitions

```sql
-- 1. USERS TABLE
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NULL,
    google_id VARCHAR(255) NULL,
    auth_provider VARCHAR(50) NOT NULL DEFAULT 'local',
    has_set_password BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_google_id (google_id)
);

-- 2. AUTHENTICATION OTPS TABLE
CREATE TABLE IF NOT EXISTS auth_otps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    otp_hash VARCHAR(255) NOT NULL,
    purpose VARCHAR(50) NOT NULL,
    token VARCHAR(255) NULL,
    metadata JSON NULL,
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_otps_email_purpose (email, purpose),
    INDEX idx_otps_token (token)
);

-- 3. EXPENSES TABLE
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
);

-- 4. BUDGETS TABLE
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
);

-- 5. NOTIFICATIONS TABLE
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
);

-- 6. APP SETTINGS TABLE
CREATE TABLE IF NOT EXISTS app_settings (
    setting_key VARCHAR(100) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

---

### 5.2 Table-by-Table Technical Breakdown

1. **`users`:** Stores the identity credentials. `email` has a unique constraint to prevent duplicate registrations. `password` is nullable to allow Google OAuth users to register without a password. `has_set_password` indicates if a Google user has set a local password.
2. **`expenses`:** Central transaction ledger. `amount` uses `DECIMAL(12, 2)` to eliminate floating-point penny errors. Contains a foreign key `fk_expenses_user` pointing to `users(id)` with `ON DELETE CASCADE`.
3. **`budgets`:** Enforces one budget per user per calendar month using `UNIQUE KEY unique_user_month_budget (user_id, month, year)`.
4. **`notifications`:** Tracks smart budget threshold warnings and system messages. Includes `is_read` boolean and an index `idx_notifications_user_read` for instantaneous badge count lookups.
5. **`auth_otps`:** Manages verification security. Separates purposes via `purpose` ('registration' or 'password_reset'). Stores hashed OTPs, attempts count, maximum attempts allowed (5), and expiration timestamps.
6. **`app_settings`:** Key-value store for application configurations that survive redeployments (such as the Google Apps Script Webhook URL).

---

# CHAPTER 6 — AUTHENTICATION & IDENTITY ARCHITECTURE

```
+---------------------------------------------------------------------------------------+
|                               AUTHENTICATION FLOWCHART                                |
+---------------------------------------------------------------------------------------+

                     +---------------------------------------+
                     |          USER VISIT: /login           |
                     +-------------------+-------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v                                   v
             [ Standard Auth ]                     [ Google OAuth 2.0 ]
                       |                                   |
            User Enters Email/Password            Click "Sign in with Google"
                       |                                   |
            Flask looks up user in DB             Generate state token
            via parameterized SQL                 Redirect to Google Auth
                       |                                   |
            check_password_hash(hash, pass)       Google returns auth code
                       |                                   |
            Credentials Match?                    Flask exchanges code for token
               /           \                      and retrieves user profile
             YES            NO                             |
             /                \                   User exists in database?
            v                  v                        /             \
    Set session['user_id']   Flash Error              YES              NO
    Redirect /dashboard      Show /login              /                 \
                                              Link Google ID       Create new user in DB
                                              Set session          Flag pending_password_setup
                                              Redirect /dashboard  Redirect /set-password
```

---

### 6.1 User Registration & Verification
1. User enters name, email, password, and confirm password on `/register`.
2. Flask validates email regex format and confirms passwords match.
3. System executes `SELECT id FROM users WHERE email = %s`. If found, flashes error: *"Email already registered."*
4. A 6-digit random code is generated via `secrets.randbelow(900000) + 100000`.
5. The OTP is hashed with PBKDF2-SHA256 and saved in `auth_otps` with `purpose = 'registration'`.
6. Registration details are temporarily cached in `pending_registrations[email]` and in `auth_otps.metadata`.
7. The OTP email is dispatched via the Google Apps Script Webhook.
8. User is redirected to `/verify-otp`.
9. Upon entering the code, Flask verifies:
   - Expiration deadline has not elapsed (`expires_at > NOW()`).
   - Failed attempts do not exceed 5 (`attempts < 5`).
   - `check_password_hash(stored_hash, submitted_code)` evaluates to `True`.
10. The user is inserted into `users` table, and `auth_otps.is_used` is set to `TRUE`.

---

### 6.2 Password Reset Engine
1. User visits `/forgot-password` and enters their email.
2. System checks if account exists:
   - If user exists: generates 6-digit OTP, generates a unique session `reset_token`, stores PBKDF2 hash in `auth_otps` with `purpose = 'password_reset'`, and dispatches OTP email.
   - If user does NOT exist: does not send email, but displays the *same generic success message* to prevent user enumeration attacks.
3. User enters code on `/verify-reset-otp`. System checks attempt limit and hash match.
4. On success, user advances to `/reset-password`, enters new password, and `users.password` hash is updated in MySQL.

---

# CHAPTER 7 — OTP VERIFICATION ENGINE IN EXTREME DETAIL

### 7.1 Mathematical Randomness & Generation
Standard pseudorandom number generators (like Python’s `random` module) use the Mersenne Twister PRNG, which is completely deterministic and insecure for cryptographic use. 

ExpenseFlow strictly generates verification codes using Python’s `secrets` module:
```python
new_otp = str(secrets.randbelow(900000) + 100000)
```
- `secrets.randbelow(900000)` yields a uniform integer in the range `[0, 899999]`.
- Adding `100000` shifts the range to `[100000, 999999]`.
- This guarantees a strictly 6-digit numerical string with 900,000 discrete possibilities backed by OS system entropy (`/dev/urandom`).

---

### 7.2 The Defense Against Brute-Force Attacks
A 6-digit code has 900,000 combinations. An attacker could write an automated script to guess every combination within 15 minutes. ExpenseFlow neutralizes this threat with a 3-tier defense:

```
[ Attacker Submits Guess ]
           |
           v
    Check attempts < 5?
       /          \
     YES           NO
     /              \
Check Hash Match?   Permanent Lockout:
   /          \     Mark is_used = TRUE,
 MATCH      MISMATCH Clear reset session,
  /              \   Force fresh OTP request.
Success       Increment attempts += 1.
              Remaining = 5 - attempts.
              If attempts >= 5 -> Invalidate.
```
* **Attempt Probability:** The mathematical probability of guessing a 6-digit code within 5 permitted attempts is:
  $$\text{Probability} = \frac{5}{900,000} \approx 0.00055\%$$
* **Expiration Window:** Every OTP expires strictly 10 minutes after generation (`expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)`).
* **Single-Use Invalidation:** The moment an OTP is successfully verified, MySQL updates `is_used = TRUE`. Replay attacks are impossible.

---

# CHAPTER 8 — PRODUCTION EMAIL ARCHITECTURE & CLOUD NETWORKING

### 8.1 Why Cloud SMTP Failed
During local development, sending emails via standard Gmail SMTP (`smtp.gmail.com:587` with an App Password) works seamlessly because residential internet service providers leave port 587 unblocked.

However, when deploying to Railway (and similar cloud hosting platforms like AWS, Render, and DigitalOcean), the cloud provider permanently blocks outbound TCP traffic on ports **25, 465, and 587** to prevent their IP blocks from being used for malicious spam campaigns. Consequently, calls to `smtplib.SMTP("smtp.gmail.com", 587)` resulted in socket timeouts and `Errno 111: Connection Refused`.

---

### 8.2 Why the Resend Sandbox Failed
We initially integrated the Resend API (`resend>=2.6.0`) over HTTPS port 443. While Resend bypassed the port block, its free-tier sandbox (`onboarding@resend.dev`) enforces a strict security restriction:
> *It will ONLY deliver emails to the single email address registered by the developer on the Resend account.*

When arbitrary users attempted to register or reset passwords with their personal email addresses, the Resend API returned:
```json
HTTP 403 Forbidden: {"name": "validation_error", "message": "You can only send testing emails to your own email address. To send to other recipients, verify a custom domain."}
```
Verifying a custom domain requires purchasing a domain name and configuring DNS records (SPF, DKIM, DMARC), conflicting with the project's goal of maintaining a 100% free, zero-cost production footprint.

---

### 8.3 The Zero-Cost Google Apps Script Webhook Solution
To overcome both the cloud port block and the sandbox recipient barrier, we engineered an HTTPS Webhook using **Google Apps Script**:

```
+-----------------------------------------------------------------------------------+
|                        PRODUCTION EMAIL DISPATCH TOPOLOGY                         |
+-----------------------------------------------------------------------------------+

   Railway Production Container (Flask app.py)
               |
               | HTTPS POST (Standard Port 443 — Never Blocked)
               | Payload: {"to": recipient, "subject": sub, "text": txt, "html": html}
               v
   Google Apps Script Webhook Endpoint
   (https://script.google.com/macros/s/AKfycb.../exec)
               |
               | Internal Execution inside Google's Datacenter
               v
   Google MailApp Engine (MailApp.sendEmail)
               |
               | Native Google SPF/DKIM Authentication
               v
   User's Personal Inbox (Any Domain: Gmail, Outlook, Yahoo, University)
```

#### The Google Apps Script Code (`Code.gs`):
```javascript
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    MailApp.sendEmail({
      to: data.to,
      subject: data.subject,
      body: data.text,
      htmlBody: data.html
    });
    return ContentService.createTextOutput(JSON.stringify({status: "success"}))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({status: "error", error: err.toString()}))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
```

#### Why This Solution Is Superior:
1. **Standard Port 443:** Operates over standard HTTPS; cloud firewall port blocks cannot restrict it.
2. **Universal Delivery:** Can send up to 100 free emails per day to *any* email address in the world.
3. **High Deliverability:** Emails originate directly from Google's high-reputation IP pool with Google DKIM signatures, landing reliably in primary inboxes rather than spam folders.
4. **Zero Cost:** Requires ₹0, zero domain registrar subscriptions, and zero paid API keys.

---

# CHAPTER 9 — EXPENSE TRACKING & BUDGET ENGINE

### 9.1 Expense Management
- **Supported Categories (11):** Food, Transportation, Shopping, Bills, Entertainment, Health, Education, Travel, Groceries, Rent, Other.
- **Payment Methods (6):** Cash, Credit Card, Debit Card, UPI, Bank Transfer, Other.
- **Data Validation:** 
  - `amount`: Must be a positive decimal number greater than 0.
  - `category`: Validated against server-side whitelist tuple `CATEGORIES`.
  - `payment_method`: Validated against server-side whitelist tuple `PAYMENT_METHODS`.
  - `expense_date`: Validated format `YYYY-MM-DD`.
  - `description`: Sanitized, max 255 characters.
- **User Ownership Enforcement:** Every update and delete executes `WHERE id = %s AND user_id = %s`, preventing horizontal privilege escalation (IDOR).

---

### 9.2 Budget Watchdog & Alert Thresholds
Users can set a target spending limit for any calendar month. The system calculates current spending and determines budget health:

$$\text{Used Percentage} = \left(\frac{\text{Current Month Spend}}{\text{Monthly Budget Amount}}\right) \times 100$$

```
+------------------------------------------------------------------------------------+
|                               BUDGET HEALTH STATES                                 |
+-------------------+--------------------+---------------+---------------------------+
| SPENT PERCENTAGE  | HEALTH STATE       | UI COLOR      | SYSTEM NOTIFICATION       |
+-------------------+--------------------+---------------+---------------------------+
| 0% - 79.9%        | Normal Progress    | Green (#10b981) | None                      |
| 80.0% - 89.9%     | Approaching Limit  | Amber (#f59e0b) | "Approaching Limit (80%)" |
| 90.0% - 99.9%     | Critical Warning   | Orange (#ea580c)| "Critical Warning (90%)"  |
| 100.0%+           | Budget Exceeded    | Red (#ef4444)   | "Budget Exceeded!"        |
+-------------------+--------------------+---------------+---------------------------+
```

The `generate_user_notifications(user_id)` function checks if a notification of that type has already been emitted during the current month before creating a record, preventing duplicate alert fatigue.

---

# CHAPTER 10 — REPORTS & DATA ANALYTICS

### 10.1 SQL Data Aggregations
The analytics engine uses SQL aggregation functions (`SUM`, `COUNT`, `GROUP BY`) executed by the database engine:

1. **Category Breakdown Query:**
   ```sql
   SELECT category, SUM(amount) AS total 
   FROM expenses 
   WHERE user_id = %s AND expense_date >= %s AND expense_date < %s 
   GROUP BY category 
   ORDER BY total DESC;
   ```
2. **Daily Spending Query:**
   ```sql
   SELECT expense_date, SUM(amount) AS daily_total 
   FROM expenses 
   WHERE user_id = %s AND expense_date >= %s AND expense_date < %s 
   GROUP BY expense_date 
   ORDER BY expense_date ASC;
   ```
3. **Monthly Comparison Query:**
   ```sql
   SELECT MONTH(expense_date) AS m, YEAR(expense_date) AS y, SUM(amount) AS monthly_total 
   FROM expenses 
   WHERE user_id = %s AND expense_date >= %s 
   GROUP BY y, m 
   ORDER BY y ASC, m ASC;
   ```

---

### 10.2 Chart.js Client-Side Rendering
The aggregated numerical data is passed from Flask to Jinja2, where it is serialized into JavaScript arrays via `{{ category_labels | tojson }}` and `{{ category_totals | tojson }}`. 

Client-side JavaScript renders:
- **Doughnut Chart:** Visualizing category proportions with distinct hex color palettes.
- **Line Chart:** Showing daily spending velocity over time with smooth bezier curves.
- **Bar Chart:** Comparing total expenditure across calendar months.

---

# CHAPTER 11 — DEPLOYMENT PIPELINE & CLOUD INFRASTRUCTURE

```
+-----------------------------------------------------------------------------------+
|                           CONTINUOUS DEPLOYMENT PIPELINE                          |
+-----------------------------------------------------------------------------------+

   1. Local Git Commit
      `git add . && git commit -m "feat..." && git push origin main`
                     |
                     v
   2. GitHub Repository Webhook
      (Triggers Railway automated cloud builder)
                     |
                     v
   3. Railway PaaS Container Build
      - Clones repository
      - Installs Python 3.11+
      - Executes: `pip install -r requirements.txt`
                     |
                     v
   4. Container Process Launch via Procfile
      `web: gunicorn --workers 1 --threads 8 --bind 0.0.0.0:$PORT app:app`
                     |
                     v
   5. Runtime Environment Injection
      - Injects MYSQL_URL (Cloud database connection string)
      - Injects FLASK_SECRET_KEY
      - Injects GAS_WEBAPP_URL (Google Apps Script Webhook)
      - Injects GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET
                     |
                     v
   6. Railway Health Check Verification
      (Pings internal socket; verifies HTTP 200)
                     |
                     v
   7. Atomic Zero-Downtime Cutover
      (Routes live HTTPS traffic to new container; gracefully terminates old instance)
```

---

# CHAPTER 12 — TESTING STRATEGY & VERIFICATION METRICS

### 12.1 Automated Test Suite Architecture
The test suite is located in `tests/test_suite.py` and executed via Python’s standard `unittest` framework:
```powershell
python -m unittest tests/test_suite.py
```

#### Official Test Execution Results:
```text
Ran 56 tests in 14.819s
OK
```

#### Test Coverage Categorization:
- **Authentication Tests (14 Tests):** Registration flow, OTP validation, attempt lockouts, duplicate email rejections, login/logout sessions, and protected route barriers.
- **Google OAuth Tests (11 Tests):** Login redirect, state token generation, callback handling, new user creation, account linking, client secret failure handling, and state mismatch CSRF detection.
- **Expense CRUD Tests (12 Tests):** Add, view, edit, delete, cross-user isolation, category filtering, search queries, and pagination.
- **Budget & Alerts Tests (8 Tests):** Monthly budget creation, threshold calculations (80%, 90%, 100%), and duplicate notification prevention.
- **Export & Reporting Tests (5 Tests):** In-memory CSV export with active filters, unauthenticated export blocks, and Chart.js aggregation math.
- **Email Dispatcher Tests (6 Tests):** Verifying multi-provider fallbacks for Gmail API, Google Apps Script Webhook, Brevo API, and EmailJS.

---

# CHAPTER 13 — TECHNICAL CHALLENGES & LESSONS LEARNED

### 1. Cloud Host SMTP Port Block
* **Challenge:** On Railway, standard SMTP connections to Gmail hung and timed out.
* **Diagnosis:** Identified that cloud security groups block outbound ports 25, 465, and 587.
* **Solution:** Engineered a Google Apps Script Webhook operating over HTTPS port 443.
* **Lesson Learned:** Modern cloud deployments should never rely on raw SMTP sockets; HTTPS REST APIs are universally traversable.

### 2. Resend Sandbox Recipient Lockout
* **Challenge:** Resend API returned HTTP 403 when sending OTPs to arbitrary test users.
* **Diagnosis:** Free-tier Resend domains restrict delivery to the developer's registered email only.
* **Solution:** Switched primary email delivery to Google Apps Script native `MailApp.sendEmail()`, which delivers to any domain at ₹0 cost.
* **Lesson Learned:** Third-party developer sandboxes are unsuitable for open end-user registration without paid DNS domain ownership.

### 3. Google OAuth Restricted Scope Rejection
* **Challenge:** Authorizing `gmail.send` via standard Google OAuth resulted in `Error 403: access_denied` during evaluation.
* **Diagnosis:** Google classifies `gmail.send` as a sensitive scope requiring weeks of organizational verification.
* **Solution:** Separated user authentication from email delivery. Google OAuth handles user login with basic `openid email profile` scopes, while Google Apps Script handles email delivery under the developer's personal account.
* **Lesson Learned:** Decoupling authentication scopes from background transactional utilities simplifies regulatory and verification hurdles.

### 4. Google Drive Multi-Account Cookie Conflict
* **Challenge:** Authorizing Google Apps Script in standard browser sessions resulted in *"Sorry, unable to open the file at present"*.
* **Diagnosis:** Having multiple Google accounts active in one browser causes Google Drive authorization cookies to clash between `/u/0` and `/u/1`.
* **Solution:** Deployed and authorized the script within an Incognito / Private window with a single active Google session.
* **Lesson Learned:** Multi-tenant OAuth authorizations in development environments require isolated browser contexts.

---

# CHAPTER 14 — SECURITY ARCHITECTURE & DEFENSE-IN-DEPTH

```
+-----------------------------------------------------------------------------------+
|                        DEFENSE-IN-DEPTH SECURITY MATRIX                           |
+-----------------------+----------------------------------+------------------------+
| THREAT VECTOR         | SECURITY MECHANISM APPLIED       | CODEBASE FILE / LINE   |
+-----------------------+----------------------------------+------------------------+
| Password Cracking     | PBKDF2-SHA256 (16-byte salt)     | app.py, werkzeug       |
| OTP Brute Force       | 5-attempt limit, 10-minute TTL   | app.py, auth_otps      |
| Database Credential   | OTPs stored as PBKDF2 hashes     | app.py, db_create_otp  |
| SQL Injection         | 100% Parameterized queries       | app.py, cursor.execute |
| CSRF Attacks          | 32-byte HMAC synchronizer token  | app.py, csrf_protect   |
| OAuth Login CSRF      | Cryptographic random state token | app.py, google_login   |
| IDOR / Data Tampering | Mandatory user_id session checks | app.py (All CRUD views)|
| Session Hijacking     | HttpOnly, SameSite=Lax, Secure   | app.py, app.config     |
| Clickjacking          | X-Frame-Options: SAMEORIGIN      | app.py, set_sec_headers|
| MIME Sniffing         | X-Content-Type-Options: nosniff  | app.py, set_sec_headers|
| Information Leakage   | Sanitized custom error pages     | templates/error.html   |
+-----------------------+----------------------------------+------------------------+
```

---

# CHAPTER 15 — COMPLETE USER JOURNEYS (STEP-BY-STEP)

### Journey 1: New User Registration & Verification
1. **User Action:** Visits `/register`, enters Name, Email, and Password, and clicks "Create Account".
2. **Backend Processing:**
   - Validates CSRF token.
   - Checks if email exists in `users`.
   - Generates 6-digit OTP via `secrets.randbelow(900000) + 100000`.
   - Hashes OTP via `generate_password_hash(otp)`.
   - Inserts record into `auth_otps` table with `purpose='registration'`.
   - Calls `dispatch_email()` -> Google Apps Script Webhook -> User Inbox.
   - Redirects user to `/verify-otp?email=...`.
3. **User Action:** Opens email, copies OTP, pastes it on `/verify-otp`, and submits.
4. **Backend Processing:**
   - Fetches active OTP record.
   - Checks attempt counter (`attempts < 5`) and expiration timestamp.
   - Compares hash via `check_password_hash()`.
   - Inserts new user into `users` table with hashed password.
   - Marks OTP as `is_used = TRUE`.
   - Flashes success message and redirects to `/login`.

---

### Journey 2: Google OAuth 2.0 Login
1. **User Action:** Clicks "Continue with Google" on `/login`.
2. **Backend Processing:**
   - Generates random `state` token and stores it in `session['google_oauth_state']`.
   - Redirects browser to `https://accounts.google.com/o/oauth2/v2/auth`.
3. **User Action:** Authenticates at Google and grants profile consent.
4. **Backend Processing:**
   - Google redirects to `/login/google/callback?code=...&state=...`.
   - Verifies `state` parameter matches `session['google_oauth_state']` using `hmac.compare_digest`.
   - Sends server-side POST to `https://oauth2.googleapis.com/token` to exchange authorization code for access token.
   - Queries `https://www.googleapis.com/oauth2/v2/userinfo`.
   - Checks if Google email exists in `users`:
     - If user exists: links `google_id` and logs them in.
     - If user is new: inserts record into `users` with `auth_provider='google'` and redirects to `/set-password`.
   - Stores `user_id` in `session` and redirects to `/dashboard`.

---

### Journey 3: Adding an Expense & Triggering Budget Alert
1. **User Action:** Navigates to `/expenses/add`, enters Amount (₹2,500), Category (Food), Payment Method (UPI), Date (Today), Description ("Team Lunch"), and submits.
2. **Backend Processing:**
   - `@login_required` confirms active session.
   - Verifies CSRF token.
   - Validates that amount is a positive decimal and category is in whitelist.
   - Executes:
     ```sql
     INSERT INTO expenses (user_id, amount, category, payment_method, expense_date, description)
     VALUES (%s, %s, %s, %s, %s, %s);
     ```
   - Calls `generate_user_notifications(user_id)`.
   - Computes total monthly spend including the new ₹2,500.
   - Detects that total spend now equals 92% of the user's monthly budget.
   - Checks `notifications` table; sees that `budget_90` has not yet been triggered this month.
   - Inserts a new row into `notifications`:
     ```sql
     INSERT INTO notifications (user_id, type, title, message, action_url)
     VALUES (%s, 'budget_90', 'Critical Budget Warning', 'You have used 92% of your monthly budget.', '/budget');
     ```
   - Redirects to `/expenses` with success message.
3. **User Experience:** The navigation bell badge immediately displays an incremented unread count (`1`), and the dashboard budget bar updates to the warning color state.

---

# CHAPTER 16 — TECHNICAL GLOSSARY

* **ACID:** Atomicity, Consistency, Isolation, Durability — the four fundamental properties that guarantee reliable database transactions in relational databases like MySQL.
* **API:** Application Programming Interface — a structured contract that allows two software programs (such as Flask and Google Apps Script) to communicate.
* **B-Tree Index:** A balanced tree data structure maintained by MySQL to speed up search queries from O(N) linear scans to O(log N) logarithmic lookups.
* **CSPRNG:** Cryptographically Secure Pseudo-Random Number Generator — an entropy-backed random generator (such as Python’s `secrets` module) whose outputs cannot be predicted by attackers.
* **CSRF:** Cross-Site Request Forgery — an exploit where an unauthorized site transmits malicious commands to a web app on behalf of an authenticated user.
* **Gunicorn:** A production Python WSGI HTTP server capable of managing concurrent worker processes and threads.
* **HMAC:** Hash-based Message Authentication Code — a cryptographic message authentication code used for constant-time equality comparisons (`hmac.compare_digest`).
* **IDOR:** Insecure Direct Object Reference — a security vulnerability where an application provides direct access to objects based on user-supplied input without verifying ownership.
* **Jinja2:** The default template engine for Flask, providing automatic HTML escaping and template inheritance.
* **OAuth 2.0:** An industry-standard authorization framework enabling third-party applications to obtain limited access to user accounts on an HTTP service (such as Google).
* **PBKDF2:** Password-Based Key Derivation Function 2 — an algorithm that applies a cryptographic hash function repeatedly with a salt to slow down brute-force cracking.
* **ProxyFix:** A Werkzeug middleware component that adjusts WSGI environment variables based on HTTP reverse proxy headers (`X-Forwarded-Proto`, `X-Forwarded-For`).
* **Salt:** Random bytes appended to passwords prior to hashing to ensure that identical passwords yield distinct cryptographic hashes.
* **TTL:** Time-To-Live — the lifespan or expiration duration of a temporary credential, such as our 10-minute OTP expiration window.
* **WSGI:** Web Server Gateway Interface — the standardized universal specification describing how Python web servers forward requests to web application frameworks.
