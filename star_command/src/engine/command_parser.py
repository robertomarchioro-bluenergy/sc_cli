"""
Parser ibrido a due livelli per comandi del Capitano.
Livello 1: pattern matching NLP con regex (italiano/inglese).
Livello 2: fallback menu contestuale quando nessun pattern matcha.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CommandAction(Enum):
    """Azioni riconosciute dal parser"""
    FIRE_PHASER = "fire_phaser"
    FIRE_TORPEDO = "fire_torpedo"
    NAVIGATE_WARP = "navigate_warp"
    NAVIGATE_IMPULSE = "navigate_impulse"
    SCAN = "scan"
    SHIELDS_MAX = "shields_max"
    SHIELDS_SET = "shields_set"
    SHOW_MAP = "show_map"
    SHOW_STATUS = "show_status"
    SHOW_SYSTEMS = "show_systems"
    SHOW_CAPTAIN_LOG = "show_captain_log"
    SHOW_MISSION = "show_mission"
    SHOW_MENU = "show_menu"
    DOCK_STARBASE = "dock_starbase"
    REPAIR_SYSTEM = "repair_system"
    OFFICER_TACTICAL = "officer_tactical"
    OFFICER_ENGINEER = "officer_engineer"
    OFFICER_SCIENCE = "officer_science"
    OFFICER_MEDICAL = "officer_medical"
    OFFICER_SPECIAL = "officer_special"
    ACKNOWLEDGE_OFFICER = "acknowledge_officer"
    CREW_MEETING = "crew_meeting"
    CAPTAIN_LOG_MANUAL = "captain_log_manual"
    EXPORT_LOG = "export_log"
    QUIT = "quit"
    SAVE_AND_QUIT = "save_and_quit"
    UNKNOWN = "unknown"


# Azioni che richiedono conferma [S/N]
CONFIRM_REQUIRED: set[CommandAction] = {
    CommandAction.FIRE_TORPEDO,
    CommandAction.CREW_MEETING,
    CommandAction.QUIT,
}


@dataclass
class ParsedCommand:
    """Risultato del parsing di un comando"""
    action: CommandAction
    params: dict[str, Any]
    raw_text: str
    confidence: float  # 1.0=match diretto, 0.0=fallback menu


# Pattern ordinati per priorità (il primo match vince)
PATTERNS: list[tuple[str, CommandAction]] = [
    (r"(fuoco|spara|fire).*(silur|torpedo)", CommandAction.FIRE_TORPEDO),
    (r"(fuoco|spara|fire).*(faser|phaser)", CommandAction.FIRE_PHASER),
    (r"warp\s*(\d)", CommandAction.NAVIGATE_WARP),
    (r"(impulso|impulse|subwarp)", CommandAction.NAVIGATE_IMPULSE),
    (r"(scan|scansion|analizza\s+settore)", CommandAction.SCAN),
    (r"(scudi|shield).*(mass|max|pieno|full)", CommandAction.SHIELDS_MAX),
    (r"(scudi|shield)\s*(\d+)", CommandAction.SHIELDS_SET),
    (r"(mappa|map|galassia|galaxy)", CommandAction.SHOW_MAP),
    (r"(stato\s+nave|ship\s+status|status)", CommandAction.SHOW_STATUS),
    (r"(sistemi|systems|diagnostica)", CommandAction.SHOW_SYSTEMS),
    (r"(diario|captain.s\s*log)\s*:\s*(.+)", CommandAction.CAPTAIN_LOG_MANUAL),
    (r"(diario|captain.s\s*log)", CommandAction.SHOW_CAPTAIN_LOG),
    (r"(esporta\s+diario|export\s+log)", CommandAction.EXPORT_LOG),
    (r"(dock|attracco|base\s+stellare)", CommandAction.DOCK_STARBASE),
    (r"(ripara|repair)\s+(\w+)", CommandAction.REPAIR_SYSTEM),
    (r"(rapporto|report|analiz).*(tattic|armi|weapon)", CommandAction.OFFICER_TACTICAL),
    (r"(rapporto|report|analiz).*(ingegn|engineer)", CommandAction.OFFICER_ENGINEER),
    (r"(rapporto|report|analiz).*(scien|science)", CommandAction.OFFICER_SCIENCE),
    (r"(rapporto|report|analiz).*(medic|doctor|doc)", CommandAction.OFFICER_MEDICAL),
    (r"(riconosc|ringrazi|acknowledge)\s+(\w+)", CommandAction.ACKNOWLEDGE_OFFICER),
    (r"(riunione|meeting).*(equipaggio|crew)", CommandAction.CREW_MEETING),
    (r"(missione|mission|obiettiv)", CommandAction.SHOW_MISSION),
    (r"(salva\s*(e|ed)?\s*(esci|quit)|save\s*(and|&)?\s*quit)", CommandAction.SAVE_AND_QUIT),
    (r"(esci|quit|exit|fine\s+partita|abbandona)", CommandAction.QUIT),
    (r"\?", CommandAction.SHOW_MENU),
]


def parse(raw_text: str) -> ParsedCommand:
    """
    Analizza il testo grezzo del Capitano e restituisce il comando strutturato.
    Livello 1: regex pattern matching.
    Livello 2: se nessun match → UNKNOWN con confidence 0.0.
    """
    text = raw_text.strip().lower()
    if not text:
        return ParsedCommand(
            action=CommandAction.SHOW_MENU,
            params={},
            raw_text=raw_text,
            confidence=0.0,
        )

    for pattern_str, action in PATTERNS:
        match = re.search(pattern_str, text, re.IGNORECASE)
        if match:
            params = _extract_params(action, match, raw_text)
            return ParsedCommand(
                action=action,
                params=params,
                raw_text=raw_text,
                confidence=1.0,
            )

    # Nessun match — fallback
    return ParsedCommand(
        action=CommandAction.UNKNOWN,
        params={},
        raw_text=raw_text,
        confidence=0.0,
    )


def _extract_params(
    action: CommandAction,
    match: re.Match,
    raw_text: str,
) -> dict[str, Any]:
    """Estrae parametri dal match regex in base al tipo di azione"""
    params: dict[str, Any] = {}

    if action == CommandAction.NAVIGATE_WARP:
        groups = match.groups()
        for g in groups:
            if g and g.isdigit():
                params["speed"] = int(g)
                break

    elif action == CommandAction.SHIELDS_SET:
        groups = match.groups()
        for g in groups:
            if g and g.isdigit():
                params["level"] = int(g)
                break

    elif action == CommandAction.CAPTAIN_LOG_MANUAL:
        # Estrai il testo dopo ":"
        colon_match = re.search(r":\s*(.+)", raw_text, re.IGNORECASE)
        if colon_match:
            params["text"] = colon_match.group(1).strip()

    elif action == CommandAction.REPAIR_SYSTEM:
        groups = match.groups()
        if len(groups) >= 2 and groups[1]:
            params["system"] = groups[1]

    elif action == CommandAction.ACKNOWLEDGE_OFFICER:
        groups = match.groups()
        if len(groups) >= 2 and groups[1]:
            params["officer"] = groups[1]

    elif action in (CommandAction.FIRE_PHASER, CommandAction.FIRE_TORPEDO):
        # Cerca coordinate target o energia
        num_match = re.findall(r"\d+", raw_text)
        if num_match:
            if action == CommandAction.FIRE_PHASER:
                params["energy"] = int(num_match[-1])
            else:
                # Per siluri, cerca coordinate 4-cifre
                for n in num_match:
                    if len(n) == 4:
                        params["target"] = n
                        break

    elif action == CommandAction.NAVIGATE_IMPULSE:
        # Cerca coordinate settore
        num_match = re.findall(r"\d+", raw_text)
        if len(num_match) >= 2:
            params["s_row"] = int(num_match[0])
            params["s_col"] = int(num_match[1])

    return params


def needs_confirmation(action: CommandAction) -> bool:
    """Verifica se un'azione richiede conferma [S/N]"""
    return action in CONFIRM_REQUIRED


