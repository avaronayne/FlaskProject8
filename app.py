import os

import requests
from flask import Flask, jsonify
from flask import Flask, jsonify, render_template
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()


app = Flask(__name__)

# -----------------------
# HARD-CODED CONFIG (DEMO ONLY)
# -----------------------

DATABASE_URL = os.getenv("DATABASE_URL")


if __name__ == "__main__":
    app.run(debug=True)
