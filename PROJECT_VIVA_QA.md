# ExpenseFlow (DailyExpenseTracker) — Comprehensive Viva & Technical Interview Guide

This document contains **55 realistic, highly technical questions and answers** designed specifically for university capstone project defenses, viva voce examinations, and technical software engineering interviews. 

Each question provides:
- **SHORT ANSWER:** A concise, punchy 1–3 sentence response you can deliver confidently in an oral examination.
- **DETAILED ANSWER:** The in-depth technical explanation covering the exact codebase mechanisms, algorithms, security considerations, and trade-offs.

---

## Section 1: General Project & System Overview

### Q1: What is ExpenseFlow and what core problem does it solve?
* **SHORT ANSWER:** ExpenseFlow is a full-stack personal finance web application that enables users to record daily expenses, categorize transactions, set monthly budgets, receive threshold warnings, and visualize spending habits through interactive charts. It solves the widespread problem of financial unawareness by replacing manual, error-prone spreadsheets with automated budgeting, transaction tracking, and CSV exports.
* **DETAILED ANSWER:** Most individuals struggle with financial discipline due to the friction of tracking daily cash and digital transactions across multiple payment methods. ExpenseFlow provides a centralized platform featuring verified user accounts, dual authentication (local credentials and Google OAuth 2.0), automated budget progress tracking, real-time alert notifications when approaching 80%, 90%, and 100% of monthly budgets, interactive Chart.js reports, and filterable CSV exports. The application is production-deployed on Railway paired with a cloud MySQL database and a resilient HTTPS multi-provider email pipeline.

### Q2: Why did you choose to build a web application instead of a native mobile app?
* **SHORT ANSWER:** A web application provides universal cross-platform accessibility across Windows, macOS, Linux, Android, and iOS without requiring app store approvals or separate codebases. Using mobile-first responsive CSS and standard web APIs allowed me to deliver an app-like experience accessible from any browser on any device.
* **DETAILED ANSWER:** Developing native mobile applications for iOS and Android requires maintaining two codebases (Swift/Kotlin) or adopting cross-platform wrappers (React Native/Flutter), which introduces complex build toolchains and app store publishing delays. By developing ExpenseFlow as a responsive web app using Flask and clean modern CSS (with CSS Grid and Flexbox), the application functions seamlessly on desktop monitors and mobile touchscreens alike. Furthermore, cloud updates and database migrations deployed to Railway are instantly live for all users without requiring client-side updates.

### Q3: What makes this project qualify as a real-world software system rather than a student prototype?
* **SHORT ANSWER:** Unlike basic student prototypes that run only on localhost with SQLite, ExpenseFlow is deployed to live cloud infrastructure with a production WSGI server (Gunicorn), a remote MySQL database with foreign key constraints, Google OAuth 2.0 integration, PBKDF2 cryptographic password and OTP hashing, automated CSRF protection, and a multi-provider fallback email delivery system.
* **DETAILED ANSWER:** Real-world systems require rigorous non-functional requirements: fault tolerance, connection recovery, transport security, data isolation, and defensiveness. ExpenseFlow implements:
  1. **Strict User Data Isolation:** Every query enforces user ownership boundaries (`WHERE user_id = %s`), completely preventing unauthorized horizontal privilege escalation.
  2. **Zero Plaintext Security:** Passwords and OTP verification codes are hashed using PBKDF2-SHA256 with cryptographically random salts.
  3. **Cloud Port Workarounds:** Bypasses cloud host SMTP firewall blocks by routing transactional emails over HTTPS REST APIs.
  4. **Automated Verification:** Tested with 56 automated unit and integration tests covering security, edge cases, and API failures.

### Q4: Who are the target users of this platform?
* **SHORT ANSWER:** Students, young working professionals, freelancers, and household budget managers who need a private, secure, and intuitive tool to track personal expenses, monitor category spending, and prevent budget overruns without linking sensitive bank credentials.
* **DETAILED ANSWER:** Many commercial personal finance platforms (such as Mint or YNAB) demand direct integration with bank accounts via third-party aggregators (like Plaid), which many privacy-conscious users hesitate to permit. ExpenseFlow targets users who prefer manual, intentional transaction logging across multiple tender types (Cash, UPI, Credit Card, Net Banking) combined with visual analytics, custom monthly budgets, and zero subscription costs.

### Q5: What are the primary functional requirements of the system?
* **SHORT ANSWER:** Secure user registration with OTP verification, user login via password or Google OAuth 2.0, full CRUD operations on expense records, multi-parameter search and filtering, CSV transaction export, monthly budget targets with warning states, interactive spending charts, and profile/password management.
* **DETAILED ANSWER:** The system’s functional requirements encompass:
  1. **Identity Management:** Registration, email verification, local login, Google OAuth 2.0 social login, account linking, password reset via OTP, and session termination.
  2. **Expense Management:** Adding, editing, soft/hard deleting expenses, categorized by 11 domains and 6 payment methods, with search, category filtering, date-range filtering, and pagination.
  3. **Financial Intelligence:** Monthly budget thresholds (80% warning, 90% critical, >100% exceeded) triggering automated notification records.
  4. **Reporting:** Aggregating transactions into category distribution doughnuts, daily expenditure lines, and month-over-month comparison bars.

