from flask import Flask, render_template, request, redirect, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import date, datetime
from logic import budget_prediction, top_reason

app = Flask(__name__)
app.secret_key = "expense_secret"


def get_db():
    return sqlite3.connect("data/expenses.db")


# ================= LANDING PAGE (ADDED) =================
@app.route("/")
def landing():
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("landing.html")


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, password, monthly_budget FROM users WHERE username=?",
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
        username = request.form["username"]
        raw_password = request.form["password"]
        password = generate_password_hash(raw_password)
        budget = request.form["budget"]

        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password, monthly_budget) VALUES (?, ?, ?)",
                (username, password, budget)
            )
            conn.commit()
            conn.close()

            flash("Account created successfully ✅ Please login.")
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
    user_budget = session["budget"]
    # Daily limit (session based)
    daily_limit = session.get("daily_limit", 0)

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT category, SUM(amount) FROM expenses WHERE user_id=? GROUP BY category",
        (user_id,)
    )
    category_data = cur.fetchall()

    cur.execute(
        "SELECT date, SUM(amount) FROM expenses WHERE user_id=? GROUP BY date",
        (user_id,)
    )
    daily_data = cur.fetchall()

    cur.execute(
        "SELECT reason FROM expenses WHERE user_id=?",
        (user_id,)
    )
    reasons = [r[0] for r in cur.fetchall()]

    cur.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id=?",
        (user_id,)
    )
    total = cur.fetchone()[0] or 0

    cur.execute(
        "SELECT DISTINCT date FROM expenses WHERE user_id=?",
        (user_id,)
    )
    days = len(cur.fetchall())

    # ===== DAILY BUDGET INDICATOR =====
    today = datetime.now().strftime("%Y-%m-%d")

    cur.execute(
        "SELECT SUM(amount) FROM expenses WHERE user_id=? AND date=?",
        (user_id, today)
    )
    today_spent = cur.fetchone()[0] or 0

    percent = (today_spent / daily_limit) * 100 if daily_limit > 0 else 0
    percent = min(percent, 100)

    conn.close()

    budget_status = budget_prediction(total, days, user_budget)

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
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """INSERT INTO expenses 
               (user_id, date, time, amount, category, reason)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                session["user_id"],
                request.form["date"],
                request.form["time"],
                request.form["amount"],
                request.form["category"],
                request.form["reason"]
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

    new_budget = request.form["budget"]
    user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET monthly_budget=? WHERE id=?",
        (new_budget, user_id)
    )
    conn.commit()
    conn.close()

    session["budget"] = int(new_budget)
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
        "DELETE FROM expenses WHERE user_id=?",
        (user_id,)
    )
    conn.commit()
    conn.close()

    flash("All expenses cleared successfully 🗑️")
    return redirect("/dashboard")


@app.route("/set-daily-limit", methods=["POST"])
def set_daily_limit():
    if "user_id" not in session:
        return redirect("/login")

    session["daily_limit"] = int(request.form["daily_limit"])
    flash("Daily limit updated ✅")
    return redirect("/")

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)