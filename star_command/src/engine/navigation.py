"""
Sistema di navigazione: warp e impulso.
Tabella consumi, regole di movimento, calcolo stardate.
Gli effetti del degrado dei sistemi di propulsione sono applicati qui.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from .ship import Ship, ShipClass
from .systems import ShipSystem, SystemName, SystemStatus
from .difficulty import DifficultyConfig
from .galaxy import Galaxy, CellContent


class NavigationError(Exception):
    """Errore di navigazione"""
    pass


@dataclass
class WarpSpec:
    """Specifica consumo per un livello warp"""
    energia: float
    dilithium: int
    distanza_settori: int
    distanza_quadranti: int


# Tabella consumi per classe base Constitution
WARP_TABLE: dict[str, WarpSpec] = {
    "impulso": WarpSpec(energia=100, dilithium=0, distanza_settori=1, distanza_quadranti=0),
    "warp_1": WarpSpec(energia=200, dilithium=1, distanza_settori=0, distanza_quadranti=1),
    "warp_3": WarpSpec(energia=500, dilithium=3, distanza_settori=0, distanza_quadranti=3),
    "warp_6": WarpSpec(energia=1200, dilithium=8, distanza_settori=0, distanza_quadranti=6),
    "warp_emergenza": WarpSpec(energia=2000, dilithium=15, distanza_settori=0, distanza_quadranti=9),
}

# Mappa velocità warp al nome della tabella
WARP_SPEED_MAP: dict[int, str] = {
    0: "impulso",
    1: "warp_1",
    3: "warp_3",
    6: "warp_6",
    9: "warp_emergenza",
}


class MoveResult(NamedTuple):
    """Risultato di un movimento"""
    success: bool
    new_position: tuple[int, int, int, int]
    energy_spent: float
    dilithium_spent: int
    stardate_elapsed: float
    message: str


def get_warp_spec(speed: int, ship: Ship) -> WarpSpec:
    """
    Restituisce la specifica warp per la velocità richiesta,
    applicando modificatori di classe nave.
    """
    key = WARP_SPEED_MAP.get(speed)
    if key is None:
        # Trova la velocità più vicina disponibile
        available = sorted(WARP_SPEED_MAP.keys())
        for s in available:
            if s >= speed:
                key = WARP_SPEED_MAP[s]
                break
        if key is None:
            key = "warp_emergenza"

    base = WARP_TABLE[key]
    # Modificatore dilithium per classe Excelsior
    dilithium_cost = base.dilithium
    if ship.dilithium_consumption_modifier != 1.0:
        dilithium_cost = max(0, int(base.dilithium * ship.dilithium_consumption_modifier))

    return WarpSpec(
        energia=base.energia,
        dilithium=dilithium_cost,
        distanza_settori=base.distanza_settori,
        distanza_quadranti=base.distanza_quadranti,
    )


def get_max_warp(
    ship: Ship,
    systems: dict[SystemName, ShipSystem],
) -> int:
    """
    Calcola la velocità warp massima considerando:
    - Integrità motori warp (penalty riduce max warp)
    - Dilithium disponibile
    """
    warp_sys = systems.get(SystemName.WARP_ENGINES)
    if warp_sys is None or warp_sys.status == SystemStatus.OFFLINE:
        return 0  # solo impulso

    # Velocità max ridotta dal penalty
    max_warp_base = 9
    effective_max = int(max_warp_base * (1.0 - warp_sys.penalty))

    # Senza dilithium → solo impulso
    if ship.dilithium <= 0:
        return 0

    return max(0, effective_max)


def validate_destination(
    galaxy: Galaxy,
    q_row: int, q_col: int,
    s_row: int, s_col: int,
) -> tuple[bool, str]:
    """Verifica che la destinazione sia valida"""
    # Controllo limiti
    if not (1 <= q_row <= 8 and 1 <= q_col <= 8):
        return False, "Coordinate quadrante fuori dai limiti (1-8)"
    if not (1 <= s_row <= 8 and 1 <= s_col <= 8):
        return False, "Coordinate settore fuori dai limiti (1-8)"

    # Stelle sono ostacoli
    content = galaxy.get_sector(q_row, q_col, s_row, s_col)
    if content == CellContent.STAR:
        return False, "Impossibile navigare su una stella"

    return True, "OK"


def navigate_impulse(
    ship: Ship,
    galaxy: Galaxy,
    systems: dict[SystemName, ShipSystem],
    difficulty: DifficultyConfig,
    target_s_row: int,
    target_s_col: int,
) -> MoveResult:
    """
    Navigazione a impulso — movimento intra-quadrante (1 settore alla volta).
    """
    q_row, q_col, s_row, s_col = ship.position

    # Verifica motori impulso
    impulse_sys = systems.get(SystemName.IMPULSE_ENGINES)
    if impulse_sys and impulse_sys.integrity < 20:
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message="Motori impulso troppo danneggiati per manovrare",
        )

    # Verifica destinazione nello stesso quadrante
    if not (1 <= target_s_row <= 8 and 1 <= target_s_col <= 8):
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message="Coordinate settore fuori dai limiti (1-8)",
        )

    # Calcola distanza in settori
    dist = abs(target_s_row - s_row) + abs(target_s_col - s_col)
    if dist == 0:
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message="Già nella posizione target",
        )

    # Verifica destinazione
    valid, msg = validate_destination(galaxy, q_row, q_col, target_s_row, target_s_col)
    if not valid:
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message=msg,
        )

    # Consumo energia per impulso (per settore)
    spec = WARP_TABLE["impulso"]
    energy_cost = spec.energia * dist * difficulty.resource_drain
    if not ship.consume_energy(energy_cost):
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message=f"Energia insufficiente (richiesta: {energy_cost:.0f})",
        )

    # Consumo stardate: 0.05 per settore
    stardate_cost = dist * 0.05

    # Aggiorna posizione sulla mappa
    galaxy.set_sector(q_row, q_col, s_row, s_col, CellContent.EMPTY)
    galaxy.set_sector(q_row, q_col, target_s_row, target_s_col, CellContent.SHIP)
    new_pos = (q_row, q_col, target_s_row, target_s_col)
    ship.position = new_pos

    return MoveResult(
        success=True,
        new_position=new_pos,
        energy_spent=energy_cost,
        dilithium_spent=0,
        stardate_elapsed=stardate_cost,
        message=f"Impulso: spostamento a settore ({target_s_row},{target_s_col})",
    )


def navigate_warp(
    ship: Ship,
    galaxy: Galaxy,
    systems: dict[SystemName, ShipSystem],
    difficulty: DifficultyConfig,
    target_q_row: int,
    target_q_col: int,
    target_s_row: int = 1,
    target_s_col: int = 1,
    warp_speed: int = 1,
) -> MoveResult:
    """
    Navigazione warp — movimento inter-quadrante.
    """
    # Verifica dilithium
    if ship.dilithium <= 0:
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message="Dilithium esaurito — solo impulso disponibile",
        )

    # Verifica velocità massima
    max_warp = get_max_warp(ship, systems)
    if warp_speed > max_warp:
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message=f"Warp {warp_speed} non disponibile (max: {max_warp})",
        )

    # Verifica destinazione
    valid, msg = validate_destination(galaxy, target_q_row, target_q_col, target_s_row, target_s_col)
    if not valid:
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message=msg,
        )

    # Calcola distanza in quadranti
    q_row, q_col, s_row, s_col = ship.position
    q_dist = abs(target_q_row - q_row) + abs(target_q_col - q_col)

    if q_dist == 0:
        # Stesso quadrante — usa impulso
        return navigate_impulse(ship, galaxy, systems, difficulty, target_s_row, target_s_col)

    # Verifica che la distanza sia raggiungibile con il warp selezionato
    spec = get_warp_spec(warp_speed, ship)
    if spec.distanza_quadranti < q_dist:
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message=f"Warp {warp_speed} insufficiente per {q_dist} quadranti",
        )

    # Consumo risorse (proporzionale alla distanza reale)
    energy_cost = spec.energia * difficulty.resource_drain
    dilithium_cost = spec.dilithium

    if not ship.consume_energy(energy_cost):
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message=f"Energia insufficiente (richiesta: {energy_cost:.0f})",
        )
    if not ship.consume_dilithium(dilithium_cost):
        # Ripristina energia
        ship.energy += energy_cost
        return MoveResult(
            success=False,
            new_position=ship.position,
            energy_spent=0,
            dilithium_spent=0,
            stardate_elapsed=0,
            message=f"Dilithium insufficiente (richiesto: {dilithium_cost})",
        )

    # Consumo stardate: distanza × 0.2 × stardate_pressure
    stardate_cost = q_dist * 0.2 * difficulty.stardate_pressure

    # Aggiorna posizione sulla mappa
    galaxy.set_sector(q_row, q_col, s_row, s_col, CellContent.EMPTY)
    # Marca vecchio quadrante come VISITED
    from .galaxy import QuadrantVisibility
    old_quad = galaxy._get_quadrant(q_row, q_col)
    if old_quad.visibility == QuadrantVisibility.CURRENT:
        old_quad.visibility = QuadrantVisibility.VISITED

    # Posiziona la nave nel nuovo quadrante
    galaxy.set_sector(target_q_row, target_q_col, target_s_row, target_s_col, CellContent.SHIP)
    new_quad = galaxy._get_quadrant(target_q_row, target_q_col)
    new_quad.visibility = QuadrantVisibility.CURRENT

    # Aggiorna visibilità quadranti adiacenti
    galaxy.update_adjacent_visibility(target_q_row, target_q_col)

    new_pos = (target_q_row, target_q_col, target_s_row, target_s_col)
    ship.position = new_pos

    return MoveResult(
        success=True,
        new_position=new_pos,
        energy_spent=energy_cost,
        dilithium_spent=dilithium_cost,
        stardate_elapsed=stardate_cost,
        message=f"Warp {warp_speed}: arrivo in quadrante ({target_q_row},{target_q_col}) settore ({target_s_row},{target_s_col})",
    )


def calculate_stardate_cost_warp(
    distance_quadrants: int,
    difficulty: DifficultyConfig,
) -> float:
    """Calcola il costo stardate per un viaggio warp"""
    return distance_quadrants * 0.2 * difficulty.stardate_pressure