### Q6: What are the primary non-functional requirements of the system?
* **SHORT ANSWER:** Security (salted password hashing, CSRF tokens, secure session cookies), performance (sub-second response times, indexed database queries), data integrity (ACID relational constraints), reliability (automatic database reconnects), and usability (mobile responsiveness and error sanitization).
* **DETAILED ANSWER:** Non-functional specifications include:
  - **Security:** Strict prevention of OWASP Top 10 vulnerabilities including SQL Injection (parameterized queries), CSRF (HMAC token checks), XSS (Jinja auto-escaping), and Broken Access Control (ownership verification).
  - **Performance:** Optimized MySQL queries utilizing composite B-tree indexes (`idx_expenses_user_date`, `idx_expenses_user_category`).
  - **Fault Tolerance:** Automatic database ping and reconnection logic (`db.ping(reconnect=True)`) preventing MySQL timeout crashes.
  - **Privacy:** Strict sanitization of error messages to avoid leaking database schema details or stack traces to end users.

---

## Section 2: Architecture & Web Framework

### Q7: Why did you choose Flask instead of Django or FastAPI?
* **SHORT ANSWER:** Flask is a lightweight microframework that provides complete architectural freedom without the bloated overhead and rigid conventions of Django. It allowed me to write clean, optimized parameterized SQL queries directly with `mysql-connector-python` rather than relying on an opaque ORM, while keeping the dependency footprint minimal.
* **DETAILED ANSWER:** Django ships with an extensive built-in ORM, admin panel, and authentication system that often abstracts away fundamental computer science concepts. In an educational and professional evaluation context, building with Flask demonstrates mastery of the complete HTTP request lifecycle, manual session handling, custom security decorators, direct SQL transaction management, and explicit middleware construction. FastAPI, while modern, is designed primarily for asynchronous headless REST APIs rather than server-side rendered applications utilizing Jinja templates and session cookies.

### Q8: What is Gunicorn and why is it used in production instead of the Flask development server?
* **SHORT ANSWER:** Gunicorn is a production-grade Web Server Gateway Interface (WSGI) HTTP server. The built-in Flask development server is single-threaded, unoptimized, and explicitly marked unsafe for production; Gunicorn handles concurrent worker threads, process management, and high traffic reliably.
* **DETAILED ANSWER:** The standard `flask run` server is designed strictly for local debugging: it lacks robust socket management, connection pooling, and process monitoring. In our Railway production environment, Gunicorn (`gunicorn 23.0.0`) is launched via the `Procfile`:
`web: gunicorn --workers 1 --threads 8 --bind 0.0.0.0:$PORT app:app`
This configuration spawns a master process with 8 concurrent execution threads, allowing the server to process concurrent user requests simultaneously while sharing memory-resident data structures within the Python runtime.

### Q9: What is WSGI and what role does it play?
* **SHORT ANSWER:** WSGI stands for Web Server Gateway Interface. It is a standard specification (PEP 3333) that describes how a Python web server (like Gunicorn) communicates with a Python web application (like Flask).
* **DETAILED ANSWER:** Before WSGI, web servers had no standardized method to forward incoming HTTP requests to Python applications. WSGI defines a universal interface: the server accepts the raw HTTP socket connection, parses the request headers into an `environ` dictionary, and passes it to the Flask callable along with a `start_response` callback. Flask executes routing and controller logic, then returns an iterable byte stream representing the HTTP response body back to the WSGI server.

### Q10: What is `ProxyFix` in `app.wsgi_app` and why is it essential on Railway?
* **SHORT ANSWER:** `ProxyFix` is a Werkzeug middleware that inspects reverse-proxy headers like `X-Forwarded-For` and `X-Forwarded-Proto`. It tells Flask that the application is running behind a secure HTTPS reverse proxy, ensuring that redirect URLs and secure cookies correctly use `https://` instead of `http://`.
* **DETAILED ANSWER:** When deployed on cloud platforms like Railway, public HTTPS traffic is terminated at Railway's cloud edge router. The router forwards traffic internally to our Gunicorn container over plain HTTP. Without `ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)`, Flask would believe incoming requests arrived via unencrypted `http://`, resulting in insecure URL generation (`url_for`), failing Google OAuth redirect URI checks, and refusing to emit `Secure` session cookies.

### Q11: Explain the complete lifecycle of an HTTP request in your application.
* **SHORT ANSWER:** The browser sends an HTTPS request to Railway -> Railway terminates SSL and forwards to Gunicorn -> Gunicorn dispatches a worker thread to Flask -> `@app.before_request` verifies the database connection and CSRF token -> Flask routes to the view function -> The view performs business logic and queries MySQL -> Jinja renders the template -> `@app.after_request` attaches security headers -> `@app.teardown_request` commits or rolls back the MySQL transaction -> Response is returned to the user.
* **DETAILED ANSWER:** The end-to-end lifecycle proceeds through six distinct stages:
  1. **Network Ingress:** Client performs TLS handshake with Railway's load balancer; request is routed to Gunicorn socket.
  2. **Pre-Request Hooks (`@app.before_request`):** Verifies database socket health via `ensure_db_connection()`; ensures CSRF token exists in user session; checks CSRF token match on modifying verbs (POST/PUT/DELETE); verifies whether Google signup requires password setup.
  3. **Routing & Authentication:** Route decorator matches URL pattern and HTTP method; `@login_required` verifies `session['user_id']`.
  4. **Controller Execution:** View extracts validated form inputs, executes parameterized SQL queries, computes aggregates, and calls external APIs if needed.
  5. **Context Processor & View Rendering:** `inject_global_context()` populates notifications and unread counts; Jinja compiles HTML.
  6. **Teardown Hook (`@app.teardown_request`):** Finalizes the active database transaction (`db.commit()` on success, `db.rollback()` on uncaught error) and returns response headers.

