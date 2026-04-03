"""
Game Loop principale — orchestratore che coordina engine, ufficiali e presenter.
Determina il contesto corrente, gestisce turni di combattimento e navigazione,
e verifica le condizioni di fine partita/missione.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

from .ship import Ship
from .galaxy import Galaxy, CellContent, QuadrantVisibility
from .systems import ShipSystem, SystemName, RepairQueue, create_default_systems
from .combat import (
    Enemy, CombatResult, CombatAction,
    check_ambush, calcola_colpo_faser, calcola_colpo_siluro,
    calcola_colpo_nemico, check_torpedo_misfire,
    get_enemy_action, calculate_distance,
)
from .navigation import navigate_warp, navigate_impulse
from .difficulty import DifficultyConfig
from .captain_log import CaptainLog, LogTrigger, check_log_triggers, OfficerAPIError
from .campaign import MissionConfig, CampaignState, save_campaign_state
from . import command_parser
from .command_parser import CommandAction, ParsedCommand

logger = logging.getLogger(__name__)


# ── Protocolli per disaccoppiamento layer ────────────────────

class OfficerInterface(Protocol):
    """Interfaccia per un ufficiale AI (ABC nel layer officers)"""
    name: str
    role: str
    trust: float
    personal_morale: float

    def respond(self, game_state: dict, trigger: str) -> str | None: ...
    def update_trust(self, advice_followed: bool) -> None: ...
    def get_bonus_multiplier(self) -> float: ...
    def to_dict(self) -> dict: ...


class PresenterInterface(Protocol):
    """Interfaccia per il presenter (ABC nel layer presentation)"""
    def render_bridge(self, game_state: dict) -> None: ...
    def show_officer_message(self, officer_name: str, role: str, message: str, trust: float) -> None: ...
    def show_narrative_short(self, text: str, color: str) -> None: ...
    def show_narrative_long(self, text: str, title: str) -> None: ...
    def show_map_overlay(self, galaxy_state: dict, ship_position: tuple) -> None: ...
    def show_systems_overlay(self, systems_state: dict, repair_queue: list) -> None: ...
    def show_captain_log_overlay(self, entries: list) -> None: ...
    def show_contextual_menu(self, context: str) -> str: ...
    def get_captain_input(self) -> str: ...
    def show_confirm(self, message: str) -> bool: ...


@dataclass
class AdviceRecord:
    """Registra il consiglio dato dall'ufficiale per tracciare se è stato seguito"""
    officer_role: str
    advice_text: str
    action_suggested: str
    turn_number: int
    followed: bool = False

    def to_dict(self) -> dict:
        return {
            "officer_role": self.officer_role,
            "advice_text": self.advice_text,
            "action_suggested": self.action_suggested,
            "turn_number": self.turn_number,
            "followed": self.followed,
        }


