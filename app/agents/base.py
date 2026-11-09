from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.models import AgentResult, Mission, Task


class BaseAgent(ABC):
    name: str
    label: str

    @abstractmethod
    def run(
        self,
        task: Task,
        mission: Mission,
        context: dict | None = None,
    ) -> AgentResult:
        """Exécute une tâche bornée et retourne un résultat structuré."""
