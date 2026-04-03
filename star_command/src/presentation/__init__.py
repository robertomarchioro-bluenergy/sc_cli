"""
Star Command — Presentation Layer
Interfacce terminale LCARS-style (Rich) e web (Flask).
"""

from .base_presenter import BasePresenter
from .cli_lcars import CLILcarsPresenter
from .web_presenter import WebPresenter

__all__ = [
    "BasePresenter",
    "CLILcarsPresenter",
    "WebPresenter",
]
