import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "urban_group_bank_secret_key_v1"

# --- File paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
TRANSACTIONS_FILE = os.path.join(BASE_DIR, "transactions.json")
MESSAGES_FILE = os.path.join(BASE_DIR, "messages.json")

# --- Utility functions ---
def ensure_files():
    """Ensure all data files exist."""
    for f in [USERS_FILE, TRANSACTIONS_FILE, MESSAGES_FILE]:
        if not os.path.exists(f):
            with open(f, "w", encoding="utf-8") as file:
                json.dump([], file)

def load_json(path):
    """Load JSON safely."""
    ensure_files()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def save_json(path, data):
    """Save JSON data."""
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
    """Normalize and clean transactions."""
    txs = []
    for e in raw_list:
        if not isinstance(e, dict):
            continue
        txs.append({
            "from": e.get("from") or "",
            "to": e.get("to") or "",
            "amount": float(e.get("amount", 0)),
            "purpose": e.get("purpose") or "",
            "timestamp": e.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": e.get("type") or "transfer",
            "status": e.get("status") or "completed",
            "note": e.get("note") or "",
        })
    return txs

# --- Routes ---

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page"""
    if request.method == "POST":
        raw_identifier = request.form.get("username", "")
        username = raw_identifier.strip()
        password = request.form.get("password", "")

        users = load_json(USERS_FILE)
        user = None
        user_index = None
        ident_lower = username.lower()

        for i, u in enumerate(users):
            if (u.get("username") or "").lower() == ident_lower or (u.get("email") or "").lower() == ident_lower:
                user = u
                user_index = i
                break

        if not user:
            flash("Invalid username or password", "danger")
            return render_template("login.html")

        stored_pw = user.get("password", "")

        ok_hash = False
        try:
            if stored_pw:
                ok_hash = check_password_hash(stored_pw, password)
        except Exception:
            ok_hash = False

        ok_plain = (stored_pw == password)

        if ok_plain and user_index is not None:
            users[user_index]["password"] = generate_password_hash(password)
            save_json(USERS_FILE, users)
            ok_hash = True

        if ok_hash or ok_plain:
            session["username"] = user.get("username")
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
    """Main dashboard"""
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    user = get_user_by_username(username)
    txs = sanitize_transactions(load_json(TRANSACTIONS_FILE))

    # Show only user's transactions
    user_tx = [t for t in txs if t["from"] == username or t["to"] == username]
    user_tx.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    balance_formatted = "${:,.2f}".format(float(user.get("balance", 0)))

    return render_template(
        "dashboard.html",
        user=user,
        balance_formatted=balance_formatted,
        transactions=user_tx[:5],  # recent 5
    )

@app.route("/send", methods=["GET", "POST"])
def send():
    """Send money"""
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

        # Basic validation
        if amount <= 0:
            flash("Invalid amount entered.", "warning")
            return redirect(url_for("send"))
        if amount > float(sender.get("balance", 0)):
            flash("Insufficient funds.", "danger")
            return redirect(url_for("send"))

        if recipient:
            # ✅ Recipient found
            for u in users:
                if u["username"] == sender["username"]:
                    u["balance"] -= amount
                if u["username"] == recipient["username"]:
                    u["balance"] += amount
            save_json(USERS_FILE, users)

            tx = {
                "from": sender["username"],
                "to": recipient["username"],
                "amount": amount,
                "purpose": purpose,
                "timestamp": now,
                "type": "transfer",
                "status": "completed",
                "routing_number": routing_number
            }

            txs.insert(0, tx)
            save_json(TRANSACTIONS_FILE, txs)
            flash("Transaction successful!", "success")
            return redirect(url_for("transactions"))

        else:
            # ⚠️ Recipient not found
            for u in users:
                if u["username"] == sender["username"]:
                    u["balance"] -= amount
            save_json(USERS_FILE, users)

            tx = {
                "from": sender["username"],
                "to": recipient_input,
                "amount": amount,
                "purpose": purpose,
                "timestamp": now,
                "type": "transfer",
                "status": "flagged",
                "note": "Transaction pending review — potential fraud.",
                "routing_number": routing_number
            }

            txs.insert(0, tx)
            save_json(TRANSACTIONS_FILE, txs)
            flash("Transaction pending — flagged for review. Please contact support.", "warning")
            return redirect(url_for("transactions"))

    return render_template("send.html", user=sender)

@app.route("/transactions")
def transactions():
    """Transactions history"""
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    user = get_user_by_username(username)
    txs = sanitize_transactions(load_json(TRANSACTIONS_FILE))

    user_tx = [t for t in txs if t["from"] == username or t["to"] == username]
    user_tx.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return render_template("transactions.html", user=user, transactions=user_tx)

@app.route("/account")
@app.route("/account_details")
def account_details():
    """Account details"""
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
    """Contact page"""
    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        message = request.form.get("message", "")

        messages = load_json(MESSAGES_FILE)
        messages.insert(0, {
            "name": name,
            "email": email,
            "message": message,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        save_json(MESSAGES_FILE, messages)
        flash("Message sent!", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")

if __name__ == "__main__":
    ensure_files()
    app.run(host="0.0.0.0", port=5000, debug=True)
