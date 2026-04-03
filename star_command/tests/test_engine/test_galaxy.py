"""Test per il modulo Galaxy — generazione, visibilita, scansione, fog of war."""

import pytest

from src.engine.galaxy import (
    Galaxy, Quadrant, CellContent, QuadrantVisibility, ENEMY_TYPES,
)


class TestQuadrant:
    """Test singolo quadrante"""

    def test_default_empty(self):
        q = Quadrant(row=1, col=1)
        for r in range(1, 9):
            for c in range(1, 9):
                assert q.get_sector(r, c) == CellContent.EMPTY

    def test_set_and_get(self):
        q = Quadrant(row=1, col=1)
        q.set_sector(3, 5, CellContent.KLINGON)
        assert q.get_sector(3, 5) == CellContent.KLINGON
        assert q.get_sector(3, 4) == CellContent.EMPTY

    def test_count_by_type(self):
        q = Quadrant(row=1, col=1)
        q.set_sector(1, 1, CellContent.KLINGON)
        q.set_sector(2, 2, CellContent.KLINGON)
        q.set_sector(3, 3, CellContent.STARBASE)
        counts = q.count_by_type()
        assert counts.get("KLINGON") == 2
        assert counts.get("STARBASE") == 1

    def test_total_entities(self):
        q = Quadrant(row=1, col=1)
        assert q.total_entities() == 0
        q.set_sector(1, 1, CellContent.STAR)
        q.set_sector(2, 2, CellContent.KLINGON)
        assert q.total_entities() == 2

    def test_serialization(self):
        q = Quadrant(row=3, col=4)
        q.set_sector(1, 1, CellContent.KLINGON)
        q.visibility = QuadrantVisibility.SCANNED
        d = q.to_dict()
        q2 = Quadrant.from_dict(d)
        assert q2.row == 3
        assert q2.col == 4
        assert q2.get_sector(1, 1) == CellContent.KLINGON
        assert q2.visibility == QuadrantVisibility.SCANNED


class TestGalaxy:
    """Test galassia completa"""

    def test_initial_empty(self):
        g = Galaxy()
        # 64 quadranti
        assert len(g.quadrants) == 8
        assert len(g.quadrants[0]) == 8

    def test_get_set_sector(self):
        g = Galaxy()
        g.set_sector(1, 1, 4, 4, CellContent.SHIP)
        assert g.get_sector(1, 1, 4, 4) == CellContent.SHIP

    def test_generate_deterministic(self):
        """Stesso seed = stessa mappa"""
        config = {"nemici": [{"tipo": "klingon", "quantita": 3}], "basi_stellari": 1}
        g1 = Galaxy()
        g1.generate(42, config)
        g2 = Galaxy()
        g2.generate(42, config)
        # Confronta tutti i settori
        for r in range(8):
            for c in range(8):
                for sr in range(1, 9):
                    for sc in range(1, 9):
                        assert (
                            g1.get_sector(r + 1, c + 1, sr, sc)
                            == g2.get_sector(r + 1, c + 1, sr, sc)
                        )

    def test_generate_places_enemies(self):
        """Verifica che i nemici vengano piazzati"""
        config = {"nemici": [{"tipo": "klingon", "quantita": 5}], "basi_stellari": 0}
        g = Galaxy()
        g.generate(42, config)
        klingon_count = 0
        for r in range(8):
            for c in range(8):
                counts = g.quadrants[r][c].count_by_type()
                klingon_count += counts.get("KLINGON", 0)
        assert klingon_count == 5

    def test_generate_places_starbases(self):
        config = {"nemici": [], "basi_stellari": 3}
        g = Galaxy()
        g.generate(99, config)
        base_count = 0
        for r in range(8):
            for c in range(8):
                counts = g.quadrants[r][c].count_by_type()
                base_count += counts.get("STARBASE", 0)
        assert base_count == 3

    def test_scan_quadrant(self):
        g = Galaxy()
        assert g.quadrants[0][0].visibility == QuadrantVisibility.UNKNOWN
        g.scan_quadrant(1, 1)
        assert g.quadrants[0][0].visibility == QuadrantVisibility.SCANNED

    def test_update_adjacent_visibility(self):
        g = Galaxy()
        g.update_adjacent_visibility(4, 4)
        # Quadranti adiacenti a (4,4) dovrebbero essere ADJACENT
        assert g.quadrants[2][2].visibility == QuadrantVisibility.ADJACENT  # (3,3)
        assert g.quadrants[2][3].visibility == QuadrantVisibility.ADJACENT  # (3,4)
        # Lontani rimangono UNKNOWN
        assert g.quadrants[0][0].visibility == QuadrantVisibility.UNKNOWN

    def test_is_nebula(self):
        g = Galaxy()
        g.quadrants[0][0].is_nebula = True
        assert g.is_nebula(1, 1) is True
        assert g.is_nebula(1, 2) is False

    def test_serialization_roundtrip(self):
        config = {"nemici": [{"tipo": "klingon", "quantita": 2}], "basi_stellari": 1}
        g = Galaxy()
        g.generate(42, config)
        d = g.to_dict()
        g2 = Galaxy.from_dict(d)
        assert g2._seed == 42
        for r in range(8):
            for c in range(8):
                for sr in range(1, 9):
                    for sc in range(1, 9):
                        assert (
                            g.get_sector(r + 1, c + 1, sr, sc)
                            == g2.get_sector(r + 1, c + 1, sr, sc)
                        )
