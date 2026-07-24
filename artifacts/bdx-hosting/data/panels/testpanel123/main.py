from flask import Flask, jsonify, request
import os

app = Flask(__name__)

@app.route("/")
def index():
    return "<h1>Hello from T10-MEHEDI hosted Flask!</h1><p>Your app is live via public URL.</p>"

@app.route("/api/info")
def info():
    return jsonify({"status": "online", "app": "Test Flask", "hosted_by": "T10-MEHEDI"})

@app.route("/hello/<name>")
def hello(name):
    return f"<h2>Hello, {name}! Your Flask app is working via public URL.</h2>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[TEST] Flask running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
