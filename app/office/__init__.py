"""Bureau virtuel 2D — façade HTTP et état temps réel.

Le bureau est un frontend statique séparé (`office/`) alimenté par les
événements réels du système. Aucun événement décoratif n'est produit ici :
tout ce qui s'affiche provient de la base SQLite des missions.
"""

from app.office.catalog import AGENTS, DEPARTMENTS, agent_catalog
from app.office.state import build_office_state
from app.office.stream import OfficeEventStream

__all__ = [
    "AGENTS",
    "DEPARTMENTS",
    "OfficeEventStream",
    "agent_catalog",
    "build_office_state",
]
