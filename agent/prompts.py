from __future__ import annotations
import json

ROLES = {
    "tutor": "Teach, scaffold, explain, and design targeted practice.",
    "linguist": "Analyze Brazilian Portuguese grammar, sound system, syntax, semantics, pragmatics, and variation.",
    "conversation": "Run realistic interaction and prioritize communicative success and delayed correction.",
    "culture": "Explain Brazilian cultural, historical, regional, and sociolinguistic context without stereotypes.",
    "assessor": "Assess only demonstrated evidence and record CEFR-domain evidence conservatively."
}

def route_prompt(agent_md, state):
    return agent_md + "\n\nYou are the routing manager. Return only RouteDecision JSON.\nCURRENT STATE:\n" + json.dumps(state, ensure_ascii=False, indent=2)

def specialist_prompt(agent_md, state, route):
    roles = "\n".join(f"- {r}: {ROLES[r]}" for r in route["specialists"])
    return (
        agent_md
        + "\n\nYou are the specialist team supporting the Master Agent.\n"
        + roles
        + "\n\nROUTE:\n"
        + json.dumps(route, ensure_ascii=False, indent=2)
        + "\n\nCURRENT STATE:\n"
        + json.dumps(state, ensure_ascii=False, indent=2)
        + "\n\nReturn exactly one AgentDecision JSON. "
          "The response field is learner-facing. Evidence must be grounded in the current turn."
    )
