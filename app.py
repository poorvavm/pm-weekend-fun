from flask import Flask, render_template, jsonify
from agent.claude_agent import get_events_json

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/events", methods=["POST"])
def events():
    try:
        data = get_events_json()
        return jsonify({"ok": True, **data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5050, threaded=True)
