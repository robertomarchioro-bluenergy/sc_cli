"""
Ufficiale Tattico — esperto di combattimento e armi.
Diretto, militaresco. Se Klingon: aggressivo e contrario alla ritirata.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .base_officer import Officer, OfficerRole, OfficerSpecies, InteractionMode


@dataclass
class TacticalOfficer(Officer):
    """Ufficiale Tattico della nave"""
    role: OfficerRole = field(default=OfficerRole.TACTICAL, init=False)

    def get_domain_state(self, full_game_state: dict) -> dict:
        """Estrae stato rilevante per il dominio tattico"""
        ship = full_game_state.get("ship", {})
        systems = full_game_state.get("systems", {})
        enemies = full_game_state.get("enemies", [])

        # Calcola distanza dal primo nemico (se presente)
        distanza_nemico = 0.0
        scudi_nemico_pct = 0.0
        if enemies:
            distanza_nemico = 3.0  # placeholder — calcolata dal game_loop
            scudi_nemico_pct = enemies[0].get("shields_pct", 100.0)

        targeting = systems.get("computer_puntamento", {})

        return {
            "distanza_nemico": distanza_nemico,
            "scudi_propri_pct": ship.get("shields_pct", 0),
            "scudi_nemico_pct": scudi_nemico_pct,
            "energia_disponibile": ship.get("energy", 0),
            "siluri_rimasti": ship.get("torpedoes", 0),
            "targeting_computer_integrity": targeting.get("integrity", 100),
            "morale_pct": ship.get("morale_pct", 0),
            "nemici_in_settore": len(enemies),
        }

    def get_system_prompt(self) -> str:
        """System prompt del Tattico"""
        ship_name = "la nave"  # verrà sovrascritto dal contesto
        species_name = self.species.value

        prompt = (
            f"Sei l'Ufficiale Tattico della {ship_name}. Specie: {species_name}. "
            f"Parli in modo diretto e militaresco. Valuti ogni situazione in termini di "
            f"probabilità di vittoria e rischio operativo. Tendi a preferire l'offensiva "
            f"e a sottovalutare il costo energetico. "
        )
        if self.species == OfficerSpecies.KLINGON:
            prompt += (
                "Se sei Klingon dici 'QAPLA'' quando approvi una decisione aggressiva "
                "e rifiuti categoricamente di suggerire ritirate. "
            )
        prompt += "Rispondi in 2-4 frasi. Mai più di 5. Mai elenchi puntati."
        return prompt

    def _is_active_in_context(self, context: str) -> bool:
        """Attivo durante il combattimento"""
        return context == "COMBAT"

    @classmethod
    def create_default(
        cls,
        name: str = "Worf",
        species: OfficerSpecies = OfficerSpecies.KLINGON,
        rank: str = "Tenente Comandante",
        interaction_mode: InteractionMode = InteractionMode.CONTEXT,
        client: object | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> "TacticalOfficer":
        """Crea un Tattico con valori default"""
        return cls(
            name=name,
            species=species,
            rank=rank,
            interaction_mode=interaction_mode,
            _client=client,
            _model=model,
        )
