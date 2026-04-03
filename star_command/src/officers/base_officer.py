"""
Classe base astratta per tutti gli ufficiali AI.
Gestisce trust, morale, interazione con Claude API e modalità risposta.
Riceve SOLO dict serializzati, mai oggetti engine.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OfficerAPIError(Exception):
    """Errore durante la chiamata all'API Claude per gli ufficiali"""
    pass


class OfficerRole(Enum):
    """Ruoli disponibili per gli ufficiali"""
    TACTICAL = "tattico"
    ENGINEER = "ingegnere"
    SCIENCE = "scientifico"
    MEDICAL = "medico"
    SPECIAL = "speciale"


class OfficerSpecies(Enum):
    """Specie disponibili per gli ufficiali"""
    HUMAN = "Umano"
    VULCAN = "Vulcaniano"
    KLINGON = "Klingon"
    BETAZOID = "Betazoide"
    ANDORIAN = "Andoriano"
    BAJORAN = "Bajoriano"
    TRILL = "Trill"
    FERENGI = "Ferengi"


class InteractionMode(Enum):
    """Modalità di interazione degli ufficiali"""
    BRIDGE_ACTIVE = "BRIDGE_ACTIVE"    # commenta ogni turno
    ON_CALL = "ON_CALL"                # solo se chiamato esplicitamente
    EMERGENCY_ONLY = "EMERGENCY_ONLY"  # solo se risorsa < 20% o situazione critica
    CONTEXT = "CONTEXT"                # automatico per contesto (default)


# Bonus meccanici per specie
SPECIES_BONUSES: dict[OfficerSpecies, dict[str, float]] = {
    OfficerSpecies.HUMAN: {
        "all_modifier_new_situations": 1.05,  # +5% in situazioni nuove
    },
    OfficerSpecies.VULCAN: {
        "scan_bonus": 1.20,          # +20% scan
        "targeting_bonus": 1.15,     # +15% targeting computer
        "morale_recovery": 0.80,     # -20% recupero morale altrui
    },
    OfficerSpecies.KLINGON: {
        "combat_damage": 1.25,       # +25% danno combattimento
        "battle_morale": 1.0,        # no -morale in battaglia
        "refuses_retreat": True,     # rifiuta SEMPRE di suggerire ritirata
    },
    OfficerSpecies.BETAZOID: {
        "morale_recovery": 1.30,     # +30% recupero morale equipaggio
        "detect_deception": True,    # rileva inganni
        "combat_modifier": 0.90,     # -10% combat
    },
    OfficerSpecies.ANDORIAN: {
        "positional_tactics": 1.15,  # +15% tattica posizionale
        "evasive_maneuvers": 1.10,   # +10% manovre evasive
        "diplomacy": 0.90,           # -10% diplomazia
    },
    OfficerSpecies.BAJORAN: {
        "morale_resilience": 1.15,   # +15% resilienza morale
        "advanced_tech": 0.95,       # -5% tecnologia avanzata
    },
    OfficerSpecies.TRILL: {
        "all_modifier": 1.10,        # +10% a TUTTI i modifier
    },
    OfficerSpecies.FERENGI: {
        "negotiate_supplies": True,  # negozia rifornimenti
        "trade_routes": True,        # conosce rotte commerciali
        "personal_profit": True,     # priorità profitto personale
    },
}


@dataclass
class AdviceRecord:
    """Registra il consiglio dato dall'ufficiale per tracciare se è stato seguito"""
    officer_role: OfficerRole
    advice_text: str
    action_suggested: str     # es. "FIRE_PHASER", "SHIELDS_MAX"
    turn_number: int
    followed: bool = False    # aggiornato dal game_loop dopo l'azione del Capitano

    def to_dict(self) -> dict:
        return {
            "officer_role": self.officer_role.value,
            "advice_text": self.advice_text,
            "action_suggested": self.action_suggested,
            "turn_number": self.turn_number,
            "followed": self.followed,
        }


