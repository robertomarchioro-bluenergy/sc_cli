"""
Gestione sessioni di gioco thread-safe.
Ogni sessione avvia il game loop in un thread daemon e comunica
con Flask tramite il WebPresenter.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.engine.campaign import Campaign, CampaignState, save_campaign_state
from src.engine.captain_log import CaptainLog, LogTrigger, check_log_triggers
from src.engine.difficulty import DifficultyConfig, DifficultyPreset
from src.engine.galaxy import Galaxy, CellContent
from src.engine.game_loop import GameState, run_game_loop
from src.engine.ship import Ship, ShipClass, SHIP_CLASS_STATS
from src.engine.systems import create_default_systems, RepairQueue
from src.officers import TacticalOfficer, EngineerOfficer, ScienceOfficer, MedicalOfficer
from src.officers.base_officer import InteractionMode
from src.officers.special.vulcan_ambassador import VulcanAmbassador
from src.presentation.web_presenter import WebPresenter

logger = logging.getLogger(__name__)

DEFAULT_CAMPAIGN = Path(__file__).parent.parent / "src" / "config" / "campaigns" / "crisis_of_korvath.yaml"


def _create_anthropic_client(api_key: str | None):
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        return None


def _create_officers(client, model: str, interaction_mode: InteractionMode,
                     special_officers: list[str], ship_name: str) -> dict[str, object]:
    officers: dict[str, object] = {
        "tattico": TacticalOfficer.create_default(client=client, model=model, interaction_mode=interaction_mode),
        "ingegnere": EngineerOfficer.create_default(client=client, model=model, interaction_mode=interaction_mode),
        "scientifico": ScienceOfficer.create_default(client=client, model=model, interaction_mode=interaction_mode),
        "medico": MedicalOfficer.create_default(client=client, model=model, interaction_mode=interaction_mode),
    }
    if "ambasciatore_vulcaniano" in special_officers:
        officers["speciale"] = VulcanAmbassador.create_default(ship_name=ship_name, client=client, model=model)
    return officers


@dataclass
class GameSession:
    """Una sessione di gioco attiva."""
    session_id: str
    presenter: WebPresenter
    game_state: GameState | None = None
    campaign: Campaign | None = None
    campaign_state: CampaignState | None = None
    officers: dict[str, object] = field(default_factory=dict)
    difficulty: DifficultyConfig | None = None
    client: object = None
    model: str = "claude-sonnet-4-20250514"
    loop_thread: threading.Thread | None = None
    end_reason: str | None = None
    is_alive: bool = False
    ship_name: str = "USS Enterprise"
    ship_class: ShipClass = ShipClass.GALAXY


class GameManager:
    """Gestisce tutte le sessioni di gioco attive."""

    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._lock = threading.Lock()

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        presenter = WebPresenter()
        session = GameSession(session_id=session_id, presenter=presenter)
        with self._lock:
            self._sessions[session_id] = session
        return session_id

    def get_session(self, session_id: str) -> GameSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def get_setup_data(self) -> dict[str, Any]:
        """Restituisce i dati per la pagina di setup."""
        difficulties = [{"id": p.name, "label": p.value} for p in DifficultyPreset]
        ships = []
        for sc in ShipClass:
            stats = SHIP_CLASS_STATS[sc]
            ships.append({
                "id": sc.name,
                "label": sc.value,
                "crew": stats.crew,
                "energy": int(stats.energy),
                "shields": int(stats.shields),
                "torpedoes": stats.torpedoes,
                "dilithium": stats.dilithium,
            })
        return {"difficulties": difficulties, "ships": ships}

    def start_game(self, session_id: str, ship_name: str,
                   ship_class_id: str, difficulty_id: str) -> dict[str, Any]:
        """Inizializza e avvia il game loop in un thread."""
        session = self.get_session(session_id)
        if session is None:
            return {"error": "Sessione non trovata"}

        load_dotenv()
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("STAR_COMMAND_OFFICER_MODEL", "claude-sonnet-4-20250514")
        mode_str = os.getenv("STAR_COMMAND_INTERACTION_MODE", "CONTEXT")
        try:
            interaction_mode = InteractionMode(mode_str)
        except ValueError:
            interaction_mode = InteractionMode.CONTEXT

        # Difficolta
        preset = DifficultyPreset[difficulty_id]
        difficulty = DifficultyConfig.from_preset(preset)

        # Nave
        ship_class = ShipClass[ship_class_id]
        ship = Ship.create(ship_name, ship_class)
        is_intrepid = ship_class == ShipClass.INTREPID
        systems = create_default_systems(is_intrepid=is_intrepid)
        repair_queue = RepairQueue()
        captain_log = CaptainLog()

        # Client API
        client = _create_anthropic_client(api_key)

        # Campagna
        campaign = Campaign()
        campaign.load_from_yaml(str(DEFAULT_CAMPAIGN))

        campaign_state = CampaignState(
            nome_campagna=campaign.nome,
            captain_name="Capitano",
            ship=ship,
            systems=systems,
            repair_queue=repair_queue,
            difficulty=difficulty,
            captain_log=captain_log,
            stardate=campaign.stardate_inizio,
        )

        # Prima missione
        mission = campaign.get_next_mission(campaign_state.missions_completed)
        if mission is None:
            return {"error": "Nessuna missione disponibile"}

        # Galaxy
        galaxy = Galaxy()
        galaxy.generate(mission.seed_galassia, mission.to_dict())
        ship.position = (1, 1, 4, 4)
        galaxy.set_sector(1, 1, 4, 4, CellContent.SHIP)

        # Ufficiali
        officers = _create_officers(client, model, interaction_mode,
                                    mission.consiglieri_speciali, ship_name)

        # GameState
        game_state = GameState(
            ship=ship, galaxy=galaxy, systems=systems,
            repair_queue=repair_queue, difficulty=difficulty,
            captain_log=captain_log, mission=mission,
            stardate=campaign_state.stardate,
        )

        # Salva nella sessione
        session.game_state = game_state
        session.campaign = campaign
        session.campaign_state = campaign_state
        session.officers = officers
        session.difficulty = difficulty
        session.client = client
        session.model = model
        session.ship_name = ship_name
        session.ship_class = ship_class

        # Log trigger inizio missione
        check_log_triggers(
            trigger=LogTrigger.MISSION_START,
            event_data={"missione": mission.nome, "obiettivo": mission.obiettivo_testo},
            captain_log=captain_log, stardate=game_state.stardate,
            mission_id=mission.id, ship_name=ship_name,
            ship_class=ship_class, client=client, model=model,
        )

        # Avvia game loop in thread
        def _run_loop():
            try:
                reason = run_game_loop(
                    game_state=game_state, officers=officers,
                    presenter=session.presenter, difficulty=difficulty,
                    client=client, model=model,
                )
                session.end_reason = reason
            except Exception as e:
                logger.error("Game loop crashed: %s", e)
                session.end_reason = f"Errore: {e}"
            finally:
                session.is_alive = False
                # Segnala che l'output finale e pronto
                session.presenter._output_ready.set()

        session.is_alive = True
        thread = threading.Thread(target=_run_loop, daemon=True, name=f"game-{session_id[:8]}")
        session.loop_thread = thread
        thread.start()

        # Aspetta il primo render
        session.presenter.wait_for_output(timeout=30.0)

        return {
            "status": "started",
            "mission": mission.to_dict(),
            **session.presenter.flush(),
        }