### Q12: How does Flask manage user sessions without a separate cache like Redis?
* **SHORT ANSWER:** Flask uses cryptographically signed client-side session cookies. The entire session payload is serialized, base64-encoded, and signed using HMAC-SHA256 with the secret `FLASK_SECRET_KEY`, preventing client tampering while storing the session directly in the user's browser.
* **DETAILED ANSWER:** Instead of maintaining a server-side session table or Redis cluster, Flask’s default session interface stores session data inside an HTTP cookie (`session`). The cookie content is readable by the client but tamper-proof: any modification by the user invalidates the cryptographic signature, causing Flask to discard the session. We harden this cookie by setting `SESSION_COOKIE_HTTPONLY=True` (inaccessible to client JavaScript, preventing XSS theft), `SESSION_COOKIE_SAMESITE="Lax"` (mitigating CSRF), and `SESSION_COOKIE_SECURE=True` in production.

---

## Section 3: Frontend & User Interface Architecture

### Q13: What templating engine is used and what is template inheritance?
* **SHORT ANSWER:** We use Jinja2. Template inheritance is a software pattern where a master template (`dashboard_base.html`) defines the foundational HTML structure, CSS links, and navbar, while child templates (`dashboard.html`, `expenses.html`, `reports.html`) override specific `{% block content %}` areas, eliminating code duplication.
* **DETAILED ANSWER:** Jinja2 compiles Python-like expressions into optimized Python bytecode at runtime. In our application, `templates/dashboard_base.html` defines the universal shell: the responsive navigation sidebar, mobile drawer, flash alert notification banner, CSRF meta tags, Chart.js CDN scripts, and user profile badges. Child templates extend this base template using `{% extends "dashboard_base.html" %}`, allowing individual pages to define only their unique tables, forms, and canvas elements while inheriting all global styling and security controls.

### Q14: How are charts generated on the Reports page?
* **SHORT ANSWER:** Flask executes SQL aggregation queries (`SUM(amount)`, `GROUP BY category`), formats the numbers into lists of labels and float values, and injects them into the Jinja template as JSON. On page load, client-side Chart.js reads these arrays and renders responsive HTML5 Canvas charts.
* **DETAILED ANSWER:** In `reports()` view in `app.py`:
  1. MySQL executes `SELECT category, SUM(amount) FROM expenses WHERE user_id = %s GROUP BY category`.
  2. The decimal amounts are converted to floats to avoid JSON serialization errors.
  3. The lists are passed to `reports.html` and rendered into safe JavaScript variables using `{{ category_labels | tojson }}` and `{{ category_totals | tojson }}`.
  4. Client-side JavaScript initializes a `new Chart(ctx, { type: 'doughnut', data: { ... } })` and a line chart for daily spending trends.

### Q15: How is mobile responsiveness achieved without front-end CSS frameworks like Bootstrap?
* **SHORT ANSWER:** We implemented a custom CSS design system (`/static/css/style.css`, 78KB) utilizing fluid CSS Grid layouts, Flexbox alignment, and CSS `@media (max-width: 768px)` breakpoints, complemented by a JavaScript-driven mobile hamburger drawer.
* **DETAILED ANSWER:** Frameworks like Bootstrap inject hundreds of unused classes. Our vanilla CSS defines a streamlined design system using CSS Custom Properties (`--bg-primary`, `--accent-blue`, `--glass-bg`). On viewports below 768px:
  - Multi-column dashboard stat grids collapse from `repeat(4, 1fr)` to `repeat(1, 1fr)`.
  - The desktop navigation sidebar converts into a hidden off-canvas drawer toggled via a hamburger button.
  - Expense tables gain horizontal scroll containers (`overflow-x: auto`) to prevent UI breaking on narrow mobile screens.

### Q16: How do you prevent Cross-Site Scripting (XSS) in your HTML templates?
* **SHORT ANSWER:** Jinja2 automatically escapes all dynamic content rendered via `{{ variable }}` by default, converting characters like `<`, `>`, `&`, and `"` into safe HTML entities (`&lt;`, `&gt;`).
* **DETAILED ANSWER:** If an attacker enters `<script>stealCookie()</script>` in an expense description, Jinja’s automatic HTML escaping converts it to `&lt;script&gt;stealCookie()&lt;/script&gt;`. The browser renders the text literally on screen rather than interpreting it as executable JavaScript. We never use the `| safe` filter on raw user-supplied inputs.

### Q17: What role does JavaScript play on the client side?
* **SHORT ANSWER:** Vanilla JavaScript handles dynamic user interface enhancements: password visibility toggles, flash alert auto-dismissal after 5 seconds, real-time table searching, modal dialog triggers, and Chart.js initialization.
* **DETAILED ANSWER:** JavaScript is deliberately kept lightweight and vanilla (no jQuery or React dependencies). Key responsibilities include:
  - **Password Visibility:** Toggles input `type="password"` to `type="text"` and updates eye icon states.
  - **Notification Drawer:** Listens for click events on the bell badge and dispatches asynchronous POST requests to `/notifications/<id>/read`.
  - **Dynamic Form Helpers:** Validates date pickers, auto-populates today's date on `/expenses/add`, and enforces positive numeric inputs.

---

## Section 4: Database Design & Relational Integrity

