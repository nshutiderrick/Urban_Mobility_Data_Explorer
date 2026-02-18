# backend\api\app.py
# Main Flask application instance for the NYC Taxi API.
# This file initializes the Flask app and defines the basic home route.

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "Taxi API is running"

if __name__ == '__main__':
    app.run(debug=True)
