"""
Medico di Bordo — empatico, protettivo verso l'equipaggio.
In conflitto con il Tattico sulle perdite accettabili.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .base_officer import Officer, OfficerRole, OfficerSpecies, InteractionMode


@dataclass
class MedicalOfficer(Officer):
    """Medico di Bordo della nave"""
    role: OfficerRole = field(default=OfficerRole.MEDICAL, init=False)
    battle_history: list[dict] = field(default_factory=list)  # ultime 5 battaglie

    def get_domain_state(self, full_game_state: dict) -> dict:
        """Estrae stato rilevante per il dominio medico"""
        ship = full_game_state.get("ship", {})
        systems = full_game_state.get("systems", {})
        sickbay = systems.get("medicina_bordo", {})

        return {
            "equipaggio": ship.get("crew", 0),
            "equipaggio_max": ship.get("crew_max", 0),
            "morale_pct": ship.get("morale_pct", 0),
            "feriti": 0,  # calcolato dal game engine
            "perdite_ultimo_turno": full_game_state.get("crew_casualties_last_turn", 0),
            "sickbay_integrity": sickbay.get("integrity", 100) if isinstance(sickbay, dict) else 100,
            "ultime_5_battaglie": self.battle_history[-5:],
        }

    def get_system_prompt(self) -> str:
        """System prompt del Medico"""
        ship_name = "la nave"
        species_name = self.species.value

        return (
            f"Sei il Medico di Bordo della {ship_name}. Specie: {species_name}. "
            f"Sei empatico e protettivo verso l'equipaggio. Sei spesso in conflitto con "
            f"il Tattico sulle perdite accettabili. Parli di persone, non di statistiche. "
            f"Non usi mai linguaggio militaresco. "
            f"Rispondi in 2-4 frasi. Mai più di 5. Mai elenchi puntati."
        )

    def _is_active_in_context(self, context: str) -> bool:
        """Attivo dopo perdite dell'equipaggio"""
        return context == "AFTER_LOSS"

    def record_battle(self, event: dict) -> None:
        """Registra un evento battaglia per lo storico"""
        self.battle_history.append(event)
        self.battle_history = self.battle_history[-5:]

    @classmethod
    def create_default(
        cls,
        name: str = "Crusher",
        species: OfficerSpecies = OfficerSpecies.HUMAN,
        rank: str = "Comandante",
        interaction_mode: InteractionMode = InteractionMode.CONTEXT,
        client: object | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> "MedicalOfficer":
        """Crea un Medico con valori default"""
        return cls(
            name=name,
            species=species,
            rank=rank,
            interaction_mode=interaction_mode,
            _client=client,
            _model=model,
        )
