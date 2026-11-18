"""The AI workforce's agents and what each may do (Phase 8a, docs/plans/phase-8a-orchestrator.md).

An agent is a named worker bound to one job step and a closed list of actions. It acts only through the
existing deterministic services, which create `proposed` rows. No agent may approve, export, post or pay:
those stay human actions bound to a content hash (Part A rule 3).
"""

from __future__ import annotations

from dataclasses import dataclass

FORBIDDEN_ACTIONS = frozenset({"approve", "export", "post", "pay", "send"})


@dataclass(frozen=True)
class Agent:
    name: str
    steps: tuple[str, ...]
    label_fr: str
    actions: frozenset[str]


AGENTS: dict[str, Agent] = {
    # The document agent reads, then (in its own job, so reading is not held up) asks the AI for empty fields.
    "document": Agent("document", ("read_document", "ai_fill"), "Agent documents",
                      frozenset({"document.read", "document.ai_fill"})),
    "bookkeeping": Agent("bookkeeping", ("prepare_proposals",), "Agent comptable", frozenset({"proposal.draft"})),
    "reconciliation": Agent(
        "reconciliation", ("reconcile",), "Agent rapprochement", frozenset({"reconciliation.propose"})),
}

AGENT_FOR_STEP: dict[str, Agent] = {step: a for a in AGENTS.values() for step in a.steps}


class AgentPermissionError(PermissionError):
    """An agent tried an action outside its list."""


def require(agent: Agent, action: str) -> None:
    verb = action.rsplit(".", 1)[-1]
    if verb in FORBIDDEN_ACTIONS or action not in agent.actions:
        raise AgentPermissionError(f"l'agent {agent.name} n'est pas autorisé à « {action} »")