@dataclass
class GameState:
    """Stato completo del gioco per un turno"""
    ship: Ship
    galaxy: Galaxy
    systems: dict[SystemName, ShipSystem]
    repair_queue: RepairQueue
    difficulty: DifficultyConfig
    captain_log: CaptainLog
    mission: MissionConfig
    stardate: float
    turn_number: int = 0
    enemies_in_sector: list[Enemy] = field(default_factory=list)
    docked_at_starbase: bool = False
    crew_casualties_last_turn: int = 0
    anomaly_detected: bool = False
    diplomatic_contact: bool = False
    last_advice: AdviceRecord | None = None
    seen_enemy_types: set[str] = field(default_factory=set)
    mission_completed: bool = False
    mission_failed: bool = False
    faser_hits_on_enemies: dict[str, int] = field(default_factory=dict)  # enemy_id → colpi faser
    quit_requested: bool = False
    save_on_quit: bool = False

    def is_over(self) -> bool:
        """Verifica se la partita è finita"""
        if self.quit_requested:
            return True
        if self.ship.is_destroyed():
            return True
        if self.stardate > self.mission.deadline_stardate:
            return True
        if self.mission_completed or self.mission_failed:
            return True
        return False

    def get_context(self) -> str:
        """Determina il contesto corrente"""
        if self.enemies_in_sector:
            return "COMBAT"
        if self.docked_at_starbase:
            return "DOCKED"
        if self.crew_casualties_last_turn > 0:
            return "AFTER_LOSS"
        if self.anomaly_detected:
            return "EXPLORATION"
        if self.diplomatic_contact:
            return "DIPLOMACY"
        return "NAVIGATION"

    def to_dict(self) -> dict:
        """Serializza lo stato completo per passarlo agli ufficiali"""
        from .systems import systems_to_dict
        return {
            "ship": self.ship.to_dict(),
            "systems": systems_to_dict(self.systems),
            "repair_queue": self.repair_queue.to_dict(),
            "stardate": self.stardate,
            "turn_number": self.turn_number,
            "context": self.get_context(),
            "mission_id": self.mission.id,
            "mission_nome": self.mission.nome,
            "mission_obiettivo": self.mission.obiettivo_testo,
            "deadline_stardate": self.mission.deadline_stardate,
            "enemies": [e.to_dict() for e in self.enemies_in_sector],
            "docked": self.docked_at_starbase,
            "crew_casualties_last_turn": self.crew_casualties_last_turn,
            "anomaly_detected": self.anomaly_detected,
            "diplomatic_contact": self.diplomatic_contact,
        }


# ── Mappatura contesto → ruolo ufficiale di turno ────────────

CONTEXT_OFFICER_MAP: dict[str, str] = {
    "COMBAT": "tattico",
    "NAVIGATION": "scientifico",
    "DOCKED": "ingegnere",
    "AFTER_LOSS": "medico",
    "EXPLORATION": "scientifico",
    "DIPLOMACY": "speciale",
}


def get_active_officer(
    context: str,
    officers: dict[str, OfficerInterface],
) -> OfficerInterface | None:
    """Restituisce l'ufficiale di turno per il contesto corrente"""
    role = CONTEXT_OFFICER_MAP.get(context, "scientifico")
    return officers.get(role)


def check_advice_followed(
    command: ParsedCommand,
    last_advice: AdviceRecord | None,
) -> bool:
    """Verifica se il comando del Capitano segue il consiglio dell'ufficiale"""
    if last_advice is None:
        return False

    # Mappatura semplificata: azione suggerita → azioni compatibili
    suggestion_map: dict[str, set[str]] = {
        "FIRE_PHASER": {CommandAction.FIRE_PHASER.value},
        "FIRE_TORPEDO": {CommandAction.FIRE_TORPEDO.value},
        "SHIELDS_MAX": {CommandAction.SHIELDS_MAX.value, CommandAction.SHIELDS_SET.value},
        "RETREAT": {CommandAction.NAVIGATE_WARP.value, CommandAction.NAVIGATE_IMPULSE.value},
        "SCAN": {CommandAction.SCAN.value},
        "REPAIR": {CommandAction.REPAIR_SYSTEM.value},
        "DOCK": {CommandAction.DOCK_STARBASE.value},
    }
    compatible = suggestion_map.get(last_advice.action_suggested, set())
    return command.action.value in compatible


