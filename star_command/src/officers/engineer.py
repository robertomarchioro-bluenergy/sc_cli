"""
Chief Engineer — esperto di sistemi nave, propulsione e riparazioni.
Burbero, pragmatico. Sovrastima i danni per sicurezza.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .base_officer import Officer, OfficerRole, OfficerSpecies, InteractionMode


@dataclass
class EngineerOfficer(Officer):
    """Ingegnere Capo della nave"""
    role: OfficerRole = field(default=OfficerRole.ENGINEER, init=False)

    def get_domain_state(self, full_game_state: dict) -> dict:
        """Estrae stato rilevante per il dominio ingegneristico"""
        ship = full_game_state.get("ship", {})
        systems = full_game_state.get("systems", {})

        # Integrità di tutti i sistemi
        sistemi_integrita: dict[str, float] = {}
        for nome_sys, sys_data in systems.items():
            if isinstance(sys_data, dict):
                sistemi_integrita[nome_sys] = sys_data.get("integrity", 100.0)
            else:
                sistemi_integrita[nome_sys] = 100.0

        return {
            "energia": ship.get("energy", 0),
            "energia_max": ship.get("energy_max", 0),
            "dilithium": ship.get("dilithium", 0),
            "dilithium_max": ship.get("dilithium_max", 0),
            "tutti_sistemi_integrita": sistemi_integrita,
            "scafo_pct": ship.get("hull_pct", 100),
            "docked": full_game_state.get("docked", False),
        }

    def get_system_prompt(self) -> str:
        """System prompt dell'Ingegnere"""
        ship_name = "la nave"
        species_name = self.species.value

        return (
            f"Sei il Chief Engineer della {ship_name}. Specie: {species_name}. "
            f"Parli in modo burbero e pragmatico. Sei sempre preoccupato per i sistemi. "
            f"Sovrastimi i danni per sicurezza e chiedi più tempo del necessario. "
            f"Dai priorità alla sopravvivenza della nave rispetto all'offensiva. "
            f"Usi termini tecnici senza spiegarli. "
            f"Rispondi in 2-4 frasi. Mai più di 5. Mai elenchi puntati."
        )

    def _is_active_in_context(self, context: str) -> bool:
        """Attivo quando attraccati o dopo danni ai sistemi"""
        return context == "DOCKED"

    @classmethod
    def create_default(
        cls,
        name: str = "Scott",
        species: OfficerSpecies = OfficerSpecies.HUMAN,
        rank: str = "Tenente Comandante",
        interaction_mode: InteractionMode = InteractionMode.CONTEXT,
        client: object | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> "EngineerOfficer":
        """Crea un Ingegnere con valori default"""
        return cls(
            name=name,
            species=species,
            rank=rank,
            interaction_mode=interaction_mode,
            _client=client,
            _model=model,
        )
