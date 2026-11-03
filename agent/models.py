from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

CEFR = Literal["A1","A2","B1","B2","C1","C2"]
MasteryStage = Literal[
    "Recognition","Recall","Controlled Production",
    "Spontaneous Production","Automaticity"
]
EvidenceStatus = Literal[
    "Observado","Inferido","Não demonstrado",
    "Não avaliado","Pendente","Inconclusivo"
]

class DomainLevel(BaseModel):
    level: Optional[CEFR] = None
    confidence: float = Field(0.0, ge=0, le=1)
    evidence_count: int = 0

class CEFRProfile(BaseModel):
    overall: Optional[CEFR] = None
    listening: DomainLevel = Field(default_factory=DomainLevel)
    speaking: DomainLevel = Field(default_factory=DomainLevel)
    reading: DomainLevel = Field(default_factory=DomainLevel)
    writing: DomainLevel = Field(default_factory=DomainLevel)
    grammar: DomainLevel = Field(default_factory=DomainLevel)
    vocabulary: DomainLevel = Field(default_factory=DomainLevel)
    pronunciation: DomainLevel = Field(default_factory=DomainLevel)
    pragmatics: DomainLevel = Field(default_factory=DomainLevel)
    cultural_competence: DomainLevel = Field(default_factory=DomainLevel)
    fluency: DomainLevel = Field(default_factory=DomainLevel)

class Evidence(BaseModel):
    evidence_id: str = ""
    domain: str
    concept_id: Optional[str] = None
    evidence: str
    status: EvidenceStatus
    interpretation: str = ""
    confidence: float = Field(0.5, ge=0, le=1)
    limitation: str = ""
    mastery_stage: Optional[MasteryStage] = None
    source: str = "conversation"

class ErrorItem(BaseModel):
    error_id: str
    category: str
    form: str
    correction: str = ""
    explanation: str = ""
    count: int = 1
    impact: float = Field(0.5, ge=0, le=1)
    contexts: list[str] = Field(default_factory=list)

class VocabularyItem(BaseModel):
    term: str
    meaning: str = ""
    usage_register: str = ""
    region: str = ""
    status: str = "new"
    repetitions: int = 0
    ease: float = 2.5
    interval_days: float = 0
    last_seen: Optional[str] = None
    next_review: Optional[str] = None

class ReviewItem(BaseModel):
    item_id: str
    kind: Literal["vocabulary","grammar","pronunciation","pragmatics","culture","error","mixed"]
    prompt: str
    answer_key: str = ""
    due_at: str
    interval_days: float = 1
    ease: float = 2.5
    repetitions: int = 0
    priority: Literal["normal","high"] = "normal"

class CompetencyNode(BaseModel):
    id: str
    label: str
    domain: str
    description: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    level: Optional[CEFR] = None
    mastery: float = Field(0.0, ge=0, le=1)
    confidence: float = Field(0.0, ge=0, le=1)
    evidence_count: int = 0

class RouteDecision(BaseModel):
    mode: Literal[
        "diagnostic","lesson","practice","conversation","review",
        "assessment","translation","clarification","planning","pause"
    ]
    specialists: list[Literal["tutor","linguist","conversation","culture","assessor"]]
    goal: Optional[str] = None
    obstacle: Optional[str] = None
    context: Optional[str] = None
    focus: Optional[str] = None
    reason: str = ""

class StateUpdate(BaseModel):
    update_type: Literal[
        "update_goal","update_context","update_instruction_language",
        "update_modality","add_mastered_candidate","add_reinforce",
        "add_recurring_error","add_vocabulary","add_review_item",
        "add_assessment_evidence","update_competency","update_cefr"
    ]
    payload: dict[str, Any] = Field(default_factory=dict)

class AgentDecision(BaseModel):
    mode: str
    goal: Optional[str] = None
    obstacle: Optional[str] = None
    context: Optional[str] = None
    focus: Optional[str] = None
    next_action: Literal[
        "ask_user","teach","practice","assess","converse","review",
        "translate","clarify","research_needed","pause","end"
    ] = "ask_user"
    response: str
    evidence: list[Evidence] = Field(default_factory=list)
    state_updates: list[StateUpdate] = Field(default_factory=list)
    review_candidates: list[ReviewItem] = Field(default_factory=list)
    research_requests: list[ResearchRequest] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    certainty_note: str = ""

class QualityReport(BaseModel):
    pass_gate: bool
    issues: list[str] = Field(default_factory=list)
    revised_response: Optional[str] = None

class ResearchRequest(BaseModel):
    query: str
    reason: str
    priority: Literal["low","medium","high"] = "medium"
    requires_citation: bool = True

class ResearchSource(BaseModel):
    title: str
    url: str
    excerpt: str = ""
    source_type: str = "web"

class LearnerProfile(BaseModel):
    goals: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    instruction_language: Optional[str] = None
    modality: Optional[str] = None
    cefr: CEFRProfile = Field(default_factory=CEFRProfile)
    mastered: list[str] = Field(default_factory=list)
    reinforce: list[str] = Field(default_factory=list)
    recurring_errors: list[ErrorItem] = Field(default_factory=list)
    vocabulary: list[VocabularyItem] = Field(default_factory=list)
    assessment_history: list[Evidence] = Field(default_factory=list)
    review_queue: list[ReviewItem] = Field(default_factory=list)
    competencies: dict[str, CompetencyNode] = Field(default_factory=dict)
    research_sources: list[ResearchSource] = Field(default_factory=list)

class SessionState(BaseModel):
    goal: Optional[str] = None
    obstacle: Optional[str] = None
    context: Optional[str] = None
    focus: Optional[str] = None
    mode: str = "diagnostic"
    stage: str = "start"
    turn_count: int = 0

class AgentState(BaseModel):
    learner: LearnerProfile = Field(default_factory=LearnerProfile)
    current_session: SessionState = Field(default_factory=SessionState)
    history: list[dict[str, str]] = Field(default_factory=list)
    last_route: Optional[RouteDecision] = None
    last_decision: Optional[AgentDecision] = None
