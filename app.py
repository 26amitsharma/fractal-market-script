from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "FMS - Fractal Market Script is live"})

@app.route('/callback')
def callback():
    request_token = request.args.get('request_token')
    return jsonify({"request_token": request_token, "status": "received"})

if __name__ == '__main__':
    app.run(debug=True)
