"""
Mappa galattica 8x8 quadranti, ogni quadrante contiene una sotto-griglia 8x8 settori.
Coordinate: [q_row][q_col][s_row][s_col] — tutte 1-8.
Notazione compatta a 4 cifre: "3472" = quadrante(3,4) settore(7,2).
Generazione procedurale con seed deterministico.
"""
from __future__ import annotations

import math
import random as _random_module
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class CellContent(Enum):
    """Contenuti possibili di una cella settore"""
    EMPTY = "·"           # vuoto
    STAR = "*"            # stella — ostacolo navigazione
    STARBASE = "B"        # base stellare Federazione
    KLINGON = "K"         # nave Klingon
    ROMULAN = "R"         # nave Romulana
    BORG = "!"            # cubo/sfera Borg
    SILENTI = "X"         # I Silenziosi (nome visibile da missione M04)
    SILENTI_WRECK = "W"   # relitto con tracce dei Silenziosi
    ANOMALY = "?"         # anomalia non identificata
    NEBULA = "~"          # nebula — oscura sensori
    PLANET = "P"          # pianeta
    SHIP = "E"            # nave del giocatore


class QuadrantVisibility(Enum):
    """Stato di visibilità (fog of war) per ogni quadrante"""
    UNKNOWN = "UNKNOWN"               # nessuna informazione
    SCANNED = "SCANNED"               # contenuto completo + dettaglio settori
    VISITED = "VISITED"               # snapshot al momento del passaggio (può essere stale)
    ADJACENT = "ADJACENT"             # solo conteggi aggregati parziali
    NEBULA_OBSCURED = "NEBULA_OBSCURED"  # solo conteggio totale entità, no tipo
    CURRENT = "CURRENT"               # quadrante corrente — sempre aggiornato


# Tipi di entità nemiche per conteggio
ENEMY_TYPES: set[CellContent] = {
    CellContent.KLINGON, CellContent.ROMULAN,
    CellContent.BORG, CellContent.SILENTI,
}


