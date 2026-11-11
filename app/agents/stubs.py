"""Point de compatibilité historique.

Les agents réels sont implémentés dans `app.agents.phase5`, `app.agents.phase6`
et `app.agents.phase7`. Ce module ne définit plus aucun agent : il conserve
uniquement les ré-exports des anciens imports, pour ne pas casser les scripts
ou les tests existants.
"""

from app.agents.phase7 import DevOpsAgent, QAReporterAgent

__all__ = ["DevOpsAgent", "QAReporterAgent"]