### Q18: Explain your database schema and the tables present.
* **SHORT ANSWER:** The database contains 6 relational tables: `users` (user accounts and OAuth IDs), `expenses` (transaction records with foreign key to users), `budgets` (monthly spending limits), `notifications` (alert messages), `auth_otps` (hashed OTP codes), and `app_settings` (dynamic system settings).
* **DETAILED ANSWER:**
  1. `users`: Stores user identity, unique email, password hash, Google ID, auth provider ('local' or 'google'), and password status flag.
  2. `expenses`: Stores individual transactions (`amount`, `category`, `expense_date`, `payment_method`, `description`) with `ON DELETE CASCADE` foreign key referencing `users.id`.
  3. `budgets`: Stores monthly limits with a composite unique constraint `(user_id, month, year)`.
  4. `notifications`: Stores system alerts with read/unread booleans and user foreign keys.
  5. `auth_otps`: Manages registration and password reset verification codes, tracking attempt counts, hash values, and expiry timestamps.
  6. `app_settings`: Key-value store for runtime persistent parameters (e.g. `gas_webapp_url`).

### Q19: Why did you use `DECIMAL(12, 2)` instead of `FLOAT` or `DOUBLE` for financial amounts?
* **SHORT ANSWER:** `FLOAT` and `DOUBLE` are binary floating-point types that cannot represent decimal fractions precisely, causing rounding errors in financial balances. `DECIMAL(12, 2)` is an exact numeric fixed-point type that guarantees penny-perfect accuracy.
* **DETAILED ANSWER:** In IEEE 754 binary floating-point representation, numbers like `0.10` cannot be stored precisely, resulting in values like `0.10000000000000000555`. In financial accounting, adding thousands of floating-point transactions introduces cumulative rounding drift. MySQL’s `DECIMAL(12, 2)` stores numbers as exact binary-coded decimal digits, supporting up to 10 integer digits and 2 exact decimal places (e.g. ₹9,999,999,999.99), completely eliminating rounding anomalies. In Python, these map directly to `decimal.Decimal` objects.

### Q20: What indexes are created in your database and why?
* **SHORT ANSWER:** We created indexes on `users(google_id)`, `expenses(user_id, expense_date)`, `expenses(user_id, category)`, `budgets(user_id, month, year)`, `notifications(user_id, is_read, created_at)`, and `auth_otps(email, purpose)`. They transform slow full-table scans into instant B-tree lookups.
* **DETAILED ANSWER:** Without indexes, every query searching for a user’s expenses forces MySQL to perform an O(N) disk scan examining every row in the entire table. By creating composite index `idx_expenses_user_date (user_id, expense_date)`:
  - MySQL uses an O(log N) binary search on the B-tree index to locate all records matching `user_id = 5` and date ranges in milliseconds.
  - The `unique_user_month_budget (user_id, month, year)` unique index guarantees at the database engine level that a user cannot accidentally have duplicate budget records for the same month.

### Q21: What is `ON DELETE CASCADE` and why is it used?
* **SHORT ANSWER:** `ON DELETE CASCADE` is a foreign key constraint rule that automatically deletes all associated child records (expenses, budgets, notifications) when a parent record (user) is deleted, maintaining referential integrity.
* **DETAILED ANSWER:** Without `ON DELETE CASCADE`, deleting a row from `users` would either fail with a foreign key constraint violation error or leave orphaned expense records in the database with non-existent `user_id` values. By specifying `CONSTRAINT fk_expenses_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE`, MySQL guarantees that if user #12 is purged, all of their expenses, budgets, and notification alerts are atomically cleaned up in the same database operation.

### Q22: How do you prevent SQL Injection across the application?
* **SHORT ANSWER:** We strictly use parameterized SQL queries (`cursor.execute(sql, (param1, param2))`) for every database interaction. User input is never concatenated or formatted directly into SQL query strings.
* **DETAILED ANSWER:** SQL injection occurs when user input containing SQL control characters (like `' OR '1'='1`) is concatenated into a query string. We prevent this by passing SQL statements with placeholder `%s` tokens and supplying values as a separate parameter tuple:
```python
cursor.execute("SELECT * FROM expenses WHERE user_id = %s AND category = %s", (user_id, category))
```
The MySQL database protocol transmits the query blueprint and parameters in separate network packets. The database engine never interprets the parameters as executable SQL syntax, rendering injection attacks mathematically impossible.

### Q23: How does the application handle MySQL connection timeouts or server restarts?
* **SHORT ANSWER:** We implemented an active `ensure_db_connection()` health-check function that calls `db.ping(reconnect=True, attempts=3, delay=1)` before requests, automatically re-establishing the database socket if MySQL was idle or restarted.
* **DETAILED ANSWER:** Cloud database providers like Railway automatically close idle TCP connections after inactivity (such as overnight). In standard Flask setups, the next morning request crashes with `MySQL Connection Lost`. Our `ensure_db_connection()` function runs during `@app.before_request`: it invokes `db.ping(reconnect=True)` which sends a lightweight ping packet to MySQL; if the socket is broken, it cleanly creates a new connection object using `get_db_connection_params()`.

### Q24: How are transactions managed during requests?
* **SHORT ANSWER:** We set `autocommit = False` on database connections, and register `@app.teardown_request` to automatically execute `db.commit()` if the request finishes without error, or `db.rollback()` if an exception occurs.
* **DETAILED ANSWER:** Multi-step operations—such as creating an expense and triggering an associated notification, or verifying an OTP and creating a user account—must be atomic (all succeed or all fail). If an exception occurs half-way through request execution, the `teardown_request` hook intercepts the error and calls `db.rollback()`. This undoes any uncommitted intermediate database writes, preventing database corruption and deadlocks.

