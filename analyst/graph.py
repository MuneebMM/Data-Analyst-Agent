"""Five-node LangGraph with a bounded repair loop."""
from __future__ import annotations

import logging
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from . import llm
from .models import AgentState, DatasetProfile, PlanOutput
from .skills import run_code_safely

log = logging.getLogger(__name__)


def planner(state: AgentState) -> dict:
    log.info("Planner: making analysis steps")
    provider = llm.provider_name(state.get("provider"))
    output = llm.plan(state["question"], DatasetProfile.model_validate(state["profile"]), provider, state.get("api_key", ""))
    return {"plan": output.model_dump(), "provider": provider}


def coder(state: AgentState) -> dict:
    log.info("Coder: writing pandas code")
    output = llm.code(state["question"], DatasetProfile.model_validate(state["profile"]), PlanOutput.model_validate(state["plan"]), state["provider"], state.get("api_key", ""))
    return {"code": output.code}


def executor(state: AgentState) -> dict:
    attempt = state.get("attempts", 0) + 1
    log.info("Executor: attempt %s/3", attempt)
    outcome = run_code_safely(state["code"], Path(state["csv_path"]), Path(state["work_dir"]) / f"attempt_{attempt}")
    # A requested chart is part of the answer, so missing output triggers repair.
    if outcome.ok and state["plan"]["chart_wanted"] and not outcome.chart_paths:
        outcome.ok = False
        outcome.error = "The question requested a chart, but the code did not create a matplotlib figure."
    return {"attempts": attempt, "retries": attempt - 1, "error": outcome.error, "result": outcome.result, "chart_path": outcome.chart_path, "chart_paths": outcome.chart_paths}


def debugger(state: AgentState) -> dict:
    log.info("Debugger: repairing error: %s", state["error"].splitlines()[-1])
    output = llm.debug(state["code"], state["error"], DatasetProfile.model_validate(state["profile"]), state["question"], PlanOutput.model_validate(state["plan"]), state["provider"], state.get("api_key", ""))
    return {"code": output.code}


def responder(state: AgentState) -> dict:
    log.info("Responder: preparing answer")
    return {"answer": llm.respond(state["question"], state.get("result", ""), state.get("error", ""), state["provider"], state.get("api_key", "")).answer}


def route_after_execution(state: AgentState) -> str:
    return "debugger" if state.get("error") and state.get("attempts", 0) < 3 else "responder"


builder = StateGraph(AgentState)
builder.add_node("planner", planner)
builder.add_node("coder", coder)
builder.add_node("executor", executor)
builder.add_node("debugger", debugger)
builder.add_node("responder", responder)
builder.add_edge(START, "planner")
builder.add_edge("planner", "coder")
builder.add_edge("coder", "executor")
builder.add_conditional_edges("executor", route_after_execution, {"debugger": "debugger", "responder": "responder"})
builder.add_edge("debugger", "executor")
builder.add_edge("responder", END)
graph = builder.compile()
