# ExpenseFlow (DailyExpenseTracker) — Presentation Deck & Project Defense Guide

This document contains a complete, slide-by-slide presentation outline, visual presentation structure, and word-for-word speaking scripts for project reviews, seminars, capstone evaluations, and final defense presentations.

---

## 🎙️ Spoken Presentation Scripts

### A. 30-Second Elevator Pitch
> *"Good morning, respected professors. My project is **ExpenseFlow**, a secure, full-stack personal finance web application built using Python, Flask, and MySQL. It helps users gain control of their financial habits by tracking daily cash and digital expenses, enforcing monthly budget limits with automatic threshold alerts, and visualizing spending patterns using dynamic Chart.js reports. The application features dual authentication via email and Google OAuth 2.0, cryptographically hashed OTP verification, and a resilient, zero-cost HTTPS email delivery pipeline deployed live on Railway cloud infrastructure."*

---

### B. 1-Minute Project Summary
> *"Good morning. Most personal finance tracking fails because spreadsheets are too cumbersome and commercial apps demand direct access to bank accounts. I developed **ExpenseFlow** to give individuals a private, seamless, and automated platform for financial tracking.*
>
> *Built on a clean Python and Flask architecture paired with a cloud MySQL database, ExpenseFlow allows users to record transactions across eleven categories and six payment methods, including UPI and cards. The system actively monitors monthly budgets: when spending reaches 80%, 90%, or 100% of a target limit, the application triggers persistent smart notifications. Users can filter expenses with multi-field search and download CSV reports.*
>
> *Security was a primary focus: all passwords and OTPs are hashed using PBKDF2-SHA256, transactions are strictly isolated per user, and CSRF protection is enforced across all state changes. To overcome cloud host SMTP port blocks, I engineered a zero-cost transactional email pipeline using a Google Apps Script HTTPS webhook. The system is live on Railway with fifty-six automated tests validating its stability."*

---

### C. 3-Minute Technical Presentation
> *"Respected evaluators, today I am presenting **ExpenseFlow**, a production-deployed personal expense tracker designed from the ground up to address financial discipline, data privacy, and cloud reliability.*
>
> *Let's look at the core architecture. The backend is powered by Python and Flask running on a Gunicorn WSGI server. On the database layer, instead of relying on an opaque ORM, I utilized direct, parameterized SQL queries via `mysql-connector-python` to an ACID-compliant MySQL database. This ensures complete control over indexing, query execution plans, and transaction boundaries.*
>
> *Our database schema consists of six relational tables with strict foreign key constraints and `ON DELETE CASCADE` cascading deletes. User data isolation is non-negotiable: every single SQL query filters on the authenticated user's session ID, preventing Insecure Direct Object References.*
>
> *For identity management, the platform supports dual authentication. Users can register with email and password—verified via a 6-digit OTP hashed in MySQL with a 10-minute expiry and a 5-attempt lockout—or authenticate with 1-click Google OAuth 2.0. The OAuth implementation validates a cryptographically random state parameter to eliminate login CSRF attacks and automatically links Google accounts to existing email registrations.*
>
> *One of our most interesting engineering challenges was transactional email delivery. When deploying to Railway, we discovered that cloud providers permanently block outbound SMTP ports 25, 465, and 587 to prevent spam. Furthermore, free API sandbox tiers restrict sending to only the developer's registered address. To achieve a 100% reliable, zero-cost solution for arbitrary users, I architected an HTTPS webhook pipeline powered by Google Apps Script. Outbound requests travel over standard HTTPS port 443 to Google’s native MailApp API, delivering OTPs to any email domain with full SPF and DKIM signatures.*
>
> *On the frontend, ExpenseFlow uses a responsive glassmorphism UI built in vanilla CSS and Jinja2 template inheritance, with Chart.js generating interactive doughnut, line, and bar analytics from server-side SQL aggregations. The application is live on Railway, backed by fifty-six passing automated unit and integration tests."*

---

### D. 5-Minute Comprehensive Project Defense Script
> *(See complete slide-by-slide script below for the full 5-minute walkthrough.)*

---

## 🖥️ Slide-by-Slide Presentation Structure

### Slide 1: Title Slide
* **Title:** ExpenseFlow — Modern Personal Expense Tracker & Financial Intelligence System
* **Subtitle:** Full-Stack Web Application with Dual Authentication & Cloud Resilience
* **Presenter:** Student / Developer Name
* **Institution:** Alliance University
* **Tech Stack:** Python 3 | Flask | MySQL | Google OAuth 2.0 | Chart.js | Railway

---

### Slide 2: Problem Statement & Motivation
* **The Problem:**
  * 70%+ of young professionals and students experience monthly budget overruns due to untracked micro-spending.
  * Excel/Spreadsheets have high friction, poor mobile experiences, and zero automated alerts.
  * Commercial fintech apps demand invasive bank account and credit bureau permissions.
* **Our Solution:**
  * A lightweight, privacy-focused, cross-platform web application for intentional expense tracking.
  * Real-time budget progress with visual health states (Normal, Warning, Exceeded).
  * 100% free and accessible from any smartphone, tablet, or desktop browser.

---

