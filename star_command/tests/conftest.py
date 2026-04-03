"""Configurazione pytest condivisa per tutti i test."""

import sys
from pathlib import Path

# Assicura che il package star_command sia importabile
root = Path(__file__).parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
