"""
Flask application — routes API e pagine HTML per Star Command Web.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session, redirect, url_for

from .game_manager import GameManager

# Singleton game manager
game_manager = GameManager()


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "star-command-secret-key-change-me")

    # ── Pagine HTML ─────────────────────────────────

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/setup")
    def setup():
        data = game_manager.get_setup_data()
        return render_template("setup.html", **data)

    @app.route("/game")
    def game():
        sid = session.get("game_session_id")
        if not sid or not game_manager.get_session(sid):
            return redirect(url_for("setup"))
        return render_template("bridge.html")

    # ── API JSON ────────────────────────────────────

    @app.route("/api/start", methods=["POST"])
    def api_start():
        data = request.get_json() or {}
        ship_name = data.get("ship_name", "USS Enterprise")
        ship_class = data.get("ship_class", "GALAXY")
        difficulty = data.get("difficulty", "NORMAL")
        campaign_id = data.get("campaign", "crisis_of_korvath")

        sid = game_manager.create_session()
        session["game_session_id"] = sid

        result = game_manager.start_game(sid, ship_name, ship_class, difficulty, campaign_id)
        return jsonify(result)

    @app.route("/api/command", methods=["POST"])
    def api_command():
        sid = session.get("game_session_id")
        gs = game_manager.get_session(sid) if sid else None
        if not gs:
            return jsonify({"error": "Nessuna sessione attiva"}), 404

        if not gs.is_alive:
            return jsonify({
                "error": "Partita terminata",
                "end_reason": gs.end_reason,
                **gs.presenter.flush(),
            })

        data = request.get_json() or {}
        command = data.get("command", "")

        gs.presenter.set_command(command)
        gs.presenter.wait_for_output(timeout=60.0)

        result = gs.presenter.flush()
        if not gs.is_alive:
            result["end_reason"] = gs.end_reason
        return jsonify(result)

    @app.route("/api/confirm", methods=["POST"])
    def api_confirm():
        sid = session.get("game_session_id")
        gs = game_manager.get_session(sid) if sid else None
        if not gs:
            return jsonify({"error": "Nessuna sessione attiva"}), 404

        data = request.get_json() or {}
        answer = data.get("confirm", False)

        gs.presenter.set_confirm(answer)
        gs.presenter.wait_for_output(timeout=60.0)

        result = gs.presenter.flush()
        if not gs.is_alive:
            result["end_reason"] = gs.end_reason
        return jsonify(result)

    @app.route("/api/state")
    def api_state():
        sid = session.get("game_session_id")
        gs = game_manager.get_session(sid) if sid else None
        if not gs:
            return jsonify({"error": "Nessuna sessione attiva"}), 404
        return jsonify({
            "bridge_state": gs.presenter.bridge_state,
            "is_alive": gs.is_alive,
            "end_reason": gs.end_reason,
        })

    @app.route("/api/quit", methods=["POST"])
    def api_quit():
        sid = session.get("game_session_id")
        if sid:
            gs = game_manager.get_session(sid)
            if gs and gs.is_alive:
                gs.presenter.set_command("esci")
                gs.presenter.wait_for_output(timeout=5.0)
                # Auto-conferma quit
                gs.presenter.set_confirm(True)
                gs.presenter.wait_for_output(timeout=5.0)
            game_manager.remove_session(sid)
            session.pop("game_session_id", None)
        return jsonify({"status": "ok"})

    return app
