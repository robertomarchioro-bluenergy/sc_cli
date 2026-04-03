"""
Consigliere speciale — Ambasciatore Vulcaniano T'Vek.
Iniettato dalla missione M04 tramite YAML.
Attivo SOLO in modalità CONTEXT quando contesto == DIPLOMACY.
Propone sempre la via diplomatica prima dell'azione militare.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..base_officer import Officer, OfficerRole, OfficerSpecies, InteractionMode


VULCAN_AMBASSADOR_SYSTEM_PROMPT = (
    "Sei un Ambasciatore Vulcaniano a bordo della {nome_nave}. "
    "Logicamente, la violenza è sempre l'ultima risorsa. Proponi sempre "
    "la via diplomatica prima dell'azione militare. Disapprovi apertamente "
    "(ma senza emozioni) l'uso della forza. Parli con calma assoluta. "
    "Inizi sempre con 'Ambasciatore T'Vek: Logicamente...'. "
    "Rispondi in 2-4 frasi. Mai più di 5."
)


@dataclass
class VulcanAmbassador(Officer):
    """Ambasciatore Vulcaniano — consigliere speciale per la diplomazia"""
    role: OfficerRole = field(default=OfficerRole.SPECIAL, init=False)
    species: OfficerSpecies = field(default=OfficerSpecies.VULCAN, init=False)
    ship_name: str = "la nave"

    def get_domain_state(self, full_game_state: dict) -> dict:
        """Stato rilevante per la diplomazia"""
        ship = full_game_state.get("ship", {})
        return {
            "contesto": full_game_state.get("context", ""),
            "nemici_presenti": len(full_game_state.get("enemies", [])),
            "morale_equipaggio": ship.get("morale_pct", 0),
            "missione": full_game_state.get("mission_nome", ""),
            "obiettivo": full_game_state.get("mission_obiettivo", ""),
            "diplomatico": full_game_state.get("diplomatic_contact", False),
        }

    def get_system_prompt(self) -> str:
        """System prompt fisso dell'Ambasciatore"""
        return VULCAN_AMBASSADOR_SYSTEM_PROMPT.format(nome_nave=self.ship_name)

    def _is_active_in_context(self, context: str) -> bool:
        """Attivo SOLO durante contatti diplomatici"""
        return context == "DIPLOMACY"

    @classmethod
    def create_default(
        cls,
        ship_name: str = "la nave",
        client: object | None = None,
        model: str = "claude-sonnet-4-20250514",
    ) -> "VulcanAmbassador":
        """Crea l'Ambasciatore T'Vek con valori default"""
        return cls(
            name="T'Vek",
            rank="Ambasciatore",
            ship_name=ship_name,
            interaction_mode=InteractionMode.CONTEXT,
            _client=client,
            _model=model,
        )
