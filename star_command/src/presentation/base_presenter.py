"""
ABC per il layer di presentazione.
Definisce il contratto che ogni implementazione (CLI, GUI, web) deve rispettare.
Corrisponde 1:1 al PresenterInterface Protocol definito in game_loop.py.
"""

from abc import ABC, abstractmethod


class BasePresenter(ABC):
    """Classe base astratta per la presentazione del gioco"""

    @abstractmethod
    def render_bridge(self, game_state: dict) -> None:
        """Visualizza il bridge completo con tutti gli indicatori"""
        ...

    @abstractmethod
    def show_officer_message(self, officer_name: str, role: str, message: str, trust: float) -> None:
        """Mostra il messaggio di un ufficiale con indicatore trust"""
        ...

    @abstractmethod
    def show_narrative_short(self, text: str, color: str) -> None:
        """Mostra un breve messaggio narrativo colorato"""
        ...

    @abstractmethod
    def show_narrative_long(self, text: str, title: str) -> None:
        """Mostra un blocco narrativo esteso (briefing, log, ecc.)"""
        ...

    @abstractmethod
    def show_map_overlay(self, galaxy_state: dict, ship_position: tuple) -> None:
        """Mostra la mappa galattica come overlay"""
        ...

    @abstractmethod
    def show_systems_overlay(self, systems_state: dict, repair_queue: list) -> None:
        """Mostra lo stato dei sistemi di bordo"""
        ...

    @abstractmethod
    def show_captain_log_overlay(self, entries: list) -> None:
        """Mostra il diario del capitano"""
        ...

    @abstractmethod
    def show_contextual_menu(self, context: str) -> str:
        """Mostra il menu contestuale e restituisce (non usato dal game_loop)"""
        ...

    @abstractmethod
    def get_captain_input(self) -> str:
        """Legge il comando dal Capitano"""
        ...

    @abstractmethod
    def show_confirm(self, message: str) -> bool:
        """Chiede conferma S/N al giocatore"""
        ...