# ── Menu contestuali ────────────────────────────────────────

CONTEXT_MENUS: dict[str, list[tuple[str, str]]] = {
    "COMBAT": [
        ("spara faser [energia]", "Colpo faser con energia specificata"),
        ("spara siluro [coord]", "Lancia siluro fotone"),
        ("scudi max", "Scudi al massimo"),
        ("scudi [%]", "Imposta livello scudi"),
        ("rapporto tattico", "Consulta Ufficiale Tattico"),
        ("stato nave", "Mostra stato completo"),
        ("sistemi", "Mostra sistemi di bordo"),
    ],
    "NAVIGATION": [
        ("warp [velocità]", "Viaggio warp verso destinazione"),
        ("impulso [r] [c]", "Movimento impulso nel quadrante"),
        ("scan", "Scansione settore/quadrante"),
        ("mappa", "Mostra mappa galattica"),
        ("stato nave", "Mostra stato completo"),
        ("rapporto scientifico", "Consulta Ufficiale Scientifico"),
        ("rapporto ingegnere", "Consulta Ingegnere Capo"),
    ],
    "DOCKED": [
        ("ripara [sistema]", "Avvia riparazione sistema"),
        ("rapporto ingegnere", "Consulta Ingegnere Capo"),
        ("rapporto medico", "Consulta Medico di Bordo"),
        ("stato nave", "Mostra stato completo"),
        ("sistemi", "Diagnostica sistemi"),
        ("warp [velocità]", "Lascia base e viaggia"),
        ("missione", "Mostra obiettivi missione"),
    ],
    "EXPLORATION": [
        ("scan", "Scansione anomalia/settore"),
        ("rapporto scientifico", "Consulta Ufficiale Scientifico"),
        ("impulso [r] [c]", "Movimento impulso"),
        ("mappa", "Mostra mappa galattica"),
        ("diario: [testo]", "Aggiungi nota al diario"),
    ],
    "DIPLOMACY": [
        ("rapporto tattico", "Consulta Ufficiale Tattico"),
        ("rapporto scientifico", "Consulta Ufficiale Scientifico"),
        ("riunione equipaggio", "Convoca riunione di bordo"),
        ("missione", "Mostra obiettivi missione"),
        ("diario: [testo]", "Aggiungi nota al diario"),
    ],
}


def get_contextual_menu(context: str) -> list[tuple[str, str]]:
    """Restituisce il menu per il contesto corrente"""
    base_menu = CONTEXT_MENUS.get(context, CONTEXT_MENUS["NAVIGATION"])
    # Comandi universali sempre disponibili
    universal = [
        ("diario", "Mostra diario del Capitano"),
        ("missione", "Mostra obiettivi missione"),
        ("salva e esci", "Salva partita e torna al menu"),
        ("esci", "Abbandona partita (senza salvare)"),
        ("?", "Mostra questo menu"),
    ]
    return base_menu + universal
