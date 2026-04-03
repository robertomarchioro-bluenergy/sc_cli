"""
Diario del Capitano con entry automatiche (Claude API) e manuali.
Le entry automatiche si generano in risposta a eventi significativi.
Il tono varia in base alla classe nave (TOS/TNG/DS9/VOY).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime

from .ship import ShipClass

logger = logging.getLogger(__name__)


class OfficerAPIError(Exception):
    """Errore durante la chiamata all'API Claude per gli ufficiali"""
    pass


class LogEntryType(Enum):
    """Tipo di entry nel diario"""
    AUTO = "AUTO"    # generata da Claude API
    MANUAL = "NOTA"  # scritta dal giocatore con comando "DIARIO: testo"


# Mappa classe nave → stile narrativo per il diario
SHIP_TONE_MAP: dict[ShipClass, str] = {
    ShipClass.CONSTITUTION: "TOS",
    ShipClass.CONSTITUTION_REFIT: "TOS",
    ShipClass.EXCELSIOR: "TOS",
    ShipClass.GALAXY: "TNG",
    ShipClass.SOVEREIGN: "TNG",
    ShipClass.DEFIANT: "DS9",
    ShipClass.INTREPID: "VOY",
}


@dataclass
class LogEntry:
    """Singola entry nel diario del Capitano"""
    stardate: float
    entry_type: LogEntryType
    text: str
    mission_id: str

    def to_dict(self) -> dict:
        return {
            "stardate": self.stardate,
            "entry_type": self.entry_type.value,
            "text": self.text,
            "mission_id": self.mission_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LogEntry":
        return cls(
            stardate=d["stardate"],
            entry_type=LogEntryType(d["entry_type"]),
            text=d["text"],
            mission_id=d["mission_id"],
        )


class CaptainLog:
    """Gestisce il diario del Capitano con entry manuali e automatiche"""

    def __init__(self) -> None:
        self.entries: list[LogEntry] = []

    def add_manual(self, stardate: float, text: str, mission_id: str) -> None:
        """Aggiunge una nota manuale del giocatore"""
        entry = LogEntry(
            stardate=stardate,
            entry_type=LogEntryType.MANUAL,
            text=text,
            mission_id=mission_id,
        )
        self.entries.append(entry)
        logger.info("Diario: nota manuale aggiunta a SD %.1f", stardate)

    def add_auto(
        self,
        stardate: float,
        mission_id: str,
        event: dict,
        ship_name: str,
        ship_class: ShipClass,
        client: object | None,
        model: str,
    ) -> None:
        """
        Genera entry automatica con Claude API.
        Se client è None, non genera nulla.
        """
        if client is None:
            logger.debug("Diario automatico saltato: nessun client API")
            return

        tone = SHIP_TONE_MAP.get(ship_class, "TNG")
        system_prompt = (
            f"Sei il computer di bordo della {ship_name} che registra il diario del Capitano. "
            f"Scrivi in prima persona come il Capitano. Stile: conciso, ufficiale con sfumatura "
            f"personale. Lunghezza: 3-5 frasi. MAI più di 6. MAI elenchi puntati. "
            f"Tono: {tone}. "
            f"Stardate: {stardate}. Nave: {ship_name}. Missione: {mission_id}."
        )

        try:
            response = client.messages.create(
                model=model,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": str(event)}],
            )
            text = response.content[0].text
            entry = LogEntry(
                stardate=stardate,
                entry_type=LogEntryType.AUTO,
                text=text,
                mission_id=mission_id,
            )
            self.entries.append(entry)
            logger.info("Diario: entry automatica generata a SD %.1f", stardate)
        except Exception as e:
            raise OfficerAPIError(f"Errore generazione diario: {e}") from e

    def get_entries(self, mission_id: str | None = None) -> list[LogEntry]:
        """Restituisce le entry, opzionalmente filtrate per missione"""
        if mission_id is None:
            return list(self.entries)
        return [e for e in self.entries if e.mission_id == mission_id]

    def export_to_file(self, ship_name: str, output_dir: str = ".") -> str:
        """
        Esporta il diario in un file di testo.
        Ritorna il percorso del file creato.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = ship_name.replace(" ", "_").replace("/", "_")
        filename = f"captain_log_{safe_name}_{timestamp}.txt"
        filepath = Path(output_dir) / filename

        lines: list[str] = []
        lines.append(f"══════════════════════════════════════════════")
        lines.append(f"  DIARIO DEL CAPITANO — {ship_name}")
        lines.append(f"══════════════════════════════════════════════")
        lines.append("")

        for entry in self.entries:
            type_label = "CAPTAIN'S LOG AUTOMATICO" if entry.entry_type == LogEntryType.AUTO else "NOTA PERSONALE"
            lines.append(f"── {type_label} · SD {entry.stardate:.1f} ── [{entry.mission_id}]")
            lines.append(entry.text)
            lines.append("")

        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Diario esportato: %s", filepath)
        return str(filepath)

    def to_dict(self) -> dict:
        return {"entries": [e.to_dict() for e in self.entries]}

    @classmethod
    def from_dict(cls, d: dict) -> "CaptainLog":
        log = cls()
        log.entries = [LogEntry.from_dict(e) for e in d.get("entries", [])]
        return log


# ── Trigger per entry automatiche ────────────────────────────

class LogTrigger(Enum):
    """Eventi che attivano una entry automatica nel diario"""
    MISSION_START = "inizio_missione"
    MISSION_END = "fine_missione"
    HEAVY_DAMAGE = "danno_grave"           # danno >20% ricevuto o inflitto
    CREW_DEATH = "morte_equipaggio"
    NEW_ENEMY_TYPE = "nuovo_tipo_nemico"
    ANOMALY_DISCOVERED = "scoperta_anomalia"
    PLANET_DISCOVERED = "scoperta_pianeta"
    OFFICER_IGNORED_5X = "ufficiale_ignorato_5_volte"
    VICTORY = "vittoria"
    DEFEAT = "sconfitta"


def check_log_triggers(
    trigger: LogTrigger,
    event_data: dict,
    captain_log: CaptainLog,
    stardate: float,
    mission_id: str,
    ship_name: str,
    ship_class: ShipClass,
    client: object | None,
    model: str,
) -> None:
    """Verifica e attiva trigger per il diario del Capitano"""
    event = {
        "trigger": trigger.value,
        **event_data,
    }
    try:
        captain_log.add_auto(
            stardate=stardate,
            mission_id=mission_id,
            event=event,
            ship_name=ship_name,
            ship_class=ship_class,
            client=client,
            model=model,
        )
    except OfficerAPIError:
        logger.warning("Impossibile generare entry diario per trigger %s", trigger.value)
