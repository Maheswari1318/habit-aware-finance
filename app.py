```python
import os
import sqlite3
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    flash,
    session
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from logic import budget_prediction, top_reason

# ================= APP CONFIG =================

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret")

# ================= DATABASE =================

def get_db():

    db_path = "/tmp/expenses.db"

    conn = sqlite3.connect(db_path)

    return conn


def init_db():

    conn = get_db()
    cur = conn.cursor()

    # USERS TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        monthly_budget INTEGER
    )
    """)

    # EXPENSES TABLE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        time TEXT,
        amount REAL,
        category TEXT,
        reason TEXT
    )
    """)

    conn.commit()
    conn.close()


# ================= LANDING PAGE =================

@app.route("/")
def landing():

    if "user_id" in session:
        return redirect("/dashboard")

    return render_template("landing.html")


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Please enter username and password")
            return redirect("/login")

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT id, password, monthly_budget
            FROM users
            WHERE username=?
            """,
            (username,)
        )

        user = cur.fetchone()

        conn.close()

        if user and check_password_hash(user[1], password):

            session.clear()

            session["user_id"] = user[0]
            session["budget"] = user[2]

            return redirect("/dashboard")

        else:
            flash("Invalid credentials ❌")

    return render_template("login.html")


# ================= SIGNUP =================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form.get("username")
        raw_password = request.form.get("password")
        budget = request.form.get("budget")

        if not username or not raw_password or not budget:

            flash("Please fill all fields")

            return redirect("/signup")

        password = generate_password_hash(raw_password)

        try:

            conn = get_db()
            cur = conn.cursor()

            cur.execute(
                """
                INSERT INTO users
                (username, password, monthly_budget)
                VALUES (?, ?, ?)
                """,
                (username, password, budget)
            )

            conn.commit()
            conn.close()

            flash("Account created successfully ✅")

            return redirect("/login")

        except sqlite3.IntegrityError:

            flash("Username already exists ❌")

    return render_template("signup.html")


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ================= DASHBOARD =================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    user_budget = int(session["budget"])

    daily_limit = session.get("daily_limit", 0)

    conn = get_db()
    cur = conn.cursor()

    # CATEGORY DATA
    cur.execute(
        """
        SELECT category, SUM(amount)
        FROM expenses
        WHERE user_id=?
        GROUP BY category
        """,
        (user_id,)
    )

    category_data = cur.fetchall()

    # DAILY DATA
    cur.execute(
        """
        SELECT date, SUM(amount)
        FROM expenses
        WHERE user_id=?
        GROUP BY date
        """,
        (user_id,)
    )

    daily_data = cur.fetchall()

    # REASONS
    cur.execute(
        """
        SELECT reason
        FROM expenses
        WHERE user_id=?
        """,
        (user_id,)
    )

    reasons = [r[0] for r in cur.fetchall()]

    # TOTAL EXPENSE
    cur.execute(
        """
        SELECT SUM(amount)
        FROM expenses
        WHERE user_id=?
        """,
        (user_id,)
    )

    total = cur.fetchone()[0] or 0

    # TOTAL DAYS
    cur.execute(
        """
        SELECT DISTINCT date
        FROM expenses
        WHERE user_id=?
        """,
        (user_id,)
    )

    days = len(cur.fetchall())

    # TODAY'S SPENDING
    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute(
        """
        SELECT SUM(amount)
        FROM expenses
        WHERE user_id=? AND date=?
        """,
        (user_id, today)
    )

    today_spent = cur.fetchone()[0] or 0

    conn.close()

    # DAILY LIMIT %
    percent = (
        (today_spent / daily_limit) * 100
        if daily_limit > 0 else 0
    )

    percent = min(percent, 100)

    # BUDGET PREDICTION
    budget_status = budget_prediction(
        total,
        days,
        user_budget
    )

    return render_template(
        "dashboard.html",
        total=total,
        budget=budget_status,
        reason=top_reason(reasons),
        category_data=category_data,
        daily_data=daily_data,
        user_budget=user_budget,
        daily_limit=round(daily_limit, 2),
        today_spent=today_spent,
        percent=round(percent, 2)
    )


# ================= ADD EXPENSE =================

@app.route("/add", methods=["GET", "POST"])
def add_expense():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        expense_date = request.form.get("date")
        expense_time = request.form.get("time")
        amount = request.form.get("amount")
        category = request.form.get("category")
        reason = request.form.get("reason")

        if not expense_date or not amount or not category:

            flash("Please fill required fields")

            return redirect("/add")

        try:
            amount = float(amount)

        except ValueError:

            flash("Enter valid amount")

            return redirect("/add")

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO expenses
            (user_id, date, time, amount, category, reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                expense_date,
                expense_time,
                amount,
                category,
                reason
            )
        )

        conn.commit()
        conn.close()

        flash("Expense added successfully ✅")

        return redirect("/dashboard")

    return render_template("add_expense.html")


# ================= UPDATE BUDGET =================

@app.route("/update-budget", methods=["POST"])
def update_budget():

    if "user_id" not in session:
        return redirect("/login")

    new_budget = request.form.get("budget")

    if not new_budget:

        flash("Enter budget amount")

        return redirect("/dashboard")

    try:
        new_budget = int(new_budget)

    except ValueError:

        flash("Enter valid budget")

        return redirect("/dashboard")

    user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET monthly_budget=?
        WHERE id=?
        """,
        (new_budget, user_id)
    )

    conn.commit()
    conn.close()

    session["budget"] = new_budget

    flash("Budget updated successfully ✅")

    return redirect("/dashboard")


# ================= CLEAR EXPENSES =================

@app.route("/clear")
def clear_expenses():

    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM expenses
        WHERE user_id=?
        """,
        (user_id,)
    )

    conn.commit()
    conn.close()

    flash("All expenses cleared successfully 🗑️")

    return redirect("/dashboard")


# ================= SET DAILY LIMIT =================

@app.route("/set-daily-limit", methods=["POST"])
def set_daily_limit():

    if "user_id" not in session:
        return redirect("/login")

    try:

        daily_limit = int(
            request.form.get("daily_limit")
        )

        session["daily_limit"] = daily_limit

    except (ValueError, TypeError):

        flash("Enter valid daily limit")

        return redirect("/dashboard")

    flash("Daily limit updated ✅")

    return redirect("/dashboard")


# ================= INITIALIZE DATABASE =================

init_db()


# ================= RUN APP =================

if __name__ == "__main__":
    app.run(debug=True)
```