def execute_command(
    command: ParsedCommand,
    game_state: GameState,
    officers: dict[str, OfficerInterface],
    presenter: PresenterInterface,
    difficulty: DifficultyConfig,
    client: object | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> None:
    """Esegue il comando del Capitano"""
    action = command.action

    if action == CommandAction.SHOW_MAP:
        presenter.show_map_overlay(
            game_state.galaxy.to_dict(),
            game_state.ship.position,
        )

    elif action == CommandAction.SHOW_STATUS:
        presenter.render_bridge(game_state.to_dict())

    elif action == CommandAction.SHOW_SYSTEMS:
        from .systems import systems_to_dict
        presenter.show_systems_overlay(
            systems_to_dict(game_state.systems),
            game_state.repair_queue.to_dict().get("jobs", []),
        )

    elif action == CommandAction.SHOW_CAPTAIN_LOG:
        entries = [e.to_dict() for e in game_state.captain_log.entries]
        presenter.show_captain_log_overlay(entries)

    elif action == CommandAction.SHOW_MISSION:
        presenter.show_narrative_short(
            f"Missione {game_state.mission.id}: {game_state.mission.obiettivo_testo}\n"
            f"Deadline: SD {game_state.mission.deadline_stardate}",
            color="amber",
        )

    elif action == CommandAction.SHOW_MENU:
        context = game_state.get_context()
        presenter.show_contextual_menu(context)

    elif action == CommandAction.FIRE_PHASER:
        _execute_fire_phaser(command, game_state, officers, presenter, difficulty)

    elif action == CommandAction.FIRE_TORPEDO:
        if command_parser.needs_confirmation(action):
            if not presenter.show_confirm("Conferma lancio siluro? [S/N]"):
                presenter.show_narrative_short("Lancio annullato.", color="yellow")
                return
        _execute_fire_torpedo(command, game_state, officers, presenter, difficulty)

    elif action == CommandAction.NAVIGATE_WARP:
        _execute_navigate_warp(command, game_state, presenter, difficulty)

    elif action == CommandAction.NAVIGATE_IMPULSE:
        _execute_navigate_impulse(command, game_state, presenter, difficulty)

    elif action == CommandAction.SCAN:
        _execute_scan(game_state, presenter)

    elif action == CommandAction.SHIELDS_MAX:
        game_state.ship.shields_pct = 100.0
        presenter.show_narrative_short("Scudi al massimo!", color="cyan")

    elif action == CommandAction.SHIELDS_SET:
        level = command.params.get("level", 100)
        game_state.ship.shields_pct = max(0.0, min(100.0, float(level)))
        presenter.show_narrative_short(f"Scudi impostati a {game_state.ship.shields_pct:.0f}%", color="cyan")

    elif action == CommandAction.DOCK_STARBASE:
        _execute_dock(game_state, presenter)

    elif action == CommandAction.REPAIR_SYSTEM:
        system_name = command.params.get("system", "")
        _execute_repair(game_state, presenter, system_name)

    elif action in (
        CommandAction.OFFICER_TACTICAL, CommandAction.OFFICER_ENGINEER,
        CommandAction.OFFICER_SCIENCE, CommandAction.OFFICER_MEDICAL,
        CommandAction.OFFICER_SPECIAL,
    ):
        role_map = {
            CommandAction.OFFICER_TACTICAL: "tattico",
            CommandAction.OFFICER_ENGINEER: "ingegnere",
            CommandAction.OFFICER_SCIENCE: "scientifico",
            CommandAction.OFFICER_MEDICAL: "medico",
            CommandAction.OFFICER_SPECIAL: "speciale",
        }
        role = role_map.get(action, "tattico")
        officer = officers.get(role)
        if officer:
            try:
                response = officer.respond(game_state.to_dict(), trigger="called")
            except (OfficerAPIError, Exception) as e:
                logger.warning("API non disponibile per %s: %s", officer.name, e)
                response = None
                presenter.show_narrative_short(
                    f"[Comunicatore offline] {officer.name} non raggiungibile.", color="yellow"
                )
            if response:
                presenter.show_officer_message(officer.name, role, response, officer.trust)
        else:
            presenter.show_narrative_short("Ufficiale non disponibile.", color="yellow")

    elif action == CommandAction.ACKNOWLEDGE_OFFICER:
        officer_name = command.params.get("officer", "")
        presenter.show_narrative_short(f"Riconoscimento registrato per {officer_name}.", color="green")

    elif action == CommandAction.CREW_MEETING:
        if command_parser.needs_confirmation(action):
            if not presenter.show_confirm("Convocare riunione dell'equipaggio? [S/N]"):
                return
        _execute_crew_meeting(game_state, officers, presenter)

    elif action == CommandAction.CAPTAIN_LOG_MANUAL:
        text = command.params.get("text", "")
        if text:
            game_state.captain_log.add_manual(
                game_state.stardate, text, game_state.mission.id,
            )
            presenter.show_narrative_short("Nota aggiunta al diario.", color="blue")

    elif action == CommandAction.EXPORT_LOG:
        path = game_state.captain_log.export_to_file(game_state.ship.name)
        presenter.show_narrative_short(f"Diario esportato: {path}", color="green")

    elif action == CommandAction.SAVE_AND_QUIT:
        game_state.quit_requested = True
        game_state.save_on_quit = True
        presenter.show_narrative_short("Salvataggio in corso... Rotta verso il porto.", color="cyan")

    elif action == CommandAction.QUIT:
        if command_parser.needs_confirmation(action):
            if not presenter.show_confirm("Abbandonare la missione senza salvare? [S/N]"):
                return
        game_state.quit_requested = True
        game_state.save_on_quit = False
        presenter.show_narrative_short("Il Capitano lascia il ponte di comando.", color="yellow")

    elif action == CommandAction.UNKNOWN:
        context = game_state.get_context()
        presenter.show_contextual_menu(context)

    # Avanza stardate per azione generica (non combattimento)
    if action not in (
        CommandAction.SHOW_MAP, CommandAction.SHOW_STATUS,
        CommandAction.SHOW_SYSTEMS, CommandAction.SHOW_CAPTAIN_LOG,
        CommandAction.SHOW_MISSION, CommandAction.SHOW_MENU,
        CommandAction.OFFICER_TACTICAL, CommandAction.OFFICER_ENGINEER,
        CommandAction.OFFICER_SCIENCE, CommandAction.OFFICER_MEDICAL,
        CommandAction.OFFICER_SPECIAL, CommandAction.CAPTAIN_LOG_MANUAL,
        CommandAction.ACKNOWLEDGE_OFFICER, CommandAction.EXPORT_LOG,
        CommandAction.QUIT, CommandAction.SAVE_AND_QUIT,
        CommandAction.UNKNOWN,
    ):
        game_state.stardate += 0.05
        game_state.turn_number += 1


def _execute_fire_phaser(
    command: ParsedCommand,
    game_state: GameState,
    officers: dict[str, OfficerInterface],
    presenter: PresenterInterface,
    difficulty: DifficultyConfig,
) -> None:
    """Esegue il comando fuoco faser"""
    if not game_state.enemies_in_sector:
        presenter.show_narrative_short("Nessun nemico nel settore.", color="yellow")
        return

    energy = command.params.get("energy", 300)
    if not game_state.ship.consume_energy(float(energy)):
        presenter.show_narrative_short("Energia insufficiente per i faser!", color="red")
        return

    target = game_state.enemies_in_sector[0]
    dist = calculate_distance(game_state.ship.position, target.position)

    advice_followed = game_state.last_advice.followed if game_state.last_advice else False

    hit, damage = calcola_colpo_faser(
        energia_sparata=float(energy),
        distanza=dist,
        ship=game_state.ship,
        systems=game_state.systems,
        advice_followed=advice_followed,
        difficulty=difficulty,
    )

    # Resistenza Borg ai faser
    if target.enemy_type == CellContent.BORG and target.faser_resistance > 0:
        damage *= (1.0 - target.faser_resistance)

    if hit:
        target.apply_damage(damage)
        # Traccia colpi faser per AI Borg
        enemy_id = f"{target.enemy_type.value}_{id(target)}"
        game_state.faser_hits_on_enemies[enemy_id] = (
            game_state.faser_hits_on_enemies.get(enemy_id, 0) + 1
        )
        msg = f"Faser: COLPITO! Danno {damage:.0f} a {target.enemy_type.name}"
        if target.is_destroyed():
            msg += " — DISTRUTTO!"
            game_state.enemies_in_sector.remove(target)
        presenter.show_narrative_short(msg, color="green")
    else:
        presenter.show_narrative_short("Faser: MANCATO!", color="red")

    # Turno combattimento: +0.1 stardate
    game_state.stardate += 0.1


def _execute_fire_torpedo(
    command: ParsedCommand,
    game_state: GameState,
    officers: dict[str, OfficerInterface],
    presenter: PresenterInterface,
    difficulty: DifficultyConfig,
) -> None:
    """Esegue il comando lancio siluro"""
    if not game_state.enemies_in_sector:
        presenter.show_narrative_short("Nessun nemico nel settore.", color="yellow")
        return

    if check_torpedo_misfire(game_state.systems):
        launcher = game_state.systems.get(SystemName.TORPEDO_LAUNCHER)
        if launcher and launcher.status.value == "OFFLINE":
            presenter.show_narrative_short("Lanciasiluri OFFLINE!", color="red")
        else:
            presenter.show_narrative_short("Lanciasiluri: MISFIRING! Siluro perso.", color="red")
            game_state.ship.fire_torpedo()
        return

    if not game_state.ship.fire_torpedo():
        presenter.show_narrative_short("Siluri esauriti!", color="red")
        return

    target = game_state.enemies_in_sector[0]
    advice_followed = game_state.last_advice.followed if game_state.last_advice else False

    damage = calcola_colpo_siluro(target.shields_pct, advice_followed)
    target.apply_damage(damage)

    msg = f"Siluro: IMPATTO! Danno {damage:.0f} a {target.enemy_type.name}"
    if target.is_destroyed():
        msg += " — DISTRUTTO!"
        game_state.enemies_in_sector.remove(target)
    presenter.show_narrative_short(msg, color="green")

    game_state.stardate += 0.1


def _execute_navigate_warp(
    command: ParsedCommand,
    game_state: GameState,
    presenter: PresenterInterface,
    difficulty: DifficultyConfig,
) -> None:
    """Esegue navigazione warp"""
    speed = command.params.get("speed", 1)
    # Per ora, naviga al quadrante specificato o avanza linearmente
    q_row, q_col = game_state.ship.position[0], game_state.ship.position[1]
    # Calcola destinazione semplice: avanza nella direzione warp
    target_q_row = min(8, q_row + 1)
    target_q_col = q_col

    result = navigate_warp(
        game_state.ship, game_state.galaxy, game_state.systems,
        difficulty, target_q_row, target_q_col, warp_speed=speed,
    )
    if result.success:
        game_state.stardate += result.stardate_elapsed
        presenter.show_narrative_short(result.message, color="cyan")
        # Verifica nemici nel nuovo settore
        _check_sector_contents(game_state, presenter)
    else:
        presenter.show_narrative_short(result.message, color="red")


def _execute_navigate_impulse(
    command: ParsedCommand,
    game_state: GameState,
    presenter: PresenterInterface,
    difficulty: DifficultyConfig,
) -> None:
    """Esegue navigazione a impulso"""
    s_row = command.params.get("s_row", 1)
    s_col = command.params.get("s_col", 1)

    result = navigate_impulse(
        game_state.ship, game_state.galaxy, game_state.systems,
        difficulty, s_row, s_col,
    )
    if result.success:
        game_state.stardate += result.stardate_elapsed
        presenter.show_narrative_short(result.message, color="cyan")
        _check_sector_contents(game_state, presenter)
    else:
        presenter.show_narrative_short(result.message, color="red")


def _execute_scan(game_state: GameState, presenter: PresenterInterface) -> None:
    """Esegue scansione del quadrante corrente"""
    q_row, q_col = game_state.ship.position[0], game_state.ship.position[1]

    # Verifica sensori
    sensors = game_state.systems.get(SystemName.SENSORS)
    if sensors and sensors.status.value == "OFFLINE":
        presenter.show_narrative_short("Sensori OFFLINE — scansione impossibile!", color="red")
        return

    game_state.galaxy.scan_quadrant(q_row, q_col)
    game_state.galaxy.update_adjacent_visibility(q_row, q_col)
    summary = game_state.galaxy.get_quadrant_summary(q_row, q_col)

    # Formatta risultati scansione in modo leggibile
    label_map = {
        "KLINGON": ("Klingon", "red"),
        "ROMULAN": ("Romulani", "magenta"),
        "BORG": ("Borg", "red"),
        "SILENTI": ("Silenziosi", "red"),
        "STARBASE": ("Basi stellari", "green"),
        "STAR": ("Stelle", "yellow"),
        "PLANET": ("Pianeti", "blue"),
        "ANOMALY": ("Anomalie", "cyan"),
        "NEBULA": ("Nebule", "cyan"),
        "SILENTI_WRECK": ("Relitti", "yellow"),
    }

    presenter.show_narrative_short(
        f"Scansione quadrante ({q_row},{q_col}) completata.",
        color="blue",
    )
    nebula = "Si" if summary.get("is_nebula") else "No"
    presenter.show_narrative_short(f"  Nebula: {nebula}", color="cyan")

    found_anything = False
    for key, (label, color) in label_map.items():
        count = summary.get(key, 0)
        if count > 0:
            presenter.show_narrative_short(f"  {label}: {count}", color=color)
            found_anything = True

    if not found_anything:
        presenter.show_narrative_short("  Nessuna entita rilevata.", color="dim")

    game_state.stardate += 0.05


def _execute_dock(game_state: GameState, presenter: PresenterInterface) -> None:
    """Tenta l'attracco a una base stellare"""
    q_row, q_col, s_row, s_col = game_state.ship.position
    # Verifica se c'è una base stellare adiacente
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            nr, nc = s_row + dr, s_col + dc
            if 1 <= nr <= 8 and 1 <= nc <= 8:
                if game_state.galaxy.get_sector(q_row, q_col, nr, nc) == CellContent.STARBASE:
                    game_state.docked_at_starbase = True
                    presenter.show_narrative_short(
                        "Attracco completato alla Base Stellare. Rifornimento e riparazioni disponibili.",
                        color="green",
                    )
                    return
    presenter.show_narrative_short("Nessuna base stellare in prossimità.", color="yellow")


def _execute_repair(
    game_state: GameState,
    presenter: PresenterInterface,
    system_name_str: str,
) -> None:
    """Aggiunge un sistema alla coda riparazioni"""
    # Cerca il sistema per nome
    target: SystemName | None = None
    for sn in SystemName:
        if system_name_str.lower() in sn.value.lower():
            target = sn
            break
    if target is None:
        presenter.show_narrative_short(f"Sistema '{system_name_str}' non riconosciuto.", color="yellow")
        return

    priority = 1 if game_state.systems[target].status.value in ("CRITICO", "OFFLINE") else 2
    game_state.repair_queue.add(target, priority, game_state.stardate)
    presenter.show_narrative_short(
        f"Riparazione {target.value} aggiunta alla coda (priorità {priority}).",
        color="green",
    )


def _execute_crew_meeting(
    game_state: GameState,
    officers: dict[str, OfficerInterface],
    presenter: PresenterInterface,
) -> None:
    """Convoca riunione dell'equipaggio — tutti gli ufficiali parlano"""
    presenter.show_narrative_short("── Riunione dell'equipaggio in corso ──", color="amber")
    for role, officer in officers.items():
        try:
            response = officer.respond(game_state.to_dict(), trigger="called")
        except (OfficerAPIError, Exception) as e:
            logger.warning("API non disponibile per %s: %s", officer.name, e)
            response = None
        if response:
            presenter.show_officer_message(officer.name, role, response, officer.trust)


def _check_sector_contents(game_state: GameState, presenter: PresenterInterface) -> None:
    """Verifica il contenuto del settore dopo un movimento"""
    q_row, q_col, s_row, s_col = game_state.ship.position

    # Scan settori adiacenti per nemici
    game_state.enemies_in_sector.clear()
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            nr, nc = s_row + dr, s_col + dc
            if 1 <= nr <= 8 and 1 <= nc <= 8:
                content = game_state.galaxy.get_sector(q_row, q_col, nr, nc)
                if content in (CellContent.KLINGON, CellContent.ROMULAN,
                              CellContent.BORG, CellContent.SILENTI):
                    enemy = Enemy(
                        enemy_type=content,
                        position=(q_row, q_col, nr, nc),
                        was_in_sector=True,
                    )
                    game_state.enemies_in_sector.append(enemy)

                    # Primo avvistamento di tipo nemico
                    if content.name not in game_state.seen_enemy_types:
                        game_state.seen_enemy_types.add(content.name)
                        presenter.show_narrative_short(
                            f"ALLERTA: Primo contatto con {content.name}!",
                            color="red",
                        )

    if game_state.enemies_in_sector:
        presenter.show_narrative_short(
            f"⚠ {len(game_state.enemies_in_sector)} navi ostili rilevate nel settore!",
            color="red",
        )

    # Verifica anomalie
    content = game_state.galaxy.get_sector(q_row, q_col, s_row, s_col)
    if content == CellContent.ANOMALY:
        game_state.anomaly_detected = True
        presenter.show_narrative_short("Anomalia rilevata nella posizione corrente!", color="amber")


def check_end_conditions(game_state: GameState) -> str | None:
    """
    Verifica condizioni di fine partita/missione.
    Ritorna None se in corso, altrimenti il motivo.
    """
    if game_state.ship.hull_pct <= 0:
        game_state.mission_failed = True
        return "Nave distrutta"
    if game_state.ship.crew <= 0:
        game_state.mission_failed = True
        return "Equipaggio perso"
    if game_state.stardate > game_state.mission.deadline_stardate:
        game_state.mission_failed = True
        return "Tempo scaduto — stardate oltre la deadline"
    # Verifica obiettivi completati
    all_objectives_met = all(
        obj.completed for obj in game_state.mission.obiettivi
    )
    if all_objectives_met:
        game_state.mission_completed = True
        return "Missione completata con successo!"
    # Verifica se tutti i nemici sono eliminati (per obiettivi distruggi_nemici)
    for obj in game_state.mission.obiettivi:
        if obj.tipo == "distruggi_nemici" and not obj.completed:
            # Conta nemici rimanenti del tipo richiesto nella galassia
            # (semplificazione: controlla solo il settore corrente per ora)
            pass
    return None


def run_game_loop(
    game_state: GameState,
    officers: dict[str, OfficerInterface],
    presenter: PresenterInterface,
    difficulty: DifficultyConfig,
    client: object | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """
    Loop principale del gioco.
    Ritorna il motivo di fine partita.
    """
    logger.info(
        "Game loop avviato — Missione: %s, SD: %.1f",
        game_state.mission.id,
        game_state.stardate,
    )

    while not game_state.is_over():
        # 1. Aggiorna presentazione (bridge completo)
        presenter.render_bridge(game_state.to_dict())

        # 2. In modalità CONTEXT: ufficiale di turno parla proattivamente
        context = game_state.get_context()
        active_officer = get_active_officer(context, officers)
        if active_officer:
            try:
                advice = active_officer.respond(game_state.to_dict(), trigger="auto")
            except (OfficerAPIError, Exception) as e:
                logger.warning("API non disponibile per %s: %s", active_officer.name, e)
                advice = None
            if advice:
                game_state.last_advice = AdviceRecord(
                    officer_role=active_officer.role,
                    advice_text=advice,
                    action_suggested="",  # verrà estratto dal testo se necessario
                    turn_number=game_state.turn_number,
                )
                presenter.show_officer_message(
                    active_officer.name,
                    active_officer.role.value,
                    advice,
                    active_officer.trust,
                )

        # 3. Leggi comando capitano
        raw_input = presenter.get_captain_input()
        cmd = command_parser.parse(raw_input)

        # 4. Verifica se il comando segue il consiglio dell'ufficiale attivo
        advice_followed = check_advice_followed(cmd, game_state.last_advice)
        if game_state.last_advice:
            game_state.last_advice.followed = advice_followed
            if active_officer:
                active_officer.update_trust(advice_followed)

        # 5. Esegui il comando
        execute_command(cmd, game_state, officers, presenter, difficulty, client, model)

        # 6. Tick riparazioni
        repair_msgs = game_state.repair_queue.tick(
            docked=game_state.docked_at_starbase,
            repair_speed_modifier=difficulty.repair_speed,
            systems=game_state.systems,
        )
        for msg in repair_msgs:
            presenter.show_narrative_short(msg, color="green")

        # 7. Effetti supporto vitale degradato
        life_support = game_state.systems.get(SystemName.LIFE_SUPPORT)
        if life_support:
            if life_support.integrity < 20:
                game_state.ship.adjust_morale(-5.0 * difficulty.morale_decay)
            if life_support.status.value == "OFFLINE":
                lost = game_state.ship.lose_crew(
                    max(1, int(game_state.ship.crew * 0.02))
                )
                game_state.crew_casualties_last_turn = lost
                presenter.show_narrative_short(
                    f"⚠ Supporto vitale OFFLINE — {lost} membri equipaggio persi!",
                    color="red",
                )

        # 8. Turno nemico se in combattimento
        if game_state.enemies_in_sector:
            for enemy in list(game_state.enemies_in_sector):
                enemy_id = f"{enemy.enemy_type.value}_{id(enemy)}"
                faser_hits = game_state.faser_hits_on_enemies.get(enemy_id, 0)
                action = get_enemy_action(
                    enemy, game_state.ship, game_state.systems,
                    game_state.galaxy, game_state.mission.id, faser_hits,
                )
                if action == CombatAction.ATTACK:
                    result = calcola_colpo_nemico(
                        enemy, game_state.ship, game_state.systems, difficulty,
                    )
                    if result.hit:
                        hull_damage = result.damage / game_state.ship.energy_max * 100
                        game_state.ship.apply_hull_damage(hull_damage)
                        presenter.show_narrative_short(result.message, color="red")
                        if result.critical:
                            presenter.show_narrative_short(
                                f"COLPO CRITICO! Sistema {result.system_damaged} danneggiato!",
                                color="red",
                            )
                    else:
                        presenter.show_narrative_short(result.message, color="yellow")
                elif action == CombatAction.RETREAT:
                    game_state.enemies_in_sector.remove(enemy)
                    presenter.show_narrative_short(
                        f"{enemy.enemy_type.name} si ritira dal combattimento!",
                        color="amber",
                    )

        # 9. Verifica trigger per Captain's Log automatico
        end_reason = check_end_conditions(game_state)
        if end_reason:
            trigger = LogTrigger.VICTORY if game_state.mission_completed else LogTrigger.DEFEAT
            check_log_triggers(
                trigger=trigger,
                event_data={"motivo": end_reason},
                captain_log=game_state.captain_log,
                stardate=game_state.stardate,
                mission_id=game_state.mission.id,
                ship_name=game_state.ship.name,
                ship_class=game_state.ship.ship_class,
                client=client,
                model=model,
            )

        # 10. Salvataggio automatico periodico
        if game_state.turn_number % 10 == 0 and game_state.turn_number > 0:
            try:
                save_campaign_state(CampaignState(
                    nome_campagna=game_state.mission.nome,
                    captain_name="Capitano",
                    ship=game_state.ship,
                    systems=game_state.systems,
                    repair_queue=game_state.repair_queue,
                    difficulty=difficulty,
                    captain_log=game_state.captain_log,
                    stardate=game_state.stardate,
                ))
            except Exception:
                logger.warning("Impossibile salvare stato automaticamente")

    # Gestione uscita volontaria
    if game_state.quit_requested:
        if game_state.save_on_quit:
            try:
                save_campaign_state(CampaignState(
                    nome_campagna=game_state.mission.nome,
                    captain_name="Capitano",
                    ship=game_state.ship,
                    systems=game_state.systems,
                    repair_queue=game_state.repair_queue,
                    difficulty=difficulty,
                    captain_log=game_state.captain_log,
                    stardate=game_state.stardate,
                ))
                logger.info("Partita salvata su richiesta del Capitano")
            except Exception:
                logger.warning("Impossibile salvare stato")
        logger.info("Game loop terminato: uscita volontaria")
        return "QUIT"

    end_reason = check_end_conditions(game_state) or "Partita terminata"
    logger.info("Game loop terminato: %s", end_reason)
    return end_reason
