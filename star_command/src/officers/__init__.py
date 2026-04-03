"""
Star Command — AI Officer Layer
Agenti Claude AI, uno per ruolo. Ricevono solo dict serializzati.
"""

from .base_officer import Officer, OfficerRole, OfficerSpecies, InteractionMode, OfficerAPIError
from .tactical import TacticalOfficer
from .engineer import EngineerOfficer
from .science import ScienceOfficer
from .medical import MedicalOfficer

__all__ = [
    "Officer",
    "OfficerRole",
    "OfficerSpecies",
    "InteractionMode",
    "OfficerAPIError",
    "TacticalOfficer",
    "EngineerOfficer",
    "ScienceOfficer",
    "MedicalOfficer",
]
