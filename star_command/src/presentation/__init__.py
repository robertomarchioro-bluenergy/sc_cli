"""
Star Command — Presentation Layer
Interfacce terminale LCARS-style con Rich.
"""

from .base_presenter import BasePresenter
from .cli_lcars import CLILcarsPresenter

__all__ = [
    "BasePresenter",
    "CLILcarsPresenter",
]
