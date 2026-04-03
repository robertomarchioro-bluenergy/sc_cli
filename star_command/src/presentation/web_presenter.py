"""
Collecting Presenter per l'interfaccia web.
Bufferizza tutti gli output in una lista di dict, sincronizza
con il game loop tramite threading.Event.
Il game loop gira in un thread separato e si blocca su get_captain_input();
Flask fornisce il comando via set_command() e legge il buffer via flush().
"""
from __future__ import annotations

import threading
from typing import Any

from .base_presenter import BasePresenter


class WebPresenter(BasePresenter):
    """Presenter che raccoglie output per inviarli via JSON al frontend."""

    def __init__(self) -> None:
        self._output_buffer: list[dict[str, Any]] = []
        self._bridge_state: dict[str, Any] | None = None
        self._lock = threading.Lock()

        # Sincronizzazione game loop <-> Flask
        self._command_event = threading.Event()
        self._output_ready = threading.Event()

        self._pending_command: str | None = None
        self._pending_confirm: bool | None = None
        self._needs_confirm: bool = False
        self._game_over: bool = False

    # ── Metodi Protocol PresenterInterface ──────────────

    def render_bridge(self, game_state: dict) -> None:
        with self._lock:
            self._bridge_state = game_state

    def show_officer_message(
        self, officer_name: str, role: str, message: str, trust: float
    ) -> None:
        self._append({
            "type": "officer_message",
            "officer_name": officer_name,
            "role": role,
            "message": message,
            "trust": trust,
        })

    def show_narrative_short(self, text: str, color: str) -> None:
        self._append({"type": "narrative", "text": text, "color": color})

    def show_narrative_long(self, text: str, title: str) -> None:
        self._append({"type": "narrative_long", "text": text, "title": title})

    def show_map_overlay(self, galaxy_state: dict, ship_position: tuple) -> None:
        self._append({
            "type": "map_overlay",
            "galaxy": galaxy_state,
            "ship_position": list(ship_position),
        })

    def show_systems_overlay(self, systems_state: dict, repair_queue: list) -> None:
        self._append({
            "type": "systems_overlay",
            "systems": systems_state,
            "repair_queue": repair_queue,
        })

    def show_captain_log_overlay(self, entries: list) -> None:
        self._append({"type": "captain_log_overlay", "entries": entries})

    def show_contextual_menu(self, context: str) -> str:
        self._append({"type": "contextual_menu", "context": context})
        return ""

    def get_captain_input(self) -> str:
        """Blocca il game loop thread finche Flask non fornisce un comando."""
        self._output_ready.set()
        self._command_event.wait()
        self._command_event.clear()
        cmd = self._pending_command or ""
        self._pending_command = None
        return cmd

    def show_confirm(self, message: str) -> bool:
        """Blocca il game loop thread finche Flask non fornisce la conferma."""
        self._append({"type": "confirm_request", "message": message})
        self._needs_confirm = True
        self._output_ready.set()
        self._command_event.wait()
        self._command_event.clear()
        self._needs_confirm = False
        result = self._pending_confirm if self._pending_confirm is not None else False
        self._pending_confirm = None
        return result

    # ── Metodi extra (usati da main.py web) ─────────────

    def show_title_screen(self) -> None:
        self._append({"type": "title_screen"})

    def show_mission_briefing(self, mission: dict) -> None:
        self._append({"type": "mission_briefing", "mission": mission})

    def show_game_over(self, reason: str, victory: bool) -> None:
        self._append({
            "type": "game_over",
            "reason": reason,
            "victory": victory,
        })
        self._game_over = True

    def show_resupply(self, messages: list[str]) -> None:
        self._append({"type": "resupply", "messages": messages})

    # ── API per Flask ───────────────────────────────────

    def set_command(self, command: str) -> None:
        """Chiamato da Flask per fornire il comando al game loop."""
        self._pending_command = command
        self._command_event.set()

    def set_confirm(self, value: bool) -> None:
        """Chiamato da Flask per fornire la conferma al game loop."""
        self._pending_confirm = value
        self._command_event.set()

    def wait_for_output(self, timeout: float = 60.0) -> bool:
        """Flask chiama questo per aspettare che il game loop produca output."""
        ready = self._output_ready.wait(timeout=timeout)
        self._output_ready.clear()
        return ready

    def flush(self) -> dict[str, Any]:
        """Restituisce e svuota il buffer di output + bridge state."""
        with self._lock:
            result = {
                "bridge_state": self._bridge_state,
                "output": list(self._output_buffer),
                "needs_confirm": self._needs_confirm,
                "game_over": self._game_over,
            }
            self._output_buffer.clear()
            return result

    @property
    def bridge_state(self) -> dict[str, Any] | None:
        with self._lock:
            return self._bridge_state

    # ── Interno ─────────────────────────────────────────

    def _append(self, msg: dict[str, Any]) -> None:
        with self._lock:
            self._output_buffer.append(msg)
