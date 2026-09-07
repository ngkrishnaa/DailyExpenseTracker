# ExpenseFlow (DailyExpenseTracker) — 10-Minute Viva Quick Reference Sheet

Keep this one-page summary open right before your project presentation or viva examination.

---

## ⚡ High-Priority Fact Sheet

| Question Prompt | The 10-Second Viva Answer |
| :--- | :--- |
| **What is the project?** | **ExpenseFlow** is a full-stack personal finance web application built in Python/Flask and MySQL for tracking expenses, managing monthly budgets, viewing visual reports, and exporting financial data with secure dual authentication (Password + Google OAuth). |
| **What is the live URL?** | `https://dailyexpensetracker-production-bf76.up.railway.app` |
| **What is the backend?** | **Python 3.11+** with **Flask 3.1.3**, running under **Gunicorn 23.0.0** with 1 worker and 8 threads. |
| **What is the database?** | **MySQL 8.0** hosted on Railway Cloud, connected via the official **mysql-connector-python** library using raw parameterized SQL queries (no ORM). |
| **What is the frontend?** | **Jinja2** HTML5 templates, **Vanilla ES6+ JavaScript**, and custom responsive **Vanilla CSS** (78KB design system, glassmorphism UI). Zero frontend framework bloat. |
| **What chart library is used?** | **Chart.js 4.4.1** (via CDN) rendering responsive HTML5 Canvas charts (Category Doughnut, Daily Line Trend, Monthly Comparison Bar). |
| **How does login work?** | Two options: **Local Auth** (Email + PBKDF2-SHA256 hashed password) and **Google OAuth 2.0** (Authorization Code flow with CSRF state token and auto-account linking). |
| **How does OTP work?** | 6-digit CSPRNG code (`secrets.randbelow(900000) + 100000`), hashed via PBKDF2 in MySQL `auth_otps`, valid for 10 minutes, strictly locked to maximum 5 attempts, single-use invalidation. |
| **How are emails sent?** | Primary production delivery via **Google Apps Script Webhook** (`https://script.google.com/macros/s/.../exec`) over **HTTPS Port 443** using native Google MailApp at ₹0 cost, reaching any email worldwide. |
| **Why didn't SMTP work?** | Railway cloud hosting permanently blocks outbound SMTP ports (`25`, `465`, `587`) to prevent spam abuse. HTTPS REST APIs bypass port blocks completely. |
| **Where is it hosted?** | **Railway Cloud Platform** with automated CI/CD from the GitHub `main` branch, managed cloud MySQL, and automated SSL termination. |

---

## 🛡️ Security Mechanisms in 30 Seconds
1. **Passwords:** Hashed with Werkzeug `PBKDF2-SHA256` and unique 16-byte random salts. Never stored in plaintext.
2. **OTPs:** Stored as PBKDF2 hashes in `auth_otps` table. Cannot be stolen even from raw database dumps.
3. **CSRF Protection:** Synchronizer token pattern with 32-byte secret (`secrets.token_hex(32)`) and constant-time validation (`hmac.compare_digest`).
4. **SQL Injection:** 100% prevented through parameterized queries (`cursor.execute(sql, params)`); zero string concatenation.
5. **Cross-User Data Isolation:** Every query enforces `WHERE user_id = session['user_id']`. User A can never access User B's records.
6. **Error Sanitization:** Production errors mask stack traces and database credentials to prevent information leakage.
7. **Session Cookies:** `HttpOnly=True`, `SameSite="Lax"`, `Secure=True` in production.

---

## 🗄️ Database Schema At A Glance (6 Tables)
1. **`users`:** `id` (PK), `name`, `email` (UNIQUE), `password` (NULL for Google users), `google_id`, `auth_provider`, `has_set_password`, `created_at`.
2. **`expenses`:** `id` (PK), `user_id` (FK -> users, ON DELETE CASCADE), `amount` (`DECIMAL(12, 2)`), `category`, `expense_date`, `payment_method`, `description`.
3. **`budgets`:** `id` (PK), `user_id` (FK -> users), `budget_amount`, `month`, `year`, `UNIQUE(user_id, month, year)`.
4. **`notifications`:** `id` (PK), `user_id` (FK -> users), `type`, `title`, `message`, `is_read`, `action_url`.
5. **`auth_otps`:** `id` (PK), `email`, `otp_hash`, `purpose` ('registration'/'password_reset'), `token`, `attempts`, `max_attempts` (5), `expires_at`, `is_used`.
6. **`app_settings`:** `setting_key` (PK), `setting_value`, `updated_at`.

---

## 📊 Key Numbers & Facts
- **Automated Tests:** **56 tests**, 100% passing (`Ran 56 tests in ~15s - OK`).
- **Registered Routes:** **30 routes** across authentication, expense management, budgeting, reports, and system diagnostics.
- **Categories Supported (11):** Food, Transportation, Shopping, Bills, Entertainment, Health, Education, Travel, Groceries, Rent, Other.
- **Payment Methods (6):** Cash, Credit Card, Debit Card, UPI, Bank Transfer, Other.
- **Budget Alerts:** 80% (Warning), 90% (Critical Warning), >100% (Budget Exceeded).
- **Email Providers Configured:** Google Apps Script Webhook (Priority 1), Gmail REST API (Priority 2), Brevo API (Priority 3), EmailJS (Priority 4), Resend (Fallback).

---

## 💡 "Why Did You Choose..." — Rapid Fire Answers
- **Why Flask instead of Django?** Lightweight, microframework control, no bloated ORM, clean manual SQL and middleware execution.
- **Why MySQL instead of SQLite?** ACID compliance, true multi-user concurrent write capability, persistent cloud storage on Railway.
- **Why `DECIMAL(12, 2)` instead of `FLOAT`?** Exact fixed-point numeric precision; binary floating point introduces penny rounding errors.
- **Why Google Apps Script for Email?** Bypasses cloud host SMTP firewall blocks (Port 443), delivers to any recipient domain, requires ₹0 cost, and has zero custom domain DNS requirements.
- **Why Gunicorn?** Production-grade WSGI application server with concurrent worker threads, unlike the single-threaded development server.
- **Why `ProxyFix`?** Informs Flask that it is behind an HTTPS reverse proxy on Railway, ensuring secure cookies and correct redirect protocols.
