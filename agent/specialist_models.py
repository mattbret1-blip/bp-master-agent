from __future__ import annotations
from pydantic import BaseModel, Field

from .models import Evidence, ReviewItem, StateUpdate


class SpecialistContribution(BaseModel):
    """Prose + proposed state changes from one non-assessor specialist.

    The manager weaves ``contribution`` into the single learner-facing
    response; it decides which proposed state updates survive into the
    final AgentDecision. The application, never the model, applies them.
    """

    contribution: str = ""
    state_updates: list[StateUpdate] = Field(default_factory=list)
    review_candidates: list[ReviewItem] = Field(default_factory=list)


class TutorOutput(SpecialistContribution):
    """Tutor specialist: instruction, explanation, guided practice."""


class LinguistOutput(SpecialistContribution):
    """Linguist specialist: grammar, sound system, syntax, semantics, variation."""


class ConversationOutput(SpecialistContribution):
    """Conversation specialist: realistic interaction, turn-taking, repair."""


class CultureOutput(SpecialistContribution):
    """Culture specialist: Brazilian history, anthropology, regional/social context."""


class AssessorOutput(BaseModel):
    """Assessor specialist: evidence only, never a mastery verdict by itself.

    Evidence items use the exact ``Evidence`` shape the existing pipeline
    consumes, so they flow through the same evidence gate in
    ``agent.core`` (a single correct response raises competency mastery
    slightly but never grants durable mastery or a CEFR promotion).
    """

    contribution: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    state_updates: list[StateUpdate] = Field(default_factory=list)
    review_candidates: list[ReviewItem] = Field(default_factory=list)
