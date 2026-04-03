"""Test per gli ufficiali AI — trust, morale, bonus, domain state, creazione."""

import pytest

from src.officers.base_officer import (
    Officer, OfficerRole, OfficerSpecies, InteractionMode,
    SPECIES_BONUSES,
)
from src.officers.tactical import TacticalOfficer
from src.officers.engineer import EngineerOfficer
from src.officers.science import ScienceOfficer
from src.officers.medical import MedicalOfficer
from src.officers.special.vulcan_ambassador import VulcanAmbassador


class TestTrustMechanism:
    """Test meccanismo trust degli ufficiali"""

    @pytest.fixture
    def officer(self):
        return TacticalOfficer.create_default()

    def test_initial_trust(self, officer):
        assert officer.trust == 75.0

    def test_trust_increase_on_follow(self, officer):
        old = officer.trust
        officer.update_trust(advice_followed=True)
        assert officer.trust == old + 2

    def test_trust_decrease_on_ignore(self, officer):
        old = officer.trust
        officer.update_trust(advice_followed=False)
        assert officer.trust == old - 1

    def test_trust_clamps_at_100(self, officer):
        officer.trust = 99.0
        officer.update_trust(advice_followed=True)
        assert officer.trust == 100.0

    def test_trust_clamps_at_0(self, officer):
        officer.trust = 0.5
        officer.update_trust(advice_followed=False)
        assert officer.trust == 0.0

    def test_5_consecutive_ignores_drops_morale(self, officer):
        old_morale = officer.personal_morale
        for _ in range(5):
            officer.update_trust(advice_followed=False)
        assert officer.personal_morale == old_morale - 10.0

    def test_trust_history_sliding_window(self, officer):
        for _ in range(15):
            officer.update_trust(advice_followed=True)
        assert len(officer.trust_history) == 10  # finestra scorrevole


class TestBonusMultiplier:
    """Test bonus basato su morale personale"""

    @pytest.fixture
    def officer(self):
        return TacticalOfficer.create_default()

    def test_high_morale_full_bonus(self, officer):
        officer.personal_morale = 85.0
        assert officer.get_bonus_multiplier() == 1.0

    def test_medium_morale_full_bonus(self, officer):
        officer.personal_morale = 60.0
        assert officer.get_bonus_multiplier() == 1.0

    def test_low_morale_half_bonus(self, officer):
        officer.personal_morale = 30.0
        assert officer.get_bonus_multiplier() == 0.5

    def test_zero_morale_no_bonus(self, officer):
        officer.personal_morale = 10.0
        assert officer.get_bonus_multiplier() == 0.0


class TestInteractionMode:
    """Test modalita interazione ufficiali"""

    def test_always_responds_when_called(self):
        officer = TacticalOfficer.create_default()
        officer.interaction_mode = InteractionMode.EMERGENCY_ONLY
        assert officer.should_respond("NAVIGATION", "called") is True

    def test_bridge_active_always_responds(self):
        officer = TacticalOfficer.create_default()
        officer.interaction_mode = InteractionMode.BRIDGE_ACTIVE
        assert officer.should_respond("NAVIGATION", "auto") is True

    def test_context_responds_in_context(self):
        officer = TacticalOfficer.create_default()
        officer.interaction_mode = InteractionMode.CONTEXT
        assert officer.should_respond("COMBAT", "auto") is True

    def test_context_silent_out_of_context(self):
        officer = TacticalOfficer.create_default()
        officer.interaction_mode = InteractionMode.CONTEXT
        assert officer.should_respond("NAVIGATION", "auto") is False

    def test_on_call_silent_auto(self):
        officer = TacticalOfficer.create_default()
        officer.interaction_mode = InteractionMode.ON_CALL
        assert officer.should_respond("COMBAT", "auto") is False

    def test_respond_no_client(self):
        officer = TacticalOfficer.create_default(client=None)
        result = officer.respond({"context": "COMBAT"}, trigger="called")
        assert result is None


class TestTacticalOfficer:
    """Test ufficiale tattico"""

    def test_create_default(self):
        t = TacticalOfficer.create_default()
        assert t.name == "Worf"
        assert t.species == OfficerSpecies.KLINGON
        assert t.role == OfficerRole.TACTICAL

    def test_is_active_in_combat(self):
        t = TacticalOfficer.create_default()
        assert t._is_active_in_context("COMBAT") is True
        assert t._is_active_in_context("NAVIGATION") is False

    def test_domain_state(self):
        t = TacticalOfficer.create_default()
        state = {
            "ship": {"shields_pct": 80, "energy": 3000, "torpedoes": 10, "morale_pct": 70},
            "systems": {"computer_puntamento": {"integrity": 90}},
            "enemies": [{"shields_pct": 50}],
        }
        domain = t.get_domain_state(state)
        assert "scudi_propri_pct" in domain
        assert "nemici_in_settore" in domain
        assert domain["nemici_in_settore"] == 1


class TestEngineerOfficer:
    """Test ingegnere capo"""

    def test_create_default(self):
        e = EngineerOfficer.create_default()
        assert e.name == "Scott"
        assert e.role == OfficerRole.ENGINEER


class TestScienceOfficer:
    """Test ufficiale scientifico"""

    def test_create_default(self):
        s = ScienceOfficer.create_default()
        assert s.name == "T'Pol"
        assert s.species == OfficerSpecies.VULCAN
        assert s.role == OfficerRole.SCIENCE


class TestMedicalOfficer:
    """Test medico di bordo"""

    def test_create_default(self):
        m = MedicalOfficer.create_default()
        assert m.name == "Crusher"
        assert m.role == OfficerRole.MEDICAL


class TestVulcanAmbassador:
    """Test ambasciatore vulcaniano"""

    def test_create_default(self):
        v = VulcanAmbassador.create_default(ship_name="Enterprise")
        assert v.name == "T'Vek"
        assert v.species == OfficerSpecies.VULCAN
        assert v.role == OfficerRole.SPECIAL
        assert v.ship_name == "Enterprise"

    def test_active_in_diplomacy(self):
        v = VulcanAmbassador.create_default()
        assert v._is_active_in_context("DIPLOMACY") is True
        assert v._is_active_in_context("COMBAT") is False


class TestSpeciesBonuses:
    """Test bonus di specie"""

    def test_vulcan_scan_bonus(self):
        t = ScienceOfficer.create_default()
        assert t.get_species_bonus("scan_bonus") == 1.20

    def test_klingon_combat_damage(self):
        t = TacticalOfficer.create_default()
        assert t.get_species_bonus("combat_damage") == 1.25

    def test_klingon_refuses_retreat(self):
        t = TacticalOfficer.create_default()
        assert t.get_species_bonus("refuses_retreat") is True

    def test_unknown_bonus_returns_default(self):
        t = TacticalOfficer.create_default()
        assert t.get_species_bonus("nonexistent_key") == 1.0


class TestOfficerSerialization:
    """Test serializzazione ufficiali"""

    def test_to_dict(self):
        t = TacticalOfficer.create_default()
        d = t.to_dict()
        assert d["name"] == "Worf"
        assert d["role"] == "tattico"
        assert d["species"] == "Klingon"
        assert "trust" in d
        assert "personal_morale" in d