---

## Section 5: Authentication & Session Security

### Q25: How are passwords stored securely?
* **SHORT ANSWER:** Passwords are never stored in plaintext. They are transformed into irreversible cryptographic hashes using Werkzeug's implementation of PBKDF2-SHA256 with a unique, cryptographically random salt per user.
* **DETAILED ANSWER:** When a user registers or updates their password, we invoke:
`generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)`
This derives a hash through thousands of iterations of HMAC-SHA256 combined with a 16-byte random salt. Even if the database were leaked, precomputed rainbow tables are useless because every salt is unique, and brute-force cracking is computationally infeasible. Authentication uses `check_password_hash(hash, candidate_password)` which runs in constant time to prevent side-channel timing attacks.

### Q26: What is CSRF and how is it prevented in ExpenseFlow?
* **SHORT ANSWER:** Cross-Site Request Forgery (CSRF) is an attack where a malicious website tricks a user's browser into submitting unwanted actions to an authenticated app. We prevent it by generating a cryptographically random 32-byte session token that must be submitted and verified on every POST request.
* **DETAILED ANSWER:** When a user logs in, `@app.before_request` generates a secret token (`secrets.token_hex(32)`) stored in their signed session cookie. Every HTML form embeds `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`. When a form is submitted, the server compares the submitted form token with the session token using constant-time comparison `hmac.compare_digest(str(token), str(expected))`. A third-party site cannot read the victim's session cookie due to browser SameSite restrictions, so their forged requests lack a valid token and are rejected with HTTP 400.

### Q27: How does Google OAuth 2.0 work in ExpenseFlow?
* **SHORT ANSWER:** The user clicks "Sign in with Google" -> Flask redirects them to Google's consent screen with a random `state` token -> The user logs in at Google -> Google redirects back to `/login/google/callback` with an authorization code -> Flask exchanges this code server-side for an access token -> Flask queries Google's userinfo API -> The user is logged in or linked in MySQL.
* **DETAILED ANSWER:** We implement the OAuth 2.0 Authorization Code Flow:
  1. `/login/google` generates a cryptographically secure random `state` parameter (`secrets.token_urlsafe(24)`), stores it in `session`, and redirects to `https://accounts.google.com/o/oauth2/v2/auth`.
  2. Google authenticates the user and redirects back to `/login/google/callback?code=...&state=...`.
  3. Flask validates the `state` parameter against `session` using `hmac.compare_digest` to prevent login CSRF attacks.
  4. Flask sends a POST request with the secret `GOOGLE_CLIENT_SECRET` to `https://oauth2.googleapis.com/token` to obtain an `access_token`.
  5. Flask requests `https://www.googleapis.com/oauth2/v2/userinfo` to obtain the verified email, Google ID, and name.

### Q28: Why is the `state` parameter essential in OAuth 2.0?
* **SHORT ANSWER:** The `state` parameter prevents Login CSRF attacks, where an attacker tricks a victim into linking the attacker’s social account to the victim’s local session.
* **DETAILED ANSWER:** Without a `state` parameter, an attacker could initiate a Google login, intercept the authorization code returned by Google, and construct a malicious link containing their code. If a victim clicks that link, the victim’s browser would send the attacker's code to the callback endpoint. The server would exchange the code and bind the attacker's Google account to the victim's session. The `state` parameter acts as a one-time CSRF token tied to the user's specific browser session.

### Q29: What happens when a user who previously registered with email/password clicks "Sign in with Google"?
* **SHORT ANSWER:** ExpenseFlow detects that the Google email already exists in the database. Because Google has already verified email ownership, the system automatically links the user's `google_id` to their existing account and logs them in seamlessly.
* **DETAILED ANSWER:** In `google_callback()` in `app.py`:
The system executes `SELECT * FROM users WHERE email = %s`. If a record exists with `google_id IS NULL`, ExpenseFlow updates the record:
`UPDATE users SET google_id = %s, auth_provider = 'google' WHERE id = %s`
This avoids creating confusing duplicate accounts while preserving all previously recorded expenses and budgets associated with that user's ID.

### Q30: What is the "Google-only password setup" feature?
* **SHORT ANSWER:** If a user signs up exclusively using Google, they do not have a local password. ExpenseFlow provides a `/set-password` page allowing them to create a password so they can log in via both Google and standard email/password forms.
* **DETAILED ANSWER:** The `users` table contains columns `password VARCHAR(255) NULL` and `has_set_password BOOLEAN DEFAULT FALSE`. When a brand-new user authenticates via Google OAuth, `password` is initialized to `NULL` and `has_set_password` is set to `FALSE`. The session receives `pending_password_setup = True`. The `@login_required` middleware detects this flag and forces the user to `/set-password` to establish a local password, ensuring they are never locked out if Google services are inaccessible.

---

## Section 6: OTP System & Verification Engine

### Q31: How is the OTP generated and how long is it?
* **SHORT ANSWER:** The OTP is a 6-digit numerical string between 100000 and 999999, generated using Python's cryptographically secure pseudo-random number generator: `secrets.randbelow(900000) + 100000`.
* **DETAILED ANSWER:** We avoid standard `random.randint()` because standard PRNGs use the Mersenne Twister algorithm, which is predictable if previous outputs are observed. Python’s `secrets` module accesses operating-system entropy sources (such as `/dev/urandom` on Linux or `CryptGenRandom` on Windows). Generating a 6-digit code provides 900,000 possible permutations, which offers sufficient entropy when combined with attempt limits and short expiration windows.

