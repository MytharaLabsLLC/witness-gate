"""Framework adapters: the Gate inside the stacks agents already run on.

The HTTP service and the MCP server make the Gate reachable from any
stack. These adapters make it native in the three frameworks agent
builders reach for first, without adding a dependency: this package
stays standard-library only, and each adapter is a thin shape around
Gate.check that the framework adopts with one line.

LangGraph:

    from soul_cradle.adapters import langgraph_node
    graph.add_node("witness_gate", langgraph_node(gate))
    # state in:  {"action": str, "evidence": dict}
    # state out: + {"verdict": str, "gate_result": dict, "held": bool}
    # a blocked verdict raises GateBlocked, which LangGraph surfaces
    # as a node error: the action does not proceed.

CrewAI:

    from soul_cradle.adapters import crewai_tool
    agent = Agent(tools=[crewai_tool(gate)], ...)
    # the tool takes (action, evidence_json) and returns the verdict
    # as a JSON string the crew can read.

OpenAI Agents SDK (and any OpenAI-style function caller):

    from soul_cradle.adapters import openai_function_tool
    definition, handler = openai_function_tool(gate)
    # definition is the {"type": "function", ...} tool schema;
    # handler(arguments_dict) -> verdict JSON string.
    # With the Agents SDK: FunctionTool(name=..., description=...,
    #   params_json_schema=definition["function"]["parameters"],
    #   on_invoke_tool=lambda ctx, args: handler(json.loads(args)))

Enforcement matches the Python API everywhere: clear proceeds,
flagged and contested are returned for a human (or the on_hold
callback) to decide, blocked raises or reports refusal. No adapter
turns a block into a pass.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Tuple

from .plug import Gate, GateBlocked

_PARAMETERS = {
    "type": "object",
    "properties": {
        "action": {"type": "string",
                   "description": "What the agent proposes to do."},
        "evidence": {"type": "object",
                     "description": "Observable facts about the action: "
                                    "principal_consent, fully_disclosed, "
                                    "reversible, deception_involved, ..."},
    },
    "required": ["action"],
}

_DESCRIPTION = (
    "Put a proposed agent action before the eight Witness Gate "
    "assessors BEFORE carrying it out. Returns the panel verdict: "
    "clear (proceed), flagged (hold for a human), contested (the "
    "witnesses disagree; dissent preserved, a human decides), or "
    "blocked (a critical finding; refuse the action, no override)."
)


def langgraph_node(gate: Gate) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    """A LangGraph node: reads state['action'], writes the verdict back."""

    def witness_gate_node(state: Dict[str, Any]) -> Dict[str, Any]:
        action = state.get("action")
        if not isinstance(action, str):
            raise ValueError("state must carry an 'action' string")
        evidence = state.get("evidence") or {}
        result = gate.check(action, evidence)
        if result.verdict == "blocked":
            raise GateBlocked(result, action)
        return {
            "verdict": result.verdict,
            "gate_result": result.to_dict(),
            "held": result.verdict in ("flagged", "contested"),
        }

    return witness_gate_node


def crewai_tool(gate: Gate) -> Callable[..., str]:
    """A plain callable CrewAI can adopt as a tool.

    Pass it in an Agent's tools list (CrewAI wraps plain callables),
    or wrap it with crewai's @tool decorator at the call site. Returns
    the verdict as a JSON string.
    """

    def witness_gate(action: str, evidence_json: str = "") -> str:
        """Ask the Witness Gate to judge an action before doing it."""
        evidence = json.loads(evidence_json) if evidence_json else {}
        result = gate.check(action, evidence)
        return json.dumps(result.to_dict())

    witness_gate.__name__ = "witness_gate"
    return witness_gate


def openai_function_tool(gate: Gate) -> Tuple[Dict[str, Any],
                                              Callable[[Dict[str, Any]], str]]:
    """An OpenAI-style function tool: (definition, handler).

    The definition drops into any tools=[...] list that speaks the
    OpenAI function format. The handler takes the parsed arguments
    dict and returns the verdict as a JSON string.
    """
    definition = {
        "type": "function",
        "function": {
            "name": "witness_gate_assess",
            "description": _DESCRIPTION,
            "parameters": _PARAMETERS,
        },
    }

    def handler(arguments: Dict[str, Any]) -> str:
        action = arguments.get("action")
        if not isinstance(action, str):
            return json.dumps({"error": "action must be a string"})
        evidence = arguments.get("evidence") or {}
        result = gate.check(action, evidence)
        return json.dumps(result.to_dict())

    return definition, handler
