import requests
from flask import Flask, jsonify, render_template, request, session
from datetime import datetime
import os
from supabase import create_client
import psycopg2
from psycopg2.extras import RealDictCursor
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

import psycopg2
from psycopg2.extras import RealDictCursor
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def save_conversion(amount, from_cur, to_cur, result):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversions (amount, from_cur, to_cur, result) VALUES (%s, %s, %s, %s)",
                (amount, from_cur, to_cur, result)
            )
        conn.commit()

def load_conversions():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM conversions ORDER BY created_at DESC")
            return cur.fetchall()
SUPABASE_URL = "https://osxtdllhhaeedfygtunl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9zeHRkbGxoaGFlZWRmeWd0dW5sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE0MDM3NTMsImV4cCI6MjA4Njk3OTc1M30.XXzFNsP1o-6uX5Y2jCQm5fyHtu1t_kazCeuD1fp4r0A"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

API_KEY = "9ea12d667dbda46fd01fd9a2"
BASE_URL = "https://api.exchangerate-api.com/v4/latest/"

CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY",
    "INR", "NZD", "BRL", "ZAR", "RUB", "KRW", "SGD", "NOK",
    "SEK", "MXN", "TRY", "HKD"
]

# Simple in-memory cache
cache = {
    "data": None,
    "timestamp": None,
    "base": None
}

def get_all_rates(base_currency="USD"):
    global cache
    if (cache["data"] and
            cache["base"] == base_currency and
            cache["timestamp"] and
            (datetime.now() - cache["timestamp"]).seconds < 3600):
        return cache["data"], None
    try:
        response = requests.get(f"{BASE_URL}{base_currency}", timeout=5)
        data = response.json()
        if response.status_code != 200:
            return None, f"API Error: {data.get('error', 'Unknown error')}"
        cache["data"] = data
        cache["timestamp"] = datetime.now()
        cache["base"] = base_currency
        return data, None
    except requests.RequestException as e:
        return None, f"Failed to contact exchange rate service: {str(e)}"

@app.route("/")
def index():
    return render_template("index.html", currencies=CURRENCIES)

@app.route("/convert", methods=["POST"])
def convert_page():
    from_currency = request.form.get("from_currency")
    to_currency = request.form.get("to_currency")
    amount_str = request.form.get("amount")

    # Validate input
    if not from_currency or not to_currency or not amount_str:
        return render_template("index.html", error="All fields are required.", currencies=CURRENCIES)

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        return render_template("index.html", error="Amount must be a positive number.", currencies=CURRENCIES)

    # Get rates
    data, error = get_all_rates("USD")
    if error:
        return render_template("index.html", error=error, currencies=CURRENCIES)

    try:
        if from_currency == "USD":
            converted = amount * data["rates"].get(to_currency, 0)
        elif to_currency == "USD":
            converted = amount / data["rates"].get(from_currency, 1)
        else:
            converted = amount * (data["rates"].get(to_currency, 0) / data["rates"].get(from_currency, 1))
    except Exception:
        return render_template("index.html", error="Error calculating conversion.", currencies=CURRENCIES)

    return render_template(
        "index.html",
        result=round(converted, 2),
        from_currency=from_currency,
        to_currency=to_currency,
        amount=amount,
        currencies=CURRENCIES
    )

@app.route("/save", methods=["POST"])
def save_conversion():
    try:
        data = {
            "from_currency": request.form["from_currency"],
            "to_currency": request.form["to_currency"],
            "amount": float(request.form["amount"]),
            "result": float(request.form["result"])
        }
        response = supabase.table("conversions").insert(data).execute()
        return render_template(
            "index.html",
            success="Saved successfully!",
            currencies=CURRENCIES
        )
    except Exception as e:
        return render_template(
            "index.html",
            error=str(e),
            currencies=CURRENCIES
        )

@app.route("/history")
def history():
    response = supabase.table("conversions").select("*").execute()
    saved = response.data
    return render_template("history.html", saved=saved)

# API endpoints (unchanged)
@app.route("/api/rates")
def get_rates():
    base = request.args.get("base", "USD")
    data, error = get_all_rates(base)
    if error:
        return jsonify({"error": error}), 503
    return jsonify({
        "base": data["base"],
        "date": data["date"],
        "rates": data["rates"]
    })

@app.route("/api/convert")
def convert_currency():
    try:
        from_currency = request.args.get("from", "USD").upper()
        to_currency = request.args.get("to", "EUR").upper()
        amount = float(request.args.get("amount", 1))
        if amount <= 0:
            return jsonify({"error": "Amount must be greater than 0"}), 400
        if from_currency not in CURRENCIES or to_currency not in CURRENCIES:
            return jsonify({"error": "Invalid currency code"}), 400
        data, error = get_all_rates("USD")
        if error:
            return jsonify({"error": error}), 503
        if from_currency not in data["rates"] or to_currency not in data["rates"]:
            return jsonify({"error": "Currency not supported"}), 400
        if from_currency == "USD":
            converted = amount * data["rates"][to_currency]
            rate = data["rates"][to_currency]
        elif to_currency == "USD":
            converted = amount / data["rates"][from_currency]
            rate = 1 / data["rates"][from_currency]
        else:
            converted = amount * (data["rates"][to_currency] / data["rates"][from_currency])
            rate = data["rates"][to_currency] / data["rates"][from_currency]
        return jsonify({
            "from": from_currency,
            "to": to_currency,
            "amount": amount,
            "converted": round(converted, 2),
            "rate": round(rate, 4),
            "date": data["date"]
        })
    except ValueError:
        return jsonify({"error": "Invalid amount format"}), 400
    except KeyError as e:
        return jsonify({"error": f"Currency not found: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Conversion failed: {str(e)}"}), 500

@app.route("/api/currencies")
def get_currencies():
    return jsonify({
        "currencies": CURRENCIES,
        "count": len(CURRENCIES)
    })

if __name__ == "__main__":
    app.run(debug=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)