### Q32: Why do you hash OTP codes in the database instead of storing them in plaintext?
* **SHORT ANSWER:** If an unauthorized party gains read access to the database or SQL backups, plaintext OTPs would allow them to intercept active password resets and take over user accounts. Hashing ensures OTPs cannot be stolen from database dumps.
* **DETAILED ANSWER:** Just like passwords, temporary authentication codes are sensitive secrets. In `db_create_otp()`, we execute `otp_hash = generate_password_hash(otp)`. The database only stores this irreversible hash. When the user enters their code on `/verify-otp` or `/verify-reset-otp`, Flask retrieves the hash and evaluates `check_password_hash(otp_hash, user_input)`. Even if an attacker has real-time SQL read access, they cannot determine the original 6-digit code from the hash before the 10-minute expiration deadline.

### Q33: What mechanisms prevent brute-force attacks on the 6-digit OTP?
* **SHORT ANSWER:** We enforce a strict limit of 5 failed attempts per OTP request and a 10-minute expiration window. If 5 incorrect attempts occur, the OTP is instantly invalidated.
* **DETAILED ANSWER:** A 6-digit code has 900,000 possibilities. Without rate limiting, an automated script could test all permutations in minutes. ExpenseFlow tracks failed attempts in the `auth_otps` table (`attempts` column) and in session memory:
1. On each incorrect guess, `attempts` is incremented by 1.
2. If `attempts >= 5`, the OTP record is permanently invalidated (`is_used = TRUE`), the reset session is cleared, and the user is redirected with an error message requiring them to request a new code.
3. The probability of guessing a 6-digit code within 5 attempts is 5 in 900,000 (0.00055%), rendering brute force ineffective.

### Q34: What happens when a user requests a "Resend OTP"?
* **SHORT ANSWER:** The system marks the existing active OTP as used (`is_used = TRUE`), resets the failed attempts counter to 0, generates a brand new 6-digit code, updates the database and session, and dispatches a fresh email.
* **DETAILED ANSWER:** In `resend_otp()`:
The database executes:
`UPDATE auth_otps SET is_used = TRUE WHERE email = %s AND purpose = %s AND is_used = FALSE`
This guarantees that old OTP codes are immediately invalidated and cannot be used in replay attacks. A new OTP is generated, hashed, saved with a fresh 10-minute expiration timestamp, and sent via the email dispatcher pipeline.

### Q35: How are registration OTPs separated from password reset OTPs?
* **SHORT ANSWER:** Every OTP record in the `auth_otps` table has a strict `purpose` column (`'registration'` or `'password_reset'`). Verification routes explicitly filter by purpose, preventing a registration code from being used to reset a password.
* **DETAILED ANSWER:** If OTP purposes were not segregated, an attacker who registers a dummy account could capture their registration OTP and submit it to the password reset verification route for a different target account. Our queries enforce purpose isolation:
`SELECT * FROM auth_otps WHERE email = %s AND purpose = 'password_reset' AND is_used = FALSE`
Furthermore, password reset requests generate an additional UUID token (`reset_token`) stored in the user session and validated alongside the OTP.

---

## Section 7: Email Architecture & Cloud Networking

### Q36: Why did traditional SMTP fail when deployed on Railway?
* **SHORT ANSWER:** Cloud hosting providers like Railway permanently block outbound traffic on standard SMTP ports (25, 465, and 587) to prevent spammers from abusing their IP ranges.
* **DETAILED ANSWER:** While standard SMTP works on a local development machine because home and office ISPs leave port 587 open for submission, cloud platforms (including Railway, Render, DigitalOcean, and AWS EC2) block raw outbound TCP connections on ports 25, 465, and 587 by default. When Flask attempted to connect to `smtp.gmail.com:587`, the connection hung until timing out or failing with `Errno 111: Connection Refused`.

### Q37: Why did the Resend email service fail during production testing?
* **SHORT ANSWER:** Resend's free tier sandbox domain (`onboarding@resend.dev`) restricts email delivery exclusively to the single email address registered by the developer on the Resend account. It rejected emails sent to arbitrary test users with HTTP 403.
* **DETAILED ANSWER:** When a user submits "Forgot Password" or "Register" with an email address other than the project owner's personal account, Resend’s API returns:
`HTTP 403 Forbidden: "validation_error: You can only send testing emails to your own email address. To send to other recipients, verify a custom domain."`
Because acquiring and configuring DNS records (SPF, DKIM, DMARC) for a custom domain requires paid registrar subscriptions, we needed a ₹0 cost production architecture capable of delivering emails to any arbitrary recipient worldwide.

### Q38: Explain your ₹0 Google Apps Script Webhook email solution.
* **SHORT ANSWER:** We deployed a lightweight 10-line JavaScript webhook to Google Apps Script. Railway sends an HTTPS POST request on standard web port 443 with the recipient, subject, and body; the script runs inside the owner’s personal Google account and sends the email using Google’s native `MailApp.sendEmail()` API.
* **DETAILED ANSWER:** The Google Apps Script architecture solves multiple production challenges simultaneously:
  1. **Port Block Bypass:** Railway communicates with `https://script.google.com/macros/s/.../exec` over HTTPS port 443, which is never blocked by cloud firewalls.
  2. **Arbitrary Recipients:** Google Apps Script executes under the authenticated Google user’s quota, delivering up to 100 free emails per day to *any* email domain (Gmail, Outlook, Yahoo, institutional addresses).
  3. **SPF/DKIM Compliance:** Emails originate directly from Google’s primary mail servers with full Google SPF and DKIM signatures, ensuring high inbox deliverability without spam folder diversion.
  4. **Zero Domain Cost:** Requires no custom domain or DNS records.

