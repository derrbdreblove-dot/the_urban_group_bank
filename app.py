import os
import json
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "urban_group_bank_secret_key_v1"

# =========================
# File paths
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
TRANSACTIONS_FILE = os.path.join(BASE_DIR, "transactions.json")
MESSAGES_FILE = os.path.join(BASE_DIR, "messages.json")

# =========================
# Utilities
# =========================
def ensure_files():
    for f in [USERS_FILE, TRANSACTIONS_FILE, MESSAGES_FILE]:
        if not os.path.exists(f):
            with open(f, "w", encoding="utf-8") as file:
                json.dump([], file)

def load_json(path):
    ensure_files()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user_by_username(username):
    users = load_json(USERS_FILE)
    for user in users:
        if user.get("username", "").lower() == username.lower():
            return user
    return None

def get_user_by_account(account_number):
    users = load_json(USERS_FILE)
    for user in users:
        if str(user.get("account_number", "")) == str(account_number):
            return user
    return None

def sanitize_transactions(raw_list):
    txs = []
    for e in raw_list:
        if not isinstance(e, dict):
            continue
        txs.append({
            "from": e.get("from", ""),
            "to": e.get("to", ""),
            "amount": float(e.get("amount", 0)),
            "purpose": e.get("purpose", ""),
            "timestamp": e.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "type": e.get("type", "transfer"),
            "status": e.get("status", "completed"),
            "note": e.get("note", ""),
            "routing_number": e.get("routing_number", "")
        })
    return txs

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None

def account_age_days(user):
    joined = parse_date(user.get("date_joined", ""))
    if not joined:
        return 9999
    return (datetime.now() - joined).days

# =========================
# Routes
# =========================
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        users = load_json(USERS_FILE)
        user = None
        index = None

        for i, u in enumerate(users):
            if u.get("username", "").lower() == identifier or u.get("email", "").lower() == identifier:
                user = u
                index = i
                break

        if not user:
            flash("Invalid username or password", "danger")
            return render_template("login.html")

        stored_pw = user.get("password", "").strip()

        # === FIXED: Support both hashed and plain-text passwords ===
        authenticated = False
        upgrade_needed = False

        # Check if it's a Werkzeug hashed password
        if stored_pw.startswith(('pbkdf2:', 'scrypt:', 'bcrypt:', 'argon2')):
            authenticated = check_password_hash(stored_pw, password)
        else:
            # Plain text password
            if stored_pw == password:
                authenticated = True
                upgrade_needed = True  # Upgrade to hash after login

        if authenticated:
            # Upgrade plain password to secure hash on first successful login
            if upgrade_needed:
                users[index]["password"] = generate_password_hash(password)
                save_json(USERS_FILE, users)
                flash("Your password has been securely upgraded.", "info")

            session["username"] = user["username"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username or password", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    user = get_user_by_username(session["username"])
    txs = sanitize_transactions(load_json(TRANSACTIONS_FILE))
    age_days = account_age_days(user)

    # 🔒 New account rule
    if age_days < 14:
        user_tx = []

        users = load_json(USERS_FILE)
        for u in users:
            if u["username"] == user["username"]:
                if float(u.get("balance", 0)) > 300:
                    u["balance"] = round(random.uniform(200, 300), 2)
                    user["balance"] = u["balance"]
        save_json(USERS_FILE, users)

    else:
        join_year = user.get("date_joined", "1900")[:4]
        user_tx = [
            t for t in txs
            if (t["from"] == user["username"] or t["to"] == user["username"])
            and t["timestamp"][:4] >= join_year
        ]
        user_tx.sort(key=lambda x: x["timestamp"], reverse=True)

    balance_formatted = "${:,.2f}".format(float(user.get("balance", 0)))

    return render_template(
        "dashboard.html",
        user=user,
        balance_formatted=balance_formatted,
        transactions=user_tx[:5]
    )

@app.route("/send", methods=["GET", "POST"])
def send():
    if "username" not in session:
        return redirect(url_for("login"))

    sender = get_user_by_username(session["username"])

    if request.method == "POST":
        recipient_input = request.form.get("recipient", "").strip()
        account_number = request.form.get("account_number", "").strip()
        routing_number = request.form.get("routing_number", "").strip()
        amount = float(request.form.get("amount", 0))
        purpose = request.form.get("purpose", "")

        recipient = get_user_by_username(recipient_input) or get_user_by_account(account_number)

        users = load_json(USERS_FILE)
        txs = load_json(TRANSACTIONS_FILE)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if amount <= 0 or amount > float(sender.get("balance", 0)):
            flash("Invalid or insufficient amount.", "danger")
            return redirect(url_for("send"))

        for u in users:
            if u["username"] == sender["username"]:
                u["balance"] -= amount
            if recipient and u["username"] == recipient["username"]:
                u["balance"] += amount

        save_json(USERS_FILE, users)

        txs.insert(0, {
            "from": sender["username"],
            "to": recipient["username"] if recipient else recipient_input,
            "amount": amount,
            "purpose": purpose,
            "timestamp": now,
            "type": "transfer",
            "status": "completed" if recipient else "flagged",
            "routing_number": routing_number
        })

        save_json(TRANSACTIONS_FILE, txs)
        flash("Transaction submitted successfully.", "success")
        return redirect(url_for("transactions"))

    return render_template("send.html", user=sender)

@app.route("/transactions")
def transactions():
    if "username" not in session:
        return redirect(url_for("login"))

    user = get_user_by_username(session["username"])
    txs = sanitize_transactions(load_json(TRANSACTIONS_FILE))
    age_days = account_age_days(user)

    if age_days < 14:
        user_tx = []
    else:
        join_year = user.get("date_joined", "1900")[:4]
        user_tx = [
            t for t in txs
            if (t["from"] == user["username"] or t["to"] == user["username"])
            and t["timestamp"][:4] >= join_year
        ]
        user_tx.sort(key=lambda x: x["timestamp"], reverse=True)

    return render_template("transactions.html", user=user, transactions=user_tx)

@app.route("/account")
@app.route("/account_details")
def account_details():
    if "username" not in session:
        return redirect(url_for("login"))

    user = get_user_by_username(session["username"])
    balance_formatted = "${:,.2f}".format(float(user.get("balance", 0)))

    return render_template("account.html", user=user, balance_formatted=balance_formatted)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        messages = load_json(MESSAGES_FILE)
        messages.insert(0, {
            "name": request.form.get("name", ""),
            "email": request.form.get("email", ""),
            "message": request.form.get("message", ""),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_json(MESSAGES_FILE, messages)
        flash("Message sent!", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")

if __name__ == "__main__":
    ensure_files()
    app.run(host="0.0.0.0", port=5000, debug=True)