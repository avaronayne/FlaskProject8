import os
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, jsonify
from datetime import datetime

app = Flask(__name__)

# ---------------------------
# Config
# ---------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("WARNING: DATABASE_URL not set. Saving will not work.")

CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY",
    "INR", "NZD", "BRL", "ZAR", "RUB", "KRW", "SGD", "NOK",
    "SEK", "MXN", "TRY", "HKD"
]
BASE_URL = "https://api.exchangerate-api.com/v4/latest/"

# Simple cache
cache = {"data": None, "timestamp": None, "base": None}

# ---------------------------
# Database helpers
# ---------------------------
def get_db_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def save_conversion(amount, from_cur, to_cur, result):
    if not DATABASE_URL:
        print("DATABASE_URL missing, cannot save")
        return False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO conversions (amount, from_cur, to_cur, result)
                    VALUES (%s, %s, %s, %s)
                """, (amount, from_cur, to_cur, result))
            conn.commit()
        print(f"Saved: {amount} {from_cur} -> {result} {to_cur}")
        return True
    except Exception as e:
        print(f"DB save error: {e}")
        return False

def load_conversions():
    if not DATABASE_URL:
        return []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM conversions ORDER BY created_at DESC")
                return cur.fetchall()
    except Exception as e:
        print(f"DB load error: {e}")
        return []

# ---------------------------
# Exchange rate API
# ---------------------------
def get_all_rates(base_currency="USD"):
    global cache
    now = datetime.now()
    if (cache["data"] and cache["base"] == base_currency and
        cache["timestamp"] and (now - cache["timestamp"]).seconds < 3600):
        return cache["data"], None
    try:
        resp = requests.get(f"{BASE_URL}{base_currency}", timeout=5)
        data = resp.json()
        if resp.status_code != 200:
            return None, f"API error: {data.get('error', 'Unknown')}"
        cache["data"] = data
        cache["timestamp"] = now
        cache["base"] = base_currency
        return data, None
    except Exception as e:
        return None, str(e)

# ---------------------------
# Routes
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html", currencies=CURRENCIES)

@app.route("/convert", methods=["POST"])
def convert():
    amount_str = request.form.get("amount")
    from_cur = request.form.get("from_cur")
    to_cur = request.form.get("to_cur")

    if not amount_str or not from_cur or not to_cur:
        return render_template("index.html", error="All fields required", currencies=CURRENCIES)

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return render_template("index.html", error="Amount must be > 0", currencies=CURRENCIES)

    data, err = get_all_rates("USD")
    if err:
        return render_template("index.html", error=err, currencies=CURRENCIES)

    rates = data["rates"]
    try:
        if from_cur == "USD":
            converted = amount * rates[to_cur]
        elif to_cur == "USD":
            converted = amount / rates[from_cur]
        else:
            converted = amount * (rates[to_cur] / rates[from_cur])
    except KeyError:
        return render_template("index.html", error="Currency not supported", currencies=CURRENCIES)

    result = round(converted, 2)

    # If the "save" button was clicked, store in DB
    if 'save' in request.form:
        save_conversion(amount, from_cur, to_cur, result)

    return render_template("index.html", result=result, currencies=CURRENCIES)

@app.route("/history")
def history():
    saved = load_conversions()
    return render_template("history.html", saved=saved)

# ---------------------------
# API endpoints (optional, keep as is)
# ---------------------------
@app.route("/api/rates")
def api_rates():
    base = request.args.get("base", "USD")
    data, err = get_all_rates(base)
    if err:
        return jsonify({"error": err}), 503
    return jsonify({"base": data["base"], "date": data["date"], "rates": data["rates"]})

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)