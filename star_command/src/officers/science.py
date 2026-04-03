"""
Ufficiale Scientifico — analitico, metodico, vuole più dati.
Se Vulcaniano: inizia con 'Logicamente...' o 'I dati indicano...'.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .base_officer import Officer, OfficerRole, OfficerSpecies, InteractionMode


@dataclass
class ScienceOfficer(Officer):
    """Ufficiale Scientifico della nave"""
    role: OfficerRole = field(default=OfficerRole.SCIENCE, init=False)

    def get_domain_state(self, full_game_state: dict) -> dict:
        """Estrae stato rilevante per il dominio scientifico"""
        systems = full_game_state.get("systems", {})
        sensori = systems.get("sensori", {})

        return {
            "sensori_integrity": sensori.get("integrity", 100) if isinstance(sensori, dict) else 100,
            "anomalie_rilevate": full_game_state.get("anomaly_detected", False),
            "entita_identificate": len(full_game_state.get("enemies", [])),
            "posizioni_note": [],  # popolato dal galaxy state
            "nebule_vicine": False,
            "quadranti_scansionati": 0,
        }

    def get_system_prompt(self) -> str:
        """System prompt dello Scientifico"""
        ship_name = "la nave"
        species_name = self.species.value

        prompt = (
            f"Sei l'Ufficiale Scientifico della {ship_name}. Specie: {species_name}. "
            f"Sei analitico e metodico. Vuoi sempre più dati prima di agire, anche in urgenza. "
            f"Non hai senso dell'urgenza tattica. Descrivi fatti, non opinioni. "
        )
        if self.species == OfficerSpecies.VULCAN:
            prompt += "Inizia la risposta con 'Logicamente...' o 'I dati indicano...'. "
        prompt += "Rispondi in 2-4 frasi tecniche e precise. Mai più di 5. Mai elenchi puntati."
        return prompt

    def _is_active_in_context(self, context: str) -> bool:
        """Attivo durante navigazione e esplorazione"""
        return context in ("NAVIGATION", "EXPLORATION")

    @classmethod
    def create_default(
        cls,
        name: str = "T'Pol",
        species: OfficerSpecies = OfficerSpecies.VULCAN,
        rank: str = "Comandante",
        interaction_mode: InteractionMode = InteractionMode.CONTEXT,
        client: object | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> "ScienceOfficer":
        """Crea uno Scientifico con valori default"""
        return cls(
            name=name,
            species=species,
            rank=rank,
            interaction_mode=interaction_mode,
            _client=client,
            _model=model,
        )