@dataclass
class Officer(ABC):
    """Classe base astratta per tutti gli ufficiali AI"""
    name: str
    species: OfficerSpecies
    role: OfficerRole
    rank: str
    trust: float = 75.0
    trust_history: list[int] = field(default_factory=list)  # finestra scorrevole 10
    personal_morale: float = 85.0
    interaction_mode: InteractionMode = InteractionMode.CONTEXT
    _client: object | None = field(default=None, repr=False)
    _model: str = "claude-sonnet-4-20250514"

    def update_trust(self, advice_followed: bool) -> None:
        """
        +2 se consiglio seguito, -1 se ignorato.
        Se ignorato 5 volte consecutive: personal_morale -10.
        """
        delta = 2 if advice_followed else -1
        self.trust = max(0.0, min(100.0, self.trust + delta))
        self.trust_history.append(1 if advice_followed else -1)
        self.trust_history = self.trust_history[-10:]
        # Verifica 5 ignore consecutivi
        if len(self.trust_history) >= 5 and self.trust_history[-5:] == [-1, -1, -1, -1, -1]:
            self.personal_morale = max(0.0, self.personal_morale - 10.0)
            logger.info(
                "Ufficiale %s: morale personale sceso a %.0f (5 consigli ignorati)",
                self.name, self.personal_morale,
            )

    def get_bonus_multiplier(self) -> float:
        """Riduce i bonus in base al personal_morale"""
        if self.personal_morale >= 80:
            return 1.0
        if self.personal_morale >= 50:
            return 1.0
        if self.personal_morale >= 20:
            return 0.5
        return 0.0  # ufficiale silenzioso, nessun bonus

    @abstractmethod
    def get_domain_state(self, full_game_state: dict) -> dict:
        """Estrae solo il sottoinsieme di stato pertinente al ruolo"""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Restituisce il system prompt specifico per il ruolo"""
        pass

    def should_respond(self, context: str, trigger: str) -> bool:
        """Determina se l'ufficiale deve rispondere in base alla modalità e al contesto"""
        if trigger == "called":
            return True
        if trigger == "emergency" and self.interaction_mode == InteractionMode.EMERGENCY_ONLY:
            return True
        if self.interaction_mode == InteractionMode.BRIDGE_ACTIVE:
            return True
        if self.interaction_mode == InteractionMode.CONTEXT:
            return self._is_active_in_context(context)
        return False

    @abstractmethod
    def _is_active_in_context(self, context: str) -> bool:
        """True se questo ufficiale è quello 'di turno' nel contesto corrente"""
        pass

    def respond(self, full_game_state: dict, trigger: str = "auto") -> str | None:
        """
        Chiama Claude API con il domain_state. Restituisce None se non deve rispondere.
        Se _client è None (no API key): restituisce None con log warning.
        """
        if self._client is None:
            logger.debug("Ufficiale %s: nessun client API, risposta saltata", self.name)
            return None
        context = full_game_state.get("context", "")
        if not self.should_respond(context, trigger):
            return None

        domain_state = self.get_domain_state(full_game_state)
        bonus = self.get_bonus_multiplier()

        # Costruisci system prompt con modifiche morale
        system = self.get_system_prompt()
        if bonus < 1.0 and bonus > 0.0:
            system += "\nSei demoralizzato. Rispondi in modo distaccato e sintetico."
        if bonus == 0.0:
            system += "\nRispondi solo con pochissime parole, quasi in silenzio."

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=300,
                system=system,
                messages=[{"role": "user", "content": str(domain_state)}],
            )
            return response.content[0].text
        except Exception as e:
            raise OfficerAPIError(f"Errore chiamata AI per {self.name}: {e}") from e

    def get_species_bonus(self, key: str) -> float | bool:
        """Restituisce il bonus di specie per la chiave specificata"""
        bonuses = SPECIES_BONUSES.get(self.species, {})
        return bonuses.get(key, 1.0)

    def to_dict(self) -> dict:
        """Serializza l'ufficiale"""
        return {
            "name": self.name,
            "species": self.species.value,
            "role": self.role.value,
            "rank": self.rank,
            "trust": self.trust,
            "trust_history": self.trust_history,
            "personal_morale": self.personal_morale,
            "interaction_mode": self.interaction_mode.value,
            "model": self._model,
        }
