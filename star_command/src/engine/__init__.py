"""
Star Command — Game Engine Core
Logica di gioco pura, testabile in isolamento.
Zero import da presentation o officers.
"""

from .combat import GameEngineError
from .captain_log import OfficerAPIError
from .campaign import CampaignLoadError

__all__ = [
    "GameEngineError",
    "OfficerAPIError",
    "CampaignLoadError",
]
