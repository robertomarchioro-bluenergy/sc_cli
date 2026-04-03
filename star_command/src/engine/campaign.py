"""
Gestore campagna: carica missioni da YAML, gestisce il flusso tra missioni,
la persistenza dello stato e il rifornimento parziale tra missioni.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .difficulty import DifficultyConfig, DifficultyPreset
from .galaxy import Galaxy
from .ship import Ship, ShipClass
from .systems import (
    ShipSystem, SystemName, RepairQueue,
    create_default_systems, systems_to_dict, systems_from_dict,
)
from .captain_log import CaptainLog

logger = logging.getLogger(__name__)


class CampaignLoadError(Exception):
    """Errore nel caricamento della campagna da file YAML"""
    pass


@dataclass
class MissionObjective:
    """Singolo obiettivo di una missione"""
    tipo: str
    specie: str = ""
    quantita: int = 0
    bersaglio: str = ""
    destinazione: str = ""
    completed: bool = False

    def to_dict(self) -> dict:
        return {
            "tipo": self.tipo,
            "specie": self.specie,
            "quantita": self.quantita,
            "bersaglio": self.bersaglio,
            "destinazione": self.destinazione,
            "completed": self.completed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MissionObjective":
        return cls(
            tipo=d.get("tipo", ""),
            specie=d.get("specie", ""),
            quantita=d.get("quantita", 0),
            bersaglio=d.get("bersaglio", ""),
            destinazione=d.get("destinazione", ""),
            completed=d.get("completed", False),
        )


@dataclass
class AlternativeVictory:
    """Condizione di vittoria alternativa per una missione"""
    tipo: str
    condizione: str
    bonus: str

    def to_dict(self) -> dict:
        return {"tipo": self.tipo, "condizione": self.condizione, "bonus": self.bonus}

    @classmethod
    def from_dict(cls, d: dict) -> "AlternativeVictory":
        return cls(tipo=d["tipo"], condizione=d["condizione"], bonus=d["bonus"])


@dataclass
class MissionConfig:
    """Configurazione di una singola missione caricata da YAML"""
    id: str
    nome: str
    descrizione_narrativa: str
    obiettivo_testo: str
    obiettivi: list[MissionObjective]
    deadline_stardate: float
    nemici: list[dict]
    basi_stellari: int
    seed_galassia: int
    consiglieri_speciali: list[str]
    silenti_eventi: list[dict]
    vittoria_alternativa: AlternativeVictory | None = None
    prerequisito: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "descrizione_narrativa": self.descrizione_narrativa,
            "obiettivo_testo": self.obiettivo_testo,
            "obiettivi": [o.to_dict() for o in self.obiettivi],
            "deadline_stardate": self.deadline_stardate,
            "nemici": self.nemici,
            "basi_stellari": self.basi_stellari,
            "seed_galassia": self.seed_galassia,
            "consiglieri_speciali": self.consiglieri_speciali,
            "silenti_eventi": self.silenti_eventi,
            "vittoria_alternativa": self.vittoria_alternativa.to_dict() if self.vittoria_alternativa else None,
            "prerequisito": self.prerequisito,
        }


@dataclass
class CampaignState:
    """Stato persistente della campagna tra missioni"""
    nome_campagna: str
    captain_name: str
    ship: Ship
    systems: dict[SystemName, ShipSystem]
    repair_queue: RepairQueue
    difficulty: DifficultyConfig
    captain_log: CaptainLog
    current_mission_index: int = 0
    stardate: float = 2347.1
    missions_completed: list[str] = field(default_factory=list)
    officers_state: dict = field(default_factory=dict)  # serializzato dagli ufficiali
    galaxy: Galaxy | None = None

    def to_dict(self) -> dict:
        return {
            "nome_campagna": self.nome_campagna,
            "captain_name": self.captain_name,
            "ship": self.ship.to_dict(),
            "systems": systems_to_dict(self.systems),
            "repair_queue": self.repair_queue.to_dict(),
            "difficulty": self.difficulty.to_dict(),
            "captain_log": self.captain_log.to_dict(),
            "current_mission_index": self.current_mission_index,
            "stardate": self.stardate,
            "missions_completed": self.missions_completed,
            "officers_state": self.officers_state,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CampaignState":
        return cls(
            nome_campagna=d["nome_campagna"],
            captain_name=d["captain_name"],
            ship=Ship.from_dict(d["ship"]),
            systems=systems_from_dict(d["systems"]),
            repair_queue=RepairQueue.from_dict(d["repair_queue"]),
            difficulty=DifficultyConfig.from_dict(d["difficulty"]),
            captain_log=CaptainLog.from_dict(d["captain_log"]),
            current_mission_index=d.get("current_mission_index", 0),
            stardate=d.get("stardate", 2347.1),
            missions_completed=d.get("missions_completed", []),
            officers_state=d.get("officers_state", {}),
        )


class Campaign:
    """Gestore della campagna: caricamento YAML, flusso missioni, persistenza"""

    def __init__(self) -> None:
        self.nome: str = ""
        self.descrizione: str = ""
        self.stardate_inizio: float = 2347.1
        self.difficolta_default: DifficultyPreset = DifficultyPreset.NORMAL
        self.nave_suggerita: ShipClass = ShipClass.CONSTITUTION
        self.missions: list[MissionConfig] = []

    def load_from_yaml(self, filepath: str) -> None:
        """Carica la campagna da file YAML"""
        path = Path(filepath)
        if not path.exists():
            raise CampaignLoadError(f"File campagna non trovato: {filepath}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise CampaignLoadError(f"Errore parsing YAML: {e}") from e

        camp_data = data.get("campagna", {})
        self.nome = camp_data.get("nome", "Campagna Senza Nome")
        self.descrizione = camp_data.get("descrizione", "")
        self.stardate_inizio = camp_data.get("stardate_inizio", 2347.1)

        # Difficoltà default
        diff_str = camp_data.get("difficolta_default", "NORMAL")
        try:
            self.difficolta_default = DifficultyPreset[diff_str]
        except KeyError:
            self.difficolta_default = DifficultyPreset.NORMAL

        # Nave suggerita
        nave_str = camp_data.get("nave_suggerita", "Constitution")
        try:
            self.nave_suggerita = ShipClass(nave_str)
        except ValueError:
            self.nave_suggerita = ShipClass.CONSTITUTION

        # Missioni
        self.missions = []
        for m_data in camp_data.get("missioni", []):
            objectives = []
            for obj in m_data.get("obiettivi", []):
                objectives.append(MissionObjective(
                    tipo=obj.get("tipo", ""),
                    specie=obj.get("specie", ""),
                    quantita=obj.get("quantita", 0),
                    bersaglio=obj.get("bersaglio", ""),
                    destinazione=obj.get("destinazione", ""),
                ))

            alt_victory = None
            alt_data = m_data.get("vittoria_alternativa")
            if alt_data:
                alt_victory = AlternativeVictory(
                    tipo=alt_data.get("tipo", ""),
                    condizione=alt_data.get("condizione", ""),
                    bonus=alt_data.get("bonus", ""),
                )

            mission = MissionConfig(
                id=m_data.get("id", ""),
                nome=m_data.get("nome", ""),
                descrizione_narrativa=m_data.get("descrizione_narrativa", ""),
                obiettivo_testo=m_data.get("obiettivo_testo", ""),
                obiettivi=objectives,
                deadline_stardate=m_data.get("deadline_stardate", 0.0),
                nemici=m_data.get("nemici", []),
                basi_stellari=m_data.get("basi_stellari", 0),
                seed_galassia=m_data.get("seed_galassia", 0),
                consiglieri_speciali=m_data.get("consiglieri_speciali", []),
                silenti_eventi=m_data.get("silenti_eventi", []),
                vittoria_alternativa=alt_victory,
                prerequisito=m_data.get("prerequisito"),
            )
            self.missions.append(mission)

        logger.info("Campagna caricata: '%s' con %d missioni", self.nome, len(self.missions))

    def get_mission(self, index: int) -> MissionConfig | None:
        """Restituisce la missione all'indice specificato"""
        if 0 <= index < len(self.missions):
            return self.missions[index]
        return None

    def get_next_mission(self, completed: list[str]) -> MissionConfig | None:
        """Restituisce la prossima missione disponibile considerando i prerequisiti"""
        for mission in self.missions:
            if mission.id in completed:
                continue
            if mission.prerequisito:
                prereq_mission_id = mission.prerequisito.replace("_completata", "")
                if prereq_mission_id not in completed:
                    continue
            return mission
        return None

    def apply_between_mission_resupply(self, state: CampaignState) -> list[str]:
        """
        Rifornimento parziale tra missioni (in porto a fine missione).
        Restituisce lista di messaggi su cosa è stato rifornito.
        """
        messages: list[str] = []
        ship = state.ship

        # Energia: +60% del massimo di classe
        energy_gain = ship.energy_max * 0.60
        old_energy = ship.energy
        ship.energy = min(ship.energy_max, ship.energy + energy_gain)
        if ship.energy > old_energy:
            messages.append(f"Energia rifornita: {old_energy:.0f} → {ship.energy:.0f}")

        # Dilithium: +30% del massimo di classe
        dilithium_gain = int(ship.dilithium_max * 0.30)
        old_dilithium = ship.dilithium
        ship.dilithium = min(ship.dilithium_max, ship.dilithium + dilithium_gain)
        if ship.dilithium > old_dilithium:
            messages.append(f"Dilithium rifornito: {old_dilithium} → {ship.dilithium}")

        # Siluri: nessun rifornimento
        messages.append("Siluri: nessun rifornimento disponibile")

        # Morale: +10 punti fissi (cap 100)
        old_morale = ship.morale_pct
        ship.adjust_morale(10.0)
        if ship.morale_pct > old_morale:
            messages.append(f"Morale: {old_morale:.0f}% → {ship.morale_pct:.0f}%")

        # Sistemi sotto 70%: riparati a 70%
        for sys_name, system in state.systems.items():
            if system.integrity < 70.0:
                old_int = system.integrity
                repair_target = 70.0 * state.difficulty.repair_speed
                system.integrity = min(100.0, max(system.integrity, repair_target))
                messages.append(
                    f"Sistema {sys_name.value}: {old_int:.0f}% → {system.integrity:.0f}%"
                )

        logger.info("Rifornimento tra missioni completato")
        return messages


# ── Salvataggio / Caricamento su disco ────────────────────────

SAVE_DIR = Path("saves")


def save_campaign_state(state: CampaignState, slot: str = "autosave") -> str:
    """Salva lo stato della campagna su disco in formato JSON"""
    SAVE_DIR.mkdir(exist_ok=True)
    filepath = SAVE_DIR / f"{slot}.json"
    data = state.to_dict()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Stato campagna salvato: %s", filepath)
    return str(filepath)


def load_campaign_state(slot: str = "autosave") -> CampaignState | None:
    """Carica lo stato della campagna da disco"""
    filepath = SAVE_DIR / f"{slot}.json"
    if not filepath.exists():
        logger.warning("File salvataggio non trovato: %s", filepath)
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Stato campagna caricato: %s", filepath)
    return CampaignState.from_dict(data)