### Slide 3: Objectives & Key Features
* **Key Functional Objectives:**
  * **Dual Authentication:** Email/Password registration with OTP verification + 1-Click Google OAuth 2.0.
  * **Expense CRUD & Intelligence:** Multi-category tracking (Food, Transport, Rent, etc.) and Tender tracking (Cash, UPI, Card).
  * **Advanced Search & Filtering:** Filter by keyword, category, date ranges, and min/max amounts with instant CSV export.
  * **Budget Watchdog Engine:** Automatic monthly budget tracking with 80%, 90%, and 100% smart alerts.
  * **Interactive Analytics:** Visual category doughnut charts, daily spending trends, and month-over-month comparisons via Chart.js.

---

### Slide 4: System Architecture
* **Tiered Cloud Architecture:**
  * **Client Layer:** Responsive HTML5 / Vanilla CSS / ES6 JavaScript.
  * **Edge Layer:** Railway Ingress & Cloudflare TLS 1.3 reverse proxy termination.
  * **Application Layer:** Gunicorn WSGI Server (1 worker, 8 threads) driving Flask 3.1.3.
  * **Database Layer:** Cloud MySQL 8.0 with B-tree composite indexing and relational constraints.
  * **Integration Layer:** Google Identity Services (OAuth 2.0) and Google Apps Script Webhook (HTTPS Port 443).

---

### Slide 5: Database Engineering & Data Integrity
* **Relational Schema Design (6 Tables):**
  * `users` — Primary account registry and OAuth linking IDs.
  * `expenses` — Transaction ledgers with `ON DELETE CASCADE` foreign keys.
  * `budgets` — Spending limits with composite unique constraint `(user_id, month, year)`.
  * `notifications` — Alert queue for budget warnings and system events.
  * `auth_otps` — Security store holding PBKDF2-hashed OTP verification codes.
  * `app_settings` — Dynamic runtime configuration repository.
* **Data Integrity Principles:**
  * Strict usage of `DECIMAL(12, 2)` to eliminate floating-point rounding drift in accounting.
  * Parameterized SQL queries preventing SQL Injection.
  * Transaction lifecycle managed via `@app.teardown_request` (`commit` / `rollback`).

---

### Slide 6: Authentication & Security Architecture
* **Layered Defense-in-Depth:**
  * **Password Security:** Salted PBKDF2-SHA256 password hashing via Werkzeug.
  * **OTP Engine:** 6-digit CSPRNG tokens, PBKDF2-hashed in MySQL, 10-minute expiry, locked after 5 failed attempts.
  * **Google OAuth 2.0:** Secure authorization code exchange with CSRF `state` parameter validation.
  * **CSRF Protection:** Synchronizer token pattern with constant-time HMAC validation on all POST requests.
  * **Session Security:** `HttpOnly`, `SameSite=Lax`, and `Secure` cookie attributes.
  * **User Data Isolation:** Mandatory session checks preventing horizontal privilege escalation (IDOR).

---

### Slide 7: Engineering Challenge — The ₹0 Cloud Email Architecture
* **The Cloud Obstacle:**
  * Railway permanently blocks outbound SMTP ports (`25`, `465`, `587`).
  * Resend API's free sandbox blocks all recipients except the developer's registered account (HTTP 403).
  * Custom domain verification requires paid DNS domain ownership.
* **The Solution — Google Apps Script HTTPS Webhook:**
  * Built an HTTPS webhook using Google Apps Script executing under the developer's Google account.
  * Flask posts JSON payloads to Port 443; Google Apps Script executes native `MailApp.sendEmail()`.
  * **Outcome:** Delivers 100 free OTP emails per day to *any* recipient worldwide with full Google SPF/DKIM authentication at ₹0 cost.

---

### Slide 8: Verification & Testing Results
* **Automated Test Suite:**
  * Built using Python’s native `unittest` framework (`tests/test_suite.py`).
  * **56 Automated Tests** covering authentication, OTP limits, CRUD isolation, search filtering, CSV export, budget warnings, and email dispatchers.
  * **100% Pass Rate:** Executes in under 15 seconds with 0 errors and 0 failures.
* **Live Smoke Testing:**
  * Live automated production verification (`scripts/verify_production_live.py`).
  * Verified DB health (`/test-db`), route protection, CSRF enforcement, and live OTP email dispatch.

---

### Slide 9: Advantages & Innovations
* **Why ExpenseFlow Stands Out:**
  * **Zero Operating Cost:** Operates 100% on free-tier cloud infrastructure (Railway + Google Apps Script + Cloud MySQL).
  * **No Frontend Bloat:** 78KB unified CSS with zero node_modules or Webpack overhead.
  * **High Privacy:** No bank credential scraping or third-party tracking cookies.
  * **Resilient Infrastructure:** Active database connection pinging and multi-provider email fallback.

---

### Slide 10: Limitations & Future Scope
* **Current Limitations:**
  * Google Apps Script free quota is 100 emails/24 hours (backed up by Brevo's 300/day).
  * Expenses require manual logging rather than automatic bank feed synchronization.
* **Future Roadmap:**
  * **AI Receipt OCR:** Scanning paper receipts using Tesseract or Google Cloud Vision.
  * **Progressive Web App (PWA):** Offline transaction caching and home screen installation.
  * **Multi-Currency Engine:** Automatic currency conversion for international transactions.

---

### Slide 11: Conclusion & Live Demonstration
* **Project Status:** 100% Complete, Tested, and Deployed Live.
* **Live Deployment URL:** `https://dailyexpensetracker-production-bf76.up.railway.app`
* **GitHub Repository:** `https://github.com/ngkrishnaa/DailyExpenseTracker`
* **Thank You! Questions & Discussion Welcome.**