### Q39: What is the complete email fallback priority chain in `dispatch_email`?
* **SHORT ANSWER:** The dispatcher prioritizes HTTPS services over raw SMTP: 1. Gmail REST API -> 2. Google Apps Script Webhook -> 3. Brevo REST API -> 4. EmailJS REST API -> 5. Resend (verified domain) -> 6. Raw SMTP (local dev) -> 7. Resend sandbox fallback.
* **DETAILED ANSWER:** In `dispatch_email()` in `app.py`:
The function iterates sequentially through configured providers until one returns success:
1. Checks for `GMAIL_REFRESH_TOKEN` to use Google's official Gmail API v1.
2. Checks for `GAS_WEBAPP_URL` to dispatch via the Google Apps Script Webhook (currently active in production).
3. Checks for `BREVO_API_KEY` to dispatch via Brevo REST API (300 free emails/day).
4. Checks for `EMAILJS_SERVICE_ID` to dispatch via EmailJS.
5. Checks if Resend has a verified custom domain.
6. Falls back to raw local SMTP if running in local development.
7. Logs failures in an error collector list without leaking sensitive tokens in user flash alerts.

---

## Section 8: Expense Tracking, Budgets & Reports

### Q40: How does the application enforce cross-user data isolation?
* **SHORT ANSWER:** Every SQL query that reads, updates, or deletes expenses explicitly filters by `user_id = session['user_id']`. It is impossible for User A to view or modify User B's data even if they guess User B's transaction ID.
* **DETAILED ANSWER:** In multi-tenant systems, the most common vulnerability is Insecure Direct Object References (IDOR). In ExpenseFlow, routes like `/expenses/<int:expense_id>/edit` or `/expenses/<int:expense_id>/delete` do not simply execute `DELETE FROM expenses WHERE id = %s`. They enforce:
```python
cursor.execute("DELETE FROM expenses WHERE id = %s AND user_id = %s", (expense_id, session['user_id']))
```
If an attacker authenticated as User 5 submits a POST request targeting `expense_id = 99` belonging to User 8, the query affects 0 rows, and Flask redirects them with an error flash.

### Q41: How does the budget notification algorithm work?
* **SHORT ANSWER:** Whenever a user views the dashboard or records an expense, the system calculates their total spend for the current month. If spending reaches 80%, 90%, or 100% of their budget, it automatically generates a persistent notification record if an alert hasn't already been emitted this month.
* **DETAILED ANSWER:** In `generate_user_notifications(user_id)` in `app.py`:
1. Calculates the first day of the current month and the first day of next month.
2. Queries `SUM(amount)` from `expenses` for transactions within these boundaries.
3. Queries `budget_amount` from `budgets` for `(user_id, current_month, current_year)`.
4. Checks the `notifications` table to see which alert types have already been created this month to prevent spamming duplicate alerts.
5. If `spend > budget`, creates `budget_exceeded`; if `used_pct >= 90%`, creates `budget_90`; if `used_pct >= 80%`, creates `budget_80`.

### Q42: How does CSV export work and how is memory managed?
* **SHORT ANSWER:** The `/expenses/export` route executes a filtered query, writes formatted CSV lines into an in-memory `io.StringIO()` buffer, and streams it back to the client as an attachment response with `mimetype='text/csv'`.
* **DETAILED ANSWER:** Rather than saving temporary CSV files to the server's disk (which risks disk exhaustion and file permission collisions), ExpenseFlow utilizes Python’s `io.StringIO` in-memory text stream:
1. Queries the user's filtered expenses matching active category, search, and date filters.
2. Instantiates `writer = csv.writer(output)`.
3. Writes header row: `['Date', 'Category', 'Amount (INR)', 'Payment Method', 'Description']`.
4. Writes data rows and returns `Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=expenses_export.csv"})`.

---

## Section 9: Deployment, Testing & Reliability

### Q43: How does a code commit travel from local development to the live Railway website?
* **SHORT ANSWER:** Pushing to GitHub triggers Railway's CI/CD webhook -> Railway pulls the latest `main` branch commit -> Builds the Python environment from `requirements.txt` -> Starts Gunicorn using `Procfile` -> Runs health checks -> Performs an atomic zero-downtime cutover.
* **DETAILED ANSWER:** The deployment pipeline is fully automated:
1. Developer pushes commit: `git push origin main`.
2. GitHub notifies Railway via webhook.
3. Railway launches an ephemeral Linux container, detects Python 3.11+, and executes `pip install -r requirements.txt`.
4. Railway injects all dashboard environment variables (`MYSQL_URL`, `FLASK_SECRET_KEY`, `GAS_WEBAPP_URL`, `GOOGLE_CLIENT_ID`).
5. Gunicorn binds to `0.0.0.0:$PORT`.
6. Railway’s health checker confirms HTTP 200 on the root socket before routing live web traffic to the new container and terminating the previous instance.

