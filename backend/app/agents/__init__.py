"""Agent registry: maps agent names to agent classes."""
from app.agents.architect import ArchitectAgent
from app.agents.auditor import AuditorAgent
from app.agents.base import BaseAgent
from app.agents.context_agent import ContextAgent
from app.agents.radar import RadarAgent
from app.agents.reviser import ReviserAgent
from app.agents.settler import SettlerAgent
from app.agents.writer import WriterAgent

AGENT_CLASSES = {
    "radar": RadarAgent,
    "architect": ArchitectAgent,
    "context": ContextAgent,
    "writer": WriterAgent,
    "settler": SettlerAgent,
    "auditor": AuditorAgent,
    "reviser": ReviserAgent,
}

__all__ = [
    "BaseAgent", "RadarAgent", "ArchitectAgent", "ContextAgent",
    "WriterAgent", "SettlerAgent", "AuditorAgent", "ReviserAgent", "AGENT_CLASSES",
]
