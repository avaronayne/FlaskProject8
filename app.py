import requests
from flask import Flask, jsonify, render_template, request, session
from datetime import datetime
import os

SAVE_FILE = "saved_conversions.json"

def load_conversions():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r') as f:
            return json.load(f)
    return []

def save_conversions(conversions):
    with open(SAVE_FILE, 'w') as f:
        json.dump(conversions, f, indent=2)

app = Flask(__name__)

# -----------------------
# CONFIGURATION
# -----------------------
API_KEY = "9ea12d667dbda46fd01fd9a2"
BASE_URL = "https://api.exchangerate-api.com/v4/latest/"

# Common currencies for dropdown
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
    """Fetch exchange rates from API with simple caching"""
    global cache

    # Check if we have cached data and it's less than 1 hour old
    if (cache["data"] and
            cache["base"] == base_currency and
            cache["timestamp"] and
            (datetime.now() - cache["timestamp"]).seconds < 3600):
        return cache["data"], None

    try:
        response = requests.get(
            f"{BASE_URL}{base_currency}",
            timeout=5
        )
        data = response.json()

        if response.status_code != 200:
            return None, f"API Error: {data.get('error', 'Unknown error')}"

        # Update cache
        cache["data"] = data
        cache["timestamp"] = datetime.now()
        cache["base"] = base_currency

        return data, None
    except requests.RequestException as e:
        return None, f"Failed to contact exchange rate service: {str(e)}"


@app.route("/")
def index():
    """Render the main page"""
    return render_template("index.html", currencies=CURRENCIES)


@app.route("/convert", methods=["POST"])
def convert_page():
    """Handle conversion from the HTML form, with optional save to session"""
    try:
        # Get form data (matching the HTML field names)
        amount = float(request.form.get("amount", 0))
        from_cur = request.form.get("from_cur", "").upper()
        to_cur = request.form.get("to_cur", "").upper()

        # Validate input
        if amount <= 0:
            return render_template("index.html", error="Amount must be greater than 0", currencies=CURRENCIES)
        if not from_cur or not to_cur:
            return render_template("index.html", error="Please select both currencies", currencies=CURRENCIES)

        # Get exchange rates
        data, error = get_all_rates("USD")
        if error:
            return render_template("index.html", error=error, currencies=CURRENCIES)

        # Perform conversion
        if from_cur == "USD":
            converted = amount * data["rates"][to_cur]
        elif to_cur == "USD":
            converted = amount / data["rates"][from_cur]
        else:
            converted = amount * (data["rates"][to_cur] / data["rates"][from_cur])

        result = round(converted, 2)

        # Check if Save button was clicked
        if 'save' in request.form:
            # Initialize session history if not present
            if 'history' not in session:
                session['history'] = []
            # Append the conversion record
            session['history'].append({
                'amount': amount,
                'from': from_cur,
                'to': to_cur,
                'result': result,
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            session.modified = True

        # Render the page with the result
        return render_template("index.html", result=result, currencies=CURRENCIES)

    except KeyError as e:
        return render_template("index.html", error=f"Currency not found: {str(e)}", currencies=CURRENCIES)
    except ValueError:
        return render_template("index.html", error="Invalid amount format", currencies=CURRENCIES)
    except Exception as e:
        return render_template("index.html", error=f"Conversion failed: {str(e)}", currencies=CURRENCIES)


@app.route("/history")
def history():
    """Display saved conversion history from session"""
    saved = session.get('history', [])
    return render_template("history.html", saved=saved)


# -----------------------
# API ENDPOINTS (unchanged)
# -----------------------
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
