from flask import Flask, request, jsonify, redirect
from kiteconnect import KiteConnect
import os

app = Flask(__name__)

api_key = os.environ.get("KITE_API_KEY")
api_secret = os.environ.get("KITE_API_SECRET")

kite = KiteConnect(api_key=api_key)

@app.route('/')
def home():
    login_url = kite.login_url()
    return jsonify({
        "status": "FMS - Fractal Market Script is live",
        "login_url": login_url
    })

@app.route('/callback')
def callback():
    request_token = request.args.get('request_token')
    if not request_token:
        return jsonify({"error": "No request token received"}), 400
    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        kite.set_access_token(access_token)
        return jsonify({
            "status": "authenticated",
            "access_token": access_token
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
