"""Test per il modulo Systems — degrado, penalty, riparazioni, coda."""

import pytest

from src.engine.systems import (
    ShipSystem, SystemName, SystemStatus, RepairQueue, RepairJob,
    create_default_systems, systems_to_dict, systems_from_dict,
)


class TestShipSystem:
    """Test singolo sistema di bordo"""

    def test_status_nominal(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=80.0)
        assert sys.status == SystemStatus.NOMINAL

    def test_status_degraded(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=40.0)
        assert sys.status == SystemStatus.DEGRADED

    def test_status_critical(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=10.0)
        assert sys.status == SystemStatus.CRITICAL

    def test_status_offline(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=0.0)
        assert sys.status == SystemStatus.OFFLINE

    def test_penalty_at_100(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=100.0)
        assert sys.penalty == 0.0

    def test_penalty_at_50(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=50.0)
        assert sys.penalty == 0.0

    def test_penalty_at_0(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=0.0)
        assert sys.penalty == 1.0

    def test_penalty_progressive(self):
        """La penalty è esponenziale sotto il 50%"""
        sys40 = ShipSystem(name=SystemName.SENSORS, integrity=40.0)
        sys20 = ShipSystem(name=SystemName.SENSORS, integrity=20.0)
        # penalty a 40% < penalty a 20%
        assert sys40.penalty < sys20.penalty
        # penalty a 40% = ((50-40)/50)^1.5 = 0.2^1.5 ≈ 0.089
        assert abs(sys40.penalty - 0.2**1.5) < 0.001

    def test_apply_damage(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=80.0)
        sys.apply_damage(30.0)
        assert sys.integrity == 50.0

    def test_apply_damage_clamps(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=10.0)
        sys.apply_damage(50.0)
        assert sys.integrity == 0.0

    def test_repair(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=50.0)
        sys.repair(30.0)
        assert sys.integrity == 80.0

    def test_repair_clamps(self):
        sys = ShipSystem(name=SystemName.SENSORS, integrity=90.0)
        sys.repair(20.0)
        assert sys.integrity == 100.0


class TestCreateDefaultSystems:
    """Test creazione set completo di sistemi"""

    def test_default_systems_count(self):
        systems = create_default_systems(is_intrepid=False)
        # 9 sistemi (esclude BIONUERAL_GEL)
        assert SystemName.BIONUERAL_GEL not in systems
        assert len(systems) == 9

    def test_intrepid_has_bioneural(self):
        systems = create_default_systems(is_intrepid=True)
        assert SystemName.BIONUERAL_GEL in systems
        assert len(systems) == 10

    def test_all_at_100(self):
        systems = create_default_systems()
        for sys in systems.values():
            assert sys.integrity == 100.0


class TestRepairQueue:
    """Test coda riparazioni"""

    def test_add_job(self):
        rq = RepairQueue()
        rq.add(SystemName.SENSORS, priority=1)
        assert len(rq.jobs) == 1
        assert rq.jobs[0].system == SystemName.SENSORS

    def test_no_duplicates(self):
        rq = RepairQueue()
        rq.add(SystemName.SENSORS, priority=2)
        rq.add(SystemName.SENSORS, priority=1)
        assert len(rq.jobs) == 1
        # Priorita aggiornata al minimo
        assert rq.jobs[0].priority == 1

    def test_sorted_by_priority(self):
        rq = RepairQueue()
        rq.add(SystemName.SENSORS, priority=3)
        rq.add(SystemName.WARP_ENGINES, priority=1)
        rq.add(SystemName.COMMUNICATIONS, priority=2)
        assert rq.jobs[0].system == SystemName.WARP_ENGINES
        assert rq.jobs[1].system == SystemName.COMMUNICATIONS
        assert rq.jobs[2].system == SystemName.SENSORS

    def test_tick_docked_parallel(self):
        """In porto: tutti i job avanzano"""
        rq = RepairQueue()
        systems = create_default_systems()
        systems[SystemName.SENSORS].integrity = 50.0
        systems[SystemName.WARP_ENGINES].integrity = 60.0
        rq.add(SystemName.SENSORS, priority=1)
        rq.add(SystemName.WARP_ENGINES, priority=2)

        rq.tick(docked=True, repair_speed_modifier=1.0, systems=systems)
        # Entrambi dovrebbero essere avanzati
        assert systems[SystemName.SENSORS].integrity > 50.0
        assert systems[SystemName.WARP_ENGINES].integrity > 60.0

    def test_tick_in_mission_sequential(self):
        """In missione: solo il primo job avanza"""
        rq = RepairQueue()
        systems = create_default_systems()
        systems[SystemName.SENSORS].integrity = 50.0
        systems[SystemName.WARP_ENGINES].integrity = 50.0
        rq.add(SystemName.SENSORS, priority=1)
        rq.add(SystemName.WARP_ENGINES, priority=2)

        rq.tick(docked=False, repair_speed_modifier=1.0, systems=systems)
        # Solo il primo (sensors, priority 1) avanza
        assert systems[SystemName.SENSORS].integrity > 50.0
        assert systems[SystemName.WARP_ENGINES].integrity == 50.0

    def test_tick_completes_job(self):
        """Riparazione completata viene rimossa dalla coda"""
        rq = RepairQueue()
        systems = create_default_systems()
        systems[SystemName.SENSORS].integrity = 95.0
        rq.add(SystemName.SENSORS, priority=1)

        msgs = rq.tick(docked=True, repair_speed_modifier=1.0, systems=systems)
        assert systems[SystemName.SENSORS].integrity == 100.0
        assert len(rq.jobs) == 0
        assert any("completata" in m.lower() for m in msgs)

    def test_remove(self):
        rq = RepairQueue()
        rq.add(SystemName.SENSORS, priority=1)
        rq.remove(SystemName.SENSORS)
        assert len(rq.jobs) == 0


class TestSystemsSerialization:
    """Test serializzazione/deserializzazione sistemi"""

    def test_roundtrip(self):
        systems = create_default_systems()
        systems[SystemName.SENSORS].integrity = 42.0
        d = systems_to_dict(systems)
        restored = systems_from_dict(d)
        assert restored[SystemName.SENSORS].integrity == 42.0
        assert len(restored) == len(systems)
