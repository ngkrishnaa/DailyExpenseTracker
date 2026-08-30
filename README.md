# ExpenseFlow Daily Expense Tracker

ExpenseFlow is a Flask and MySQL web application for securely tracking personal expenses, setting monthly budgets, and understanding spending through interactive reports.

## Features

- Email-verified registration, login/logout, sessions, and password recovery by OTP
- Personal dashboard with monthly, daily, budget, and category summaries
- Create, search, filter, sort, edit, and delete your own expenses
- Monthly budget progress with normal, warning, and exceeded states
- Chart.js reports for category, daily, and monthly spending
- Profile updates and password change
- Responsive desktop and mobile dashboard navigation

## Technology

- Python, Flask, Jinja templates
- MySQL and `mysql-connector-python`
- HTML, CSS, JavaScript, Chart.js
- Werkzeug password hashing and Gmail SMTP OTP delivery

## Setup

1. Create and activate a virtual environment.

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install dependencies.

   ```powershell
   pip install -r requirements.txt
   ```

3. Create the MySQL database and tables by running `database_schema.sql` in MySQL Workbench or the MySQL client. The application also safely creates the `expenses` and `budgets` tables when it starts.

4. Create a `.env` file in the project root with your own values:

   ```env
   MAIL_EMAIL=your-gmail-address
   MAIL_PASSWORD=your-gmail-app-password
   DB_HOST=localhost
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=your-database-password
   DB_NAME=daily_expense_tracker
   FLASK_SECRET_KEY=a-long-random-secret-value
   ```

   For Gmail, use an app password rather than your normal Gmail password.

5. Run the application.

   ```powershell
   .\venv\Scripts\python.exe app.py
   ```

   Open `http://127.0.0.1:5000` in your browser.

## Testing the main features

- Register with a new email, use the verification code, and confirm the dashboard opens.
- Log out, log in again, and confirm the dashboard is protected when signed out.
- Use **Forgot Password** and confirm the reset OTP arrives; reset the password and log in with it.
- Add an expense, edit it, and delete it from **My Expenses**.
- Try search, category/payment filters, dates, sorting, and pagination in **My Expenses**.
- Set a budget and confirm the progress bar and remaining balance update after adding expenses.
- Open **Reports** and switch between current month, previous month, and a custom range.
- Update your name or password from **Profile**.

## Notes

- Each expense, budget, report query, and edit/delete action is scoped to the logged-in user ID.
- OTP requests are currently held in application memory, so restarting the development server invalidates pending registration and password-reset codes. Use a database or cache such as Redis before deploying across multiple servers.
- Enable HTTPS in production and set `SESSION_COOKIE_SECURE=True` in Flask configuration.
