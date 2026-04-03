"""
Sistemi di bordo della nave con degrado progressivo.
Ogni sistema ha un'integrità 0-100% e una formula di penalty esponenziale
che riduce gradualmente le prestazioni sotto il 50%.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SystemName(Enum):
    """Nomi dei sistemi di bordo, raggruppati per dominio"""
    # Propulsione (dominio Ingegnere)
    WARP_ENGINES = "motori_warp"
    IMPULSE_ENGINES = "motori_impulso"
    # Combattimento (dominio Tattico)
    TARGETING_COMPUTER = "computer_puntamento"
    SHIELD_GENERATOR = "scudo_deflettore"
    TORPEDO_LAUNCHER = "lanciasiluri"
    # Sensori e comunicazioni (dominio Scientifico)
    SENSORS = "sensori"
    COMMUNICATIONS = "comunicazioni"
    # Supporto vitale (dominio Medico)
    SICKBAY = "medicina_bordo"
    LIFE_SUPPORT = "supporto_vitale"
    BIONUERAL_GEL = "bio_neural_gel"  # solo Intrepid


class SystemStatus(Enum):
    """Stato qualitativo del sistema basato sull'integrità"""
    NOMINAL = "NOMINALE"    # integrità > 50%
    DEGRADED = "DEGRADATO"  # integrità 20-50%
    CRITICAL = "CRITICO"    # integrità 1-19%
    OFFLINE = "OFFLINE"     # integrità 0%


@dataclass
class ShipSystem:
    """Singolo sistema di bordo con stato e formula di degrado"""
    name: SystemName
    integrity: float  # 0.0-100.0

    @property
    def status(self) -> SystemStatus:
        """Stato qualitativo derivato dall'integrità"""
        if self.integrity > 50:
            return SystemStatus.NOMINAL
        if self.integrity > 19:
            return SystemStatus.DEGRADED
        if self.integrity > 0:
            return SystemStatus.CRITICAL
        return SystemStatus.OFFLINE

    @property
    def penalty(self) -> float:
        """
        Formula degrado progressivo (esponente 1.5):
        penalty = ((50 - integrità) / 50) ^ 1.5  se integrità < 50
        penalty = 0                                se integrità >= 50

        Esempi:
          50% → 0.00    40% → 0.09    30% → 0.25
          20% → 0.46    10% → 0.72     0% → 1.00 (OFFLINE)
        """
        if self.integrity >= 50.0:
            return 0.0
        return ((50.0 - self.integrity) / 50.0) ** 1.5

    def apply_damage(self, amount: float) -> None:
        """Applica danno al sistema"""
        self.integrity = max(0.0, self.integrity - amount)

    def repair(self, amount: float) -> None:
        """Ripara il sistema"""
        self.integrity = min(100.0, self.integrity + amount)

    def to_dict(self) -> dict:
        """Serializza il sistema"""
        return {
            "name": self.name.value,
            "integrity": self.integrity,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShipSystem":
        """Deserializza il sistema"""
        return cls(
            name=SystemName(d["name"]),
            integrity=d["integrity"],
        )


@dataclass
class RepairJob:
    """Lavoro di riparazione in coda"""
    system: SystemName
    priority: int      # 1=alta, 2=media, 3=bassa
    progress: float    # 0.0-100.0 (progresso della riparazione corrente)
    eta_stardate: float  # stima completamento in stardate

    def to_dict(self) -> dict:
        return {
            "system": self.system.value,
            "priority": self.priority,
            "progress": self.progress,
            "eta_stardate": self.eta_stardate,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RepairJob":
        return cls(
            system=SystemName(d["system"]),
            priority=d["priority"],
            progress=d["progress"],
            eta_stardate=d["eta_stardate"],
        )


class RepairQueue:
    """
    Coda riparazioni con priorità.
    In porto: tutti i job avanzano in parallelo.
    In missione: solo il job con priority più alta avanza.
    """

    def __init__(self) -> None:
        self.jobs: list[RepairJob] = []

    def add(self, system: SystemName, priority: int, current_stardate: float = 0.0) -> None:
        """Aggiunge un lavoro di riparazione alla coda"""
        # Evita duplicati
        for job in self.jobs:
            if job.system == system:
                job.priority = min(job.priority, priority)
                return
        eta = current_stardate + (3 - priority + 1) * 0.5  # stima basata su priorità
        self.jobs.append(RepairJob(
            system=system,
            priority=priority,
            progress=0.0,
            eta_stardate=eta,
        ))
        self._sort_jobs()

    def remove(self, system: SystemName) -> None:
        """Rimuove un lavoro dalla coda"""
        self.jobs = [j for j in self.jobs if j.system != system]

    def tick(
        self,
        docked: bool,
        repair_speed_modifier: float,
        systems: dict[SystemName, "ShipSystem"],
    ) -> list[str]:
        """
        Avanza le riparazioni di un tick.
        Ritorna lista di messaggi su riparazioni completate.
        """
        if not self.jobs:
            return []

        messages: list[str] = []
        base_repair = 5.0 * repair_speed_modifier  # punti riparazione per tick

        if docked:
            # In porto: tutti i job avanzano in parallelo
            for job in list(self.jobs):
                repair_amount = base_repair * 2.0  # bonus attracco
                if job.system in systems:
                    systems[job.system].repair(repair_amount)
                    job.progress += repair_amount
                    if systems[job.system].integrity >= 100.0:
                        messages.append(
                            f"Riparazione completata: {job.system.value}"
                        )
                        self.remove(job.system)
        else:
            # In missione: solo il job con priority più alta avanza
            if self.jobs:
                job = self.jobs[0]  # già ordinati per priorità
                if job.system in systems:
                    systems[job.system].repair(base_repair)
                    job.progress += base_repair
                    if systems[job.system].integrity >= 100.0:
                        messages.append(
                            f"Riparazione completata: {job.system.value}"
                        )
                        self.remove(job.system)

        return messages

    def _sort_jobs(self) -> None:
        """Ordina per priorità (1=prima)"""
        self.jobs.sort(key=lambda j: j.priority)

    def to_dict(self) -> dict:
        return {"jobs": [j.to_dict() for j in self.jobs]}

    @classmethod
    def from_dict(cls, d: dict) -> "RepairQueue":
        rq = cls()
        rq.jobs = [RepairJob.from_dict(j) for j in d.get("jobs", [])]
        return rq


def create_default_systems(is_intrepid: bool = False) -> dict[SystemName, ShipSystem]:
    """Crea il set completo di sistemi di bordo a integrità nominale"""
    systems: dict[SystemName, ShipSystem] = {}
    for sn in SystemName:
        # Il gel bio-neurale è solo per la classe Intrepid
        if sn == SystemName.BIONUERAL_GEL and not is_intrepid:
            continue
        systems[sn] = ShipSystem(name=sn, integrity=100.0)
    return systems


def systems_to_dict(systems: dict[SystemName, ShipSystem]) -> dict:
    """Serializza tutti i sistemi"""
    return {sn.value: ss.to_dict() for sn, ss in systems.items()}


def systems_from_dict(d: dict) -> dict[SystemName, ShipSystem]:
    """Deserializza tutti i sistemi"""
    result: dict[SystemName, ShipSystem] = {}
    for key, val in d.items():
        ss = ShipSystem.from_dict(val)
        result[ss.name] = ss
    return result