@dataclass
class Quadrant:
    """Un quadrante 8x8 della galassia"""
    row: int
    col: int
    sectors: list[list[CellContent]] = field(default_factory=list)
    visibility: QuadrantVisibility = QuadrantVisibility.UNKNOWN
    is_nebula: bool = False

    def __post_init__(self) -> None:
        if not self.sectors:
            # Inizializza griglia 8x8 vuota (indici 0-7, coordinate utente 1-8)
            self.sectors = [
                [CellContent.EMPTY for _ in range(8)]
                for _ in range(8)
            ]

    def get_sector(self, s_row: int, s_col: int) -> CellContent:
        """Restituisce il contenuto del settore (coordinate 1-8)"""
        return self.sectors[s_row - 1][s_col - 1]

    def set_sector(self, s_row: int, s_col: int, content: CellContent) -> None:
        """Imposta il contenuto del settore (coordinate 1-8)"""
        self.sectors[s_row - 1][s_col - 1] = content

    def count_by_type(self) -> dict[str, int]:
        """Conteggio aggregato delle entità per tipo"""
        counts: dict[str, int] = {}
        for row in self.sectors:
            for cell in row:
                if cell != CellContent.EMPTY:
                    key = cell.name
                    counts[key] = counts.get(key, 0) + 1
        return counts

    def total_entities(self) -> int:
        """Conteggio totale entità non vuote"""
        return sum(
            1 for row in self.sectors
            for cell in row if cell != CellContent.EMPTY
        )

    def to_dict(self) -> dict:
        """Serializza il quadrante"""
        return {
            "row": self.row,
            "col": self.col,
            "sectors": [
                [cell.value for cell in row]
                for row in self.sectors
            ],
            "visibility": self.visibility.value,
            "is_nebula": self.is_nebula,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Quadrant":
        """Deserializza il quadrante"""
        sectors = [
            [CellContent(cell) for cell in row]
            for row in d["sectors"]
        ]
        return cls(
            row=d["row"],
            col=d["col"],
            sectors=sectors,
            visibility=QuadrantVisibility(d["visibility"]),
            is_nebula=d.get("is_nebula", False),
        )


class Galaxy:
    """
    Mappa galattica 8x8 quadranti.
    Generazione procedurale da seed deterministico.
    """

    def __init__(self) -> None:
        # Griglia 8x8 di quadranti (indici 0-7, coordinate utente 1-8)
        self.quadrants: list[list[Quadrant]] = [
            [Quadrant(row=r + 1, col=c + 1) for c in range(8)]
            for r in range(8)
        ]
        self._seed: int = 0

    def _get_quadrant(self, q_row: int, q_col: int) -> Quadrant:
        """Accesso interno al quadrante (coordinate 1-8)"""
        return self.quadrants[q_row - 1][q_col - 1]

    def generate(self, seed: int, mission_config: dict) -> None:
        """
        Genera la mappa procedurale da seed.
        mission_config contiene: nemici, basi_stellari, silenti_eventi, ecc.
        Stesso seed → stessa mappa sempre.
        """
        self._seed = seed
        rng = _random_module.Random(seed)

        # Reset tutti i quadranti
        for r in range(8):
            for c in range(8):
                self.quadrants[r][c] = Quadrant(row=r + 1, col=c + 1)

        # Piazza stelle (3-6 per quadrante)
        for r in range(8):
            for c in range(8):
                q = self.quadrants[r][c]
                n_stars = rng.randint(3, 6)
                for _ in range(n_stars):
                    sr, sc = rng.randint(1, 8), rng.randint(1, 8)
                    if q.get_sector(sr, sc) == CellContent.EMPTY:
                        q.set_sector(sr, sc, CellContent.STAR)

        # Piazza pianeti (0-2 per quadrante)
        for r in range(8):
            for c in range(8):
                q = self.quadrants[r][c]
                n_planets = rng.randint(0, 2)
                for _ in range(n_planets):
                    sr, sc = rng.randint(1, 8), rng.randint(1, 8)
                    if q.get_sector(sr, sc) == CellContent.EMPTY:
                        q.set_sector(sr, sc, CellContent.PLANET)

        # Piazza nebule (4-8 quadranti contengono nebula)
        n_nebula_quads = rng.randint(4, 8)
        nebula_positions = rng.sample(
            [(r, c) for r in range(8) for c in range(8)],
            min(n_nebula_quads, 64),
        )
        for r, c in nebula_positions:
            q = self.quadrants[r][c]
            q.is_nebula = True
            # Piazza alcune celle nebula nei settori
            n_nebula_cells = rng.randint(4, 12)
            for _ in range(n_nebula_cells):
                sr, sc = rng.randint(1, 8), rng.randint(1, 8)
                if q.get_sector(sr, sc) == CellContent.EMPTY:
                    q.set_sector(sr, sc, CellContent.NEBULA)

        # Piazza anomalie (2-5 nella galassia)
        n_anomalies = rng.randint(2, 5)
        for _ in range(n_anomalies):
            qr, qc = rng.randint(0, 7), rng.randint(0, 7)
            sr, sc = rng.randint(1, 8), rng.randint(1, 8)
            if self.quadrants[qr][qc].get_sector(sr, sc) == CellContent.EMPTY:
                self.quadrants[qr][qc].set_sector(sr, sc, CellContent.ANOMALY)

        # Piazza basi stellari dalla configurazione missione
        n_starbases = mission_config.get("basi_stellari", 1)
        placed_bases = 0
        attempts = 0
        while placed_bases < n_starbases and attempts < 100:
            qr, qc = rng.randint(0, 7), rng.randint(0, 7)
            sr, sc = rng.randint(1, 8), rng.randint(1, 8)
            if self.quadrants[qr][qc].get_sector(sr, sc) == CellContent.EMPTY:
                self.quadrants[qr][qc].set_sector(sr, sc, CellContent.STARBASE)
                placed_bases += 1
            attempts += 1

        # Piazza nemici dalla configurazione missione
        nemici = mission_config.get("nemici", [])
        content_map: dict[str, CellContent] = {
            "klingon": CellContent.KLINGON,
            "romulani": CellContent.ROMULAN,
            "borg": CellContent.BORG,
            "silenti": CellContent.SILENTI,
        }
        for gruppo in nemici:
            tipo = gruppo.get("tipo", "")
            quantita = gruppo.get("quantita", 0)
            cell_type = content_map.get(tipo)
            if cell_type is None:
                continue
            placed = 0
            attempts = 0
            while placed < quantita and attempts < 100:
                qr, qc = rng.randint(0, 7), rng.randint(0, 7)
                sr, sc = rng.randint(1, 8), rng.randint(1, 8)
                if self.quadrants[qr][qc].get_sector(sr, sc) == CellContent.EMPTY:
                    self.quadrants[qr][qc].set_sector(sr, sc, cell_type)
                    placed += 1
                attempts += 1

        # Piazza eventi Silenziosi se presenti
        silenti_eventi = mission_config.get("silenti_eventi", [])
        for evento in silenti_eventi:
            tipo_ev = evento.get("tipo", "")
            settore = evento.get("settore")
            if tipo_ev == "lettura_anomala" and settore:
                qr, qc = settore[0] - 1, settore[1] - 1
                if 0 <= qr < 8 and 0 <= qc < 8:
                    # Piazza anomalia in un settore casuale del quadrante indicato
                    sr, sc = rng.randint(1, 8), rng.randint(1, 8)
                    if self.quadrants[qr][qc].get_sector(sr, sc) == CellContent.EMPTY:
                        self.quadrants[qr][qc].set_sector(sr, sc, CellContent.ANOMALY)
            elif tipo_ev == "relitto_trovabile" and settore:
                qr, qc = settore[0] - 1, settore[1] - 1
                if 0 <= qr < 8 and 0 <= qc < 8:
                    sr, sc = rng.randint(1, 8), rng.randint(1, 8)
                    if self.quadrants[qr][qc].get_sector(sr, sc) == CellContent.EMPTY:
                        self.quadrants[qr][qc].set_sector(sr, sc, CellContent.SILENTI_WRECK)

    def get_sector(self, q_row: int, q_col: int, s_row: int, s_col: int) -> CellContent:
        """Restituisce il contenuto di un settore specifico"""
        return self._get_quadrant(q_row, q_col).get_sector(s_row, s_col)

    def set_sector(
        self, q_row: int, q_col: int, s_row: int, s_col: int, content: CellContent
    ) -> None:
        """Imposta il contenuto di un settore specifico"""
        self._get_quadrant(q_row, q_col).set_sector(s_row, s_col, content)

    def get_quadrant_summary(self, q_row: int, q_col: int) -> dict:
        """Conteggi aggregati per tipo nel quadrante"""
        q = self._get_quadrant(q_row, q_col)
        summary = q.count_by_type()
        summary["visibility"] = q.visibility.value
        summary["is_nebula"] = q.is_nebula
        summary["position"] = (q_row, q_col)
        return summary

    def get_distances_from(self, pos: tuple[int, int, int, int]) -> dict[str, float]:
        """
        Calcola distanze euclidee dalla posizione data a tutte le entità note.
        Restituisce dict con chiavi tipo "KLINGON_3_4_7_2" e valori distanza.
        """
        q_row, q_col, s_row, s_col = pos
        # Posizione assoluta in griglia 64x64
        abs_row = (q_row - 1) * 8 + (s_row - 1)
        abs_col = (q_col - 1) * 8 + (s_col - 1)

        distances: dict[str, float] = {}
        for qr in range(8):
            for qc in range(8):
                q = self.quadrants[qr][qc]
                # Solo quadranti con visibilità sufficiente
                if q.visibility in (
                    QuadrantVisibility.UNKNOWN,
                    QuadrantVisibility.NEBULA_OBSCURED,
                ):
                    continue
                for sr in range(8):
                    for sc in range(8):
                        cell = q.sectors[sr][sc]
                        if cell in (CellContent.EMPTY, CellContent.STAR, CellContent.SHIP):
                            continue
                        target_abs_row = qr * 8 + sr
                        target_abs_col = qc * 8 + sc
                        dist = math.sqrt(
                            (abs_row - target_abs_row) ** 2
                            + (abs_col - target_abs_col) ** 2
                        )
                        key = f"{cell.name}_{qr+1}_{qc+1}_{sr+1}_{sc+1}"
                        distances[key] = round(dist, 2)
        return distances

    def scan_quadrant(self, q_row: int, q_col: int) -> None:
        """Marca quadrante come SCANNED — visibilità completa"""
        self._get_quadrant(q_row, q_col).visibility = QuadrantVisibility.SCANNED

    def update_adjacent_visibility(self, q_row: int, q_col: int) -> None:
        """Aggiorna la visibilità dei quadranti adiacenti a ADJACENT"""
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = q_row + dr, q_col + dc
                if 1 <= nr <= 8 and 1 <= nc <= 8:
                    q = self._get_quadrant(nr, nc)
                    if q.visibility == QuadrantVisibility.UNKNOWN:
                        if q.is_nebula:
                            q.visibility = QuadrantVisibility.NEBULA_OBSCURED
                        else:
                            q.visibility = QuadrantVisibility.ADJACENT

    def is_nebula(self, q_row: int, q_col: int) -> bool:
        """Verifica se il quadrante è una nebula"""
        return self._get_quadrant(q_row, q_col).is_nebula

    def to_dict(self) -> dict:
        """Serializza l'intera galassia"""
        return {
            "seed": self._seed,
            "quadrants": [
                [self.quadrants[r][c].to_dict() for c in range(8)]
                for r in range(8)
            ],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Galaxy":
        """Deserializza la galassia"""
        galaxy = cls()
        galaxy._seed = d.get("seed", 0)
        for r in range(8):
            for c in range(8):
                galaxy.quadrants[r][c] = Quadrant.from_dict(d["quadrants"][r][c])
        return galaxy
