"""Test per il modulo CaptainLog — entry manuali, export, serializzazione."""

import pytest
from pathlib import Path

from src.engine.captain_log import (
    CaptainLog, LogEntry, LogEntryType, LogTrigger,
    check_log_triggers, SHIP_TONE_MAP,
)
from src.engine.ship import ShipClass


class TestLogEntry:
    """Test singola entry"""

    def test_create_manual(self):
        entry = LogEntry(
            stardate=2347.5,
            entry_type=LogEntryType.MANUAL,
            text="Nota test",
            mission_id="M01",
        )
        assert entry.entry_type == LogEntryType.MANUAL
        assert entry.text == "Nota test"

    def test_serialization(self):
        entry = LogEntry(
            stardate=2347.5,
            entry_type=LogEntryType.AUTO,
            text="Entry automatica",
            mission_id="M02",
        )
        d = entry.to_dict()
        restored = LogEntry.from_dict(d)
        assert restored.stardate == 2347.5
        assert restored.entry_type == LogEntryType.AUTO
        assert restored.text == "Entry automatica"


class TestCaptainLog:
    """Test diario del capitano"""

    def test_add_manual(self):
        log = CaptainLog()
        log.add_manual(2347.1, "Prima nota", "M01")
        assert len(log.entries) == 1
        assert log.entries[0].entry_type == LogEntryType.MANUAL
        assert log.entries[0].text == "Prima nota"

    def test_get_entries_all(self):
        log = CaptainLog()
        log.add_manual(2347.1, "Nota M01", "M01")
        log.add_manual(2347.2, "Nota M02", "M02")
        assert len(log.get_entries()) == 2

    def test_get_entries_filtered(self):
        log = CaptainLog()
        log.add_manual(2347.1, "Nota M01", "M01")
        log.add_manual(2347.2, "Nota M02", "M02")
        log.add_manual(2347.3, "Altra M01", "M01")
        m01_entries = log.get_entries("M01")
        assert len(m01_entries) == 2
        assert all(e.mission_id == "M01" for e in m01_entries)

    def test_add_auto_no_client(self):
        """Senza client API, add_auto non fa nulla"""
        log = CaptainLog()
        log.add_auto(
            stardate=2347.1,
            mission_id="M01",
            event={"trigger": "test"},
            ship_name="Enterprise",
            ship_class=ShipClass.CONSTITUTION,
            client=None,
            model="test",
        )
        assert len(log.entries) == 0

    def test_export_to_file(self, tmp_path):
        log = CaptainLog()
        log.add_manual(2347.1, "Nota di test", "M01")
        log.add_manual(2347.5, "Seconda nota", "M01")
        path = log.export_to_file("USS Enterprise", str(tmp_path))
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "USS Enterprise" in content
        assert "Nota di test" in content
        assert "Seconda nota" in content

    def test_serialization_roundtrip(self):
        log = CaptainLog()
        log.add_manual(2347.1, "Nota 1", "M01")
        log.add_manual(2347.2, "Nota 2", "M02")
        d = log.to_dict()
        restored = CaptainLog.from_dict(d)
        assert len(restored.entries) == 2
        assert restored.entries[0].text == "Nota 1"
        assert restored.entries[1].mission_id == "M02"


class TestLogTriggers:
    """Test trigger automatici"""

    def test_trigger_without_client(self):
        """check_log_triggers senza client non genera entry"""
        log = CaptainLog()
        check_log_triggers(
            trigger=LogTrigger.MISSION_START,
            event_data={"missione": "M01"},
            captain_log=log,
            stardate=2347.1,
            mission_id="M01",
            ship_name="Enterprise",
            ship_class=ShipClass.CONSTITUTION,
            client=None,
            model="test",
        )
        assert len(log.entries) == 0


class TestShipToneMap:
    """Test mappa toni narrativi"""

    def test_all_classes_mapped(self):
        for sc in ShipClass:
            assert sc in SHIP_TONE_MAP
            assert SHIP_TONE_MAP[sc] in ("TOS", "TNG", "DS9", "VOY")

    def test_constitution_is_tos(self):
        assert SHIP_TONE_MAP[ShipClass.CONSTITUTION] == "TOS"

    def test_galaxy_is_tng(self):
        assert SHIP_TONE_MAP[ShipClass.GALAXY] == "TNG"

    def test_defiant_is_ds9(self):
        assert SHIP_TONE_MAP[ShipClass.DEFIANT] == "DS9"

    def test_intrepid_is_voy(self):
        assert SHIP_TONE_MAP[ShipClass.INTREPID] == "VOY"
