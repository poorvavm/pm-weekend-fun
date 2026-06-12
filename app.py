from flask import Flask, render_template, jsonify, request
from agent import config, geo
from agent.claude_agent import get_events_json

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/config")
def config_page():
    return render_template("config.html")


@app.route("/api/events", methods=["POST"])
def events():
    try:
        data = get_events_json()
        return jsonify({"ok": True, **data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify({"ok": True, "config": config.load_config()})


@app.route("/api/geo/states", methods=["GET"])
def api_geo_states():
    return jsonify({"ok": True, "states": geo.list_states()})


@app.route("/api/geo/cities", methods=["GET"])
def api_geo_cities():
    state = request.args.get("state", "")
    return jsonify({"ok": True, "cities": geo.list_cities(state)})


@app.route("/api/geo/nearby", methods=["GET"])
def api_geo_nearby():
    state = request.args.get("state", "")
    city = request.args.get("city", "")
    try:
        radius = float(request.args.get("radius", "25"))
    except ValueError:
        return jsonify({"ok": False, "error": "radius must be a number"}), 400
    if radius <= 0 or radius > 500:
        return jsonify({"ok": False, "error": "radius must be between 1 and 500 miles"}), 400

    try:
        cap = int(request.args.get("cap", "25"))
    except ValueError:
        cap = 25
    cap = max(1, min(cap, 100))

    nearby = geo.cities_within_radius(state, city, radius, cap=cap)
    if not nearby:
        return jsonify({
            "ok": False,
            "error": f"City '{city}' not found in state '{state.upper()}'.",
        }), 404

    region_name = f"Within {int(radius)}mi of {nearby[0]['name']}, {state.upper()}"
    cities = [
        {"name": c["name"], "slug": geo.slugify(c["name"]), "distance_mi": c["distance_mi"]}
        for c in nearby
    ]
    return jsonify({
        "ok": True,
        "region_name": region_name,
        "state": state.lower(),
        "cities": cities,
    })


@app.route("/api/config/reset", methods=["POST"])
def api_reset_config():
    import json as _json
    saved = config.save_config(_json.loads(_json.dumps(config.DEFAULT_CONFIG)))
    return jsonify({"ok": True, "config": saved})


@app.route("/api/config", methods=["POST"])
def api_save_config():
    try:
        body = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"ok": False, "error": "Request body must be valid JSON."}), 400

    try:
        saved = config.save_config(body)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to save config: {e}"}), 500

    return jsonify({"ok": True, "config": saved})


if __name__ == "__main__":
    app.run(debug=True, port=5050, threaded=True)