### Q44: What is the current test coverage and what testing frameworks are used?
* **SHORT ANSWER:** We use Python’s built-in `unittest` framework with 56 automated test cases in `tests/test_suite.py` that pass with 100% success in under 15 seconds.
* **DETAILED ANSWER:** The test suite covers:
  - User registration and OTP attempt limits (5-attempt lockout).
  - Password hashing and verification.
  - Google OAuth login, CSRF state verification, and account linking.
  - Expenses CRUD operations and strict user data isolation.
  - Multi-parameter search, date range filters, and CSV export.
  - Budget calculations and automated notification triggers.
  - Multi-provider email dispatchers (mocking API responses for Gmail API, Google Apps Script, Brevo, and EmailJS).

### Q45: Why can't unit tests alone prove that emails reach real inboxes?
* **SHORT ANSWER:** Unit tests mock external HTTP requests to ensure our code formats payloads correctly without spending network quotas; they do not verify external DNS records, spam filters, or cloud port firewalls. Live smoke testing is required to prove inbox delivery.
* **DETAILED ANSWER:** In automated unit tests, `@patch("requests.post")` intercepts outgoing calls and returns simulated HTTP 200 responses. While this verifies that our JSON formatting, headers, and error-handling logic function as designed, it cannot test external network realities: ISP latency, Google Apps Script execution quotas, or spam filtering. To prove true real-world delivery, we built dedicated live verification scripts (`scripts/test_live_forgot_password.py` and `scripts/verify_production_live.py`) that trigger real HTTP requests against the live production server.

---

## Section 10: Limitations & Future Enhancements

### Q46: What are the primary technical limitations of the current implementation?
* **SHORT ANSWER:** The Google Apps Script free tier is limited to 100 emails/day; in-memory dictionaries (`pending_registrations`) require running Gunicorn with 1 worker process; and expenses must be entered manually rather than synced via bank APIs.
* **DETAILED ANSWER:** Honest system limitations include:
  1. **Process Scalability:** Because `pending_registrations` and `password_reset_requests` maintain in-memory state alongside database backups, scaling Gunicorn to multiple worker processes on different server nodes would require an external state store like Redis.
  2. **Email Quotas:** The primary Google Apps Script pipeline is capped at 100 emails every 24 hours per personal Gmail account (though Brevo provides 300 more as a backup).
  3. **No Background Worker Queue:** Outbound HTTPS requests to Google Apps Script run synchronously within the HTTP request thread (~1-2 seconds latency). Adopting Celery or Redis Queue would make email dispatch asynchronous.

### Q47: How would you scale this application to handle 100,000 active users?
* **SHORT ANSWER:** Migrate from a single Gunicorn container to multiple container replicas behind a load balancer; replace in-memory state with a Redis cache cluster; offload emails to Celery background workers; and configure a read-replica MySQL cluster.
* **DETAILED ANSWER:** At enterprise scale:
  1. **Stateless App Servers:** Remove all in-memory session dictionaries and store OTPs and rate-limiting counters in a Redis cluster.
  2. **Asynchronous Task Workers:** Use Celery with Redis/RabbitMQ to offload email dispatching, report generation, and CSV exports into asynchronous background workers.
  3. **Database Optimization:** Deploy a managed AWS RDS MySQL cluster with one primary read-write node and multiple read replicas for intensive analytics queries, utilizing connection pooling (such as ProxySQL).
  4. **Dedicated Transactional Email:** Provision AWS SES or SendGrid with dedicated IP pools and verified custom domain authentication (DKIM/DMARC).

### Q48: What would you improve in the codebase if given another sprint?
* **SHORT ANSWER:** Implement AI-powered receipt scanning using Optical Character Recognition (OCR), add multi-currency conversion support, and introduce Web Push notifications for real-time mobile budget alerts.
* **DETAILED ANSWER:** Key enhancements would include:
  - **Receipt OCR:** Integrate Tesseract or Google Cloud Vision API to allow users to upload grocery receipts and auto-populate amount, category, and date fields.
  - **Recurring Expenses:** Add automated recurring transaction scheduling (e.g. monthly rent or Netflix subscriptions) via Celery Beat or cron jobs.
  - **Progressive Web App (PWA):** Add a Web App Manifest and Service Worker caching to enable offline transaction drafting and native home screen installation on smartphones.

---

## Section 11: Quick-Fire Viva Questions

### Q49: What is the difference between `autocommit=True` and `autocommit=False`?
* **SHORT ANSWER:** With `autocommit=True`, every individual SQL statement is immediately committed permanently to disk. With `autocommit=False`, multiple queries execute within a single transaction block that can be atomically committed or rolled back together.

### Q50: What is the difference between `GET` and `POST` in your routes?
* **SHORT ANSWER:** `GET` requests are idempotent and retrieve data to display web pages; `POST` requests submit user data to alter state (such as adding an expense or logging in) and require CSRF token validation.

### Q51: What HTTP status code is returned when a CSRF token is invalid?
* **SHORT ANSWER:** `HTTP 400 Bad Request`.

### Q52: What happens if a user navigates to `/dashboard` without logging in?
* **SHORT ANSWER:** The `@login_required` decorator intercepts the request, stores a flash message, and redirects the user with `HTTP 302` to `/login`.

### Q53: What is the function of the `auth_provider` column in the `users` table?
* **SHORT ANSWER:** It records whether the account was registered via `'local'` email/password or `'google'` OAuth 2.0 social login.

### Q54: What does `secrets.compare_digest` / `hmac.compare_digest` prevent?
* **SHORT ANSWER:** It prevents timing attacks by comparing two strings in constant time regardless of where a character mismatch occurs.

### Q55: What is the exact URL of your live deployed production application?
* **SHORT ANSWER:** `https://dailyexpensetracker-production-bf76.up.railway.app`
