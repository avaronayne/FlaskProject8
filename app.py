import os
import requests
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv

#Load environment variables from .env
load_dotenv()

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
TICKETMASTER_API_KEY = os.getenv("TICKETMASTER_API_KEY")
TICKETMASTER_URL = "https://oauth.ticketmaster.com/oauth/login"

# -----------------------
# HARD-CODED CONFIG (DEMO ONLY)
# -----------------------

def get_events(city):
    try:
        r = requests.get(
            TICKETMASTER_URL,
            params={
                "apikey": TICKETMASTER_API_KEY,
                "city": city,
                "size": 5,            # limit events per city
                "sort": "date,asc"
            },
            timeout=5
        )

        data = r.json()

        if r.status_code != 200 or "_embedded" not in data:
            return {"city": city, "events": []}

        events = []
        for e in data["_embedded"]["events"]:
            events.append({
                "name": e["name"],
                "date": e["dates"]["start"].get("localDate"),
                "venue": e["_embedded"]["venues"][0]["name"]
            })

        return {
            "city": city,
            "events": events
        }

    except requests.RequestException as e:
        return {
            "city": city,
            "error": str(e)
        }



if __name__ == "__main__":
    app.run(debug=True)
