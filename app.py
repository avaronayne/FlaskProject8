import os
from dotenv import load_dotenv
load_dotenv()
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, jsonify
from datetime import datetime
##


app = Flask(__name__)

# ---------------------------
# Configuration
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

# Simple cache for exchange rates
cache = {"data": None, "timestamp": None, "base": None}

# ---------------------------
# Database helpers (using your table columns)
# ---------------------------
def get_db_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def save_conversion_db(amount, from_cur, to_cur, result):
    """Save a conversion to the PostgreSQL database using your table columns."""
    if not DATABASE_URL:
        print(" DATABASE_URL missing – cannot save")
        return False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Note: column names are from_currency, to_currency, amount, result (all text)
                cur.execute("""
                    INSERT INTO conversions (from_currency, to_currency, amount, result)
                    VALUES (%s, %s, %s, %s)
                """, (from_cur, to_cur, str(amount), str(result)))
            conn.commit()
        print(f"Saved: {amount} {from_cur} → {result} {to_cur}")
        return True
    except Exception as e:
        print(f"DB save error: {e}")
        return False

def load_conversions():
    """Load all saved conversions, newest first."""
    if not DATABASE_URL:
        return []
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM conversions ORDER BY created_at DESC")
                rows = cur.fetchall()
                # Convert amount and result from text to float for display
                for row in rows:
                    row['amount'] = float(row['amount']) if row['amount'] else 0
                    row['result'] = float(row['result']) if row['result'] else 0
                return rows
    except Exception as e:
        print(f" DB load error: {e}")
        return []

# ---------------------------
# Exchange rate API with caching
# ---------------------------
def get_all_rates(base_currency="USD"):
    global cache
    now = datetime.now()
    if (cache["data"] and cache["base"] == base_currency and
        cache["timestamp"] and (now - cache["timestamp"]).seconds < 3600):
        return cache["data"], None
    try:
        response = requests.get(f"{BASE_URL}{base_currency}", timeout=5)
        data = response.json()
        if response.status_code != 200:
            return None, f"API Error: {data.get('error', 'Unknown error')}"
        cache["data"] = data
        cache["timestamp"] = now
        cache["base"] = base_currency
        return data, None
    except requests.RequestException as e:
        return None, f"Failed to contact exchange rate service: {str(e)}"

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
        return render_template("index.html", error="Amount must be a positive number", currencies=CURRENCIES)

    data, error = get_all_rates("USD")
    if error:
        return render_template("index.html", error=error, currencies=CURRENCIES)

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

    return render_template("index.html",
                           result=result,
                           from_currency=from_cur,
                           to_currency=to_cur,
                           amount=amount,
                           currencies=CURRENCIES)

@app.route("/save", methods=["POST"])
def save():
    from_cur = request.form.get("from_cur")
    to_cur = request.form.get("to_cur")
    amount_str = request.form.get("amount")
    result_str = request.form.get("result")

    if not all([from_cur, to_cur, amount_str, result_str]):
        return render_template("index.html", error="Missing data – cannot save", currencies=CURRENCIES)

    try:
        amount = float(amount_str)
        result = float(result_str)
    except ValueError:
        return render_template("index.html", error="Invalid numeric data", currencies=CURRENCIES)

    save_conversion_db(amount, from_cur, to_cur, result)
    return render_template("index.html", success="Conversion saved!", currencies=CURRENCIES)

@app.route("/history")
def history():
    saved = load_conversions()
    # Use a template that matches your column names (from_currency, to_currency, etc.)
    return render_template("history.html", saved=saved)

# ---------------------------
# API endpoints (unchanged, but you can keep them)
# ---------------------------
@app.route("/api/rates")
def api_rates():
    base = request.args.get("base", "USD")
    data, error = get_all_rates(base)
    if error:
        return jsonify({"error": error}), 503
    return jsonify({"base": data["base"], "date": data["date"], "rates": data["rates"]})

@app.route("/api/convert")
def api_convert():
    try:
        from_cur = request.args.get("from", "USD").upper()
        to_cur = request.args.get("to", "EUR").upper()
        amount = float(request.args.get("amount", 1))
        if amount <= 0:
            return jsonify({"error": "Amount must be > 0"}), 400
        if from_cur not in CURRENCIES or to_cur not in CURRENCIES:
            return jsonify({"error": "Invalid currency"}), 400
        data, error = get_all_rates("USD")
        if error:
            return jsonify({"error": error}), 503
        rates = data["rates"]
        if from_cur == "USD":
            converted = amount * rates[to_cur]
            rate = rates[to_cur]
        elif to_cur == "USD":
            converted = amount / rates[from_cur]
            rate = 1 / rates[from_cur]
        else:
            converted = amount * (rates[to_cur] / rates[from_cur])
            rate = rates[to_cur] / rates[from_cur]
        return jsonify({
            "from": from_cur,
            "to": to_cur,
            "amount": amount,
            "converted": round(converted, 2),
            "rate": round(rate, 4),
            "date": data["date"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/currencies")
def api_currencies():
    return jsonify({"currencies": CURRENCIES, "count": len(CURRENCIES)})

@app.route("/health")
def health():
    db_ok = False
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                db_ok = True
    except:
        pass
    #api_ok = get_all_rates()[0] is not None
    data, error = get_all_rates()
    api_ok = data is not None
    status = "ok" if db_ok and api_ok else "degraded"
    return jsonify({
        "status": status,
        "database": "up" if db_ok else "down",
        "exchange_api": "up" if api_ok else "down",
        "timestamp": datetime.utcnow().isoformat()
    })
@app.route("/debug")
def debug():
    import os
    db_url = os.environ.get("DATABASE_URL", "NOT SET")
    result = f"DATABASE_URL: {' Set' if db_url != 'NOT SET' else ' Missing'}<br>"
    if db_url != "NOT SET":
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM conversions")
                count = cur.fetchone()[0]
            result += f" Database connected. 'conversions' table exists. Row count: {count}<br>"
            # Try a test insert
            test_from = "TEST"
            test_to = "TEST"
            test_amount = "1.23"
            test_result = "4.56"
            cur.execute("""
                INSERT INTO conversions (from_currency, to_currency, amount, result)
                VALUES (%s, %s, %s, %s)
            """, (test_from, test_to, test_amount, test_result))
            conn.commit()
            result += " Test insert succeeded. Check your history page now.<br>"
        except Exception as e:
            result += f" Database error: {e}<br>"
    return result

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)