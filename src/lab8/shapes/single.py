"""Shape B — one ReAct agent. Student work.

The agent loop is `lab8.runtime.run_react` with max_steps=8. `decide` plays the model:
each step costs one MockLLM call and picks one read tool, or stops with a final.
The model never calls `issue_refund` (the runtime rejects write tools) and its final
carries only a suggested status and amount.

After the loop the code takes over:

- it reads the order view the runtime returned, never the ticket;
- it recomputes the quote with `compute_compensation` and uses that number. A final
  from the model that disagrees is recorded as `model_final_overruled` and dropped;
- it calls `durability.issue_refund` with the FULL quote. The host subtracts earlier
  refunds on the same order (T13, T14), so the history the agent read is context only.

Caps: 8 steps. Every model call goes through the Budget so cost stays comparable.

Trace contract v1: every return path goes through `finish()`. The trace never holds
the ticket, the principal, the claim row or the raw order row.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete, parse_delay_days
from lab8.runtime import ToolRejected, dispatch, run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8

_TRACE_ORDER_FIELDS = ("status", "delay_days", "shipping_fee_vnd", "paid_vnd", "damage_verified")


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at, budget=budget, trace=trace)
    except InjectedCrash:
        # CP3: the crash must reach the caller. Flush the trace so the run stays auditable.
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    except Exception as exc:  # noqa: BLE001 — run_claim must not raise (docs/contracts.md)
        return _internal_error(conn, claim_id, seed, budget, trace, exc)
    finally:
        conn.close()


def _run(
    conn: sqlite3.Connection,
    claim_id: str,
    *,
    seed: int,
    crash_at: str | None,
    budget: Budget,
    trace: Trace,
) -> RunResult:
    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": proposal, "reason": reason})
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status=status,
            proposal_amount=proposal,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )

    claim = dispatch(conn, budget, "get_claim_view", {"claim_id": claim_id}, worker=True)
    trace.add("claim_view", {"found": bool(claim.get("found")), "has_order_id": bool(claim.get("order_id"))})
    if not claim.get("found"):
        return done("failed", 0, "unknown_claim")

    # What the tools returned, kept by the code. The model's final is checked against it.
    seen: dict[str, Any] = {}

    def decide(observation: dict[str, Any]) -> dict[str, Any]:
        last_tool = observation.get("last_tool")
        if last_tool:
            seen[last_tool] = observation["last_result"]
        step = len(seen) + 1
        if not seen:
            # First thought: the model reads the ticket. What it says is a hint, not a fact.
            complete(budget, seed=seed, purpose="parse", prompt=claim["ticket"])
            claimed = parse_delay_days(claim["ticket"])
            trace.add("thought", {"step": step, "ticket_states_delay": claimed is not None})
        else:
            complete(budget, seed=seed, purpose="react", prompt=f"step={step} after={last_tool}")

        if not claim.get("order_id"):
            return _final(trace, step, "needs_info", 0)
        scope = {"order_id": claim["order_id"], "principal_id": claim["principal_id"]}
        if "lookup_order" not in seen:
            return _act(trace, step, "lookup_order", scope)
        order_view = seen["lookup_order"]
        if not order_view.get("visible"):
            return _final(trace, step, "escalated", 0)
        if "lookup_refund_history" not in seen:
            return _act(trace, step, "lookup_refund_history", scope)
        if "compute_compensation" not in seen:
            return _act(trace, step, "compute_compensation", {"order": order_view["order"]})
        amount = int(seen["compute_compensation"]["amount_vnd"])
        return _final(trace, step, "propose_refund" if amount > 0 else "denied", amount)

    try:
        loop = run_react(conn, budget, observation={"claim": claim}, decide=decide, max_steps=MAX_STEPS)
    except ToolRejected:
        return done("failed", 0, "tool_rejected")
    if loop["stopped"] != "final":
        return done("failed", 0, "step_cap")
    model_final = loop["final"]

    # From here on the code decides. The checks below do not depend on the model's final.
    if not claim.get("order_id"):
        return done("needs_info", 0, "missing_order_id")
    order_view = seen.get("lookup_order")
    if order_view is None:
        return done("failed", 0, "agent_skipped_order_lookup")
    if not order_view.get("visible"):
        trace.add("order_lookup", {"visible": False, "reason": order_view.get("reason")})
        return done("escalated", 0, order_view.get("reason"))
    order = order_view["order"]
    trace.add("order_lookup", {"visible": True, "order": {k: order[k] for k in _TRACE_ORDER_FIELDS if k in order}})
    history = seen.get("lookup_refund_history") or {}
    if history.get("visible"):
        trace.add("refund_history", {"refund_count": history["refund_count"], "refunded_vnd": history["refunded_vnd"]})

    # Host-side validation: the quote is recomputed from the order row, not taken from the model.
    quote = dispatch(conn, budget, "compute_compensation", {"order": order}, worker=True)
    proposal = int(quote["amount_vnd"])
    trace.add(
        "quote",
        {"amount_vnd": proposal, "reason": quote.get("reason"), "clause_ids": list(quote.get("clause_ids") or [])},
    )
    if _as_int(model_final.get("amount_vnd")) != proposal:
        trace.add("model_final_overruled", {"used_amount_vnd": proposal})

    if proposal <= 0:
        return done("denied", 0, quote.get("reason"))

    # Full quote in, crash_at forwarded, InjectedCrash not caught.
    outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    effect = outcome.get("effect") or {}
    trace.add(
        "host_refund",
        {
            "ok": bool(outcome["ok"]),
            "reason": outcome["reason"],
            "conflict": bool(outcome["conflict"]),
            "committed_vnd": effect.get("amount_vnd"),
        },
    )
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)


def _act(trace: Trace, step: int, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    trace.add("action", {"step": step, "tool": tool})
    return {"tool": tool, "args": args}


def _final(trace: Trace, step: int, status: str, amount: int) -> dict[str, Any]:
    trace.add("final", {"step": step, "status": status, "amount_vnd": amount})
    return {"final": {"status": status, "amount_vnd": amount}}


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _internal_error(
    conn: sqlite3.Connection,
    claim_id: str,
    seed: int,
    budget: Budget,
    trace: Trace,
    exc: Exception,
) -> RunResult:
    """Unexpected failure: report `failed` with a valid trace. Only the exception type is logged."""
    reason = f"internal_error:{type(exc).__name__}"
    trace.add("error", {"reason": reason})
    try:
        return finish(
            conn,
            shape=SHAPE,
            claim_id=claim_id,
            seed=seed,
            status="failed",
            proposal_amount=0,
            budget=budget,
            trace=trace,
            error_reason=reason,
        )
    except Exception:  # noqa: BLE001 — the store itself is unreadable
        return RunResult(
            run_id=trace.run_id,
            claim_id=claim_id,
            shape=SHAPE,
            seed=seed,
            status="failed",
            proposal_amount=0,
            refund_effects=[],
            committed_audit_count=0,
            model_calls=budget.model_calls,
            tool_calls=budget.tool_calls,
            input_tokens=budget.input_tokens,
            output_tokens=budget.output_tokens,
            cost_estimate=round(budget.cost_estimate, 6),
            trace_path=trace.write(),
            error_reason=reason,
        )
