"""Shape C — orchestrator plus read-only investigators. Student work.

The orchestrator plans, hands two narrow tasks to investigators, then decides in code.

1. `order_facts` investigator: handoff with no facts, tools `lookup_order` and
   `lookup_refund_history`.
2. `check_applicable_policy` investigator: handoff whose facts are the allowlisted
   order fields from step 1, tool `lookup_policy`.
3. The orchestrator quotes from the investigator's order view with
   `compute_compensation` and calls `durability.issue_refund` with the FULL quote.
   The host subtracts earlier refunds on the same order (T13, T14).

Both handoffs come from `lab8.handoff.make_handoff`: allowlisted fields, read-only
tools, and a refusal if a canary survives. The ticket, the principal, parent_secret
and the headers never enter a handoff. Investigators have no write registry.

Trace contract v1: every return path goes through `finish()`. The trace holds the
sanitized handoffs and allowlisted results, never the parent context.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import HandoffError, make_handoff
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import compute_compensation, get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"

# handoff.FACT_KEYS name -> field of the allowlisted order view. `carrier` is allowed by
# the contract but left out: the policy check does not need it (least privilege).
_FACT_SOURCES = {
    "delay_days": "delay_days",
    "damage_verified": "damage_verified",
    "order_status": "status",
    "shipping_fee_vnd": "shipping_fee_vnd",
    "paid_vnd": "paid_vnd",
}


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
        complete(budget, seed=seed, purpose="draft", prompt=f"status={status}")
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

    # Parent context: stays inside the orchestrator. Only allowlisted columns are read.
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    trace.add("claim_view", {"found": bool(claim.get("found")), "has_order_id": bool(claim.get("order_id"))})
    if not claim.get("found"):
        return done("failed", 0, "unknown_claim")

    # The orchestrator reads the ticket to plan. The plan never changes the money.
    complete(budget, seed=seed, purpose="plan", prompt=claim["ticket"])
    if not claim.get("order_id"):
        return done("needs_info", 0, "missing_order_id")
    trace.add("plan", {"investigators": ["order_facts", "check_applicable_policy"]})

    try:
        # Investigator 1 — order facts and refund history.
        order_report = _investigate(
            conn,
            budget,
            trace,
            seed=seed,
            claim=claim,
            task="order_facts",
            facts={},
            tools=["lookup_order", "lookup_refund_history"],
        )
        order_view = order_report.get("lookup_order") or {}
        if not order_view.get("visible"):
            trace.add("investigator", {"task": "order_facts", "visible": False, "reason": order_view.get("reason")})
            return done("escalated", 0, order_view.get("reason"))
        order = order_view["order"]
        history = order_report.get("lookup_refund_history") or {}
        trace.add(
            "investigator",
            {
                "task": "order_facts",
                "visible": True,
                "refund_count": history.get("refund_count"),
                "refunded_vnd": history.get("refunded_vnd"),
            },
        )

        # Investigator 2 — which policy applies. It gets allowlisted order facts only.
        facts = {fact: order[source] for fact, source in _FACT_SOURCES.items() if source in order}
        policy_report = _investigate(
            conn,
            budget,
            trace,
            seed=seed,
            claim=claim,
            task="check_applicable_policy",
            facts=facts,
            tools=["lookup_policy"],
        )
    except (HandoffError, ToolRejected) as exc:
        # A handoff that would carry a secret or a write tool is refused, not forwarded.
        return done("failed", 0, f"handoff_rejected:{type(exc).__name__}")
    policies = (policy_report.get("lookup_policy") or {}).get("policies") or []
    trace.add(
        "investigator",
        {"task": "check_applicable_policy", "current_policy_ids": [policy["policy_id"] for policy in policies]},
    )

    # The orchestrator owns the quote: code, from the investigator's order view.
    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order)
    proposal = int(quote["amount_vnd"])
    trace.add(
        "quote",
        {"amount_vnd": proposal, "reason": quote.get("reason"), "clause_ids": list(quote.get("clause_ids") or [])},
    )
    if proposal <= 0:
        return done("denied", 0, quote.get("reason"))

    # Only the orchestrator reaches the host gate. Full quote in, crash_at forwarded,
    # InjectedCrash not caught.
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


def _investigate(
    conn: sqlite3.Connection,
    budget: Budget,
    trace: Trace,
    *,
    seed: int,
    claim: dict[str, Any],
    task: str,
    facts: dict[str, Any],
    tools: list[str],
) -> dict[str, Any]:
    """Run one read-only investigator on a sanitized handoff. Returns its tool results."""
    handoff = make_handoff(
        request_id=f"REQ-{claim['claim_id']}-{task}",
        claim_id=claim["claim_id"],
        task=task,
        facts=facts,
        allowed_tools=tools,
    )
    trace.add("handoff", safe_dump(handoff))
    report = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
    # One model call per investigator, so the cost of delegating shows up in the benchmark.
    complete(budget, seed=seed, purpose="investigate", prompt=f"task={task} tools={','.join(tools)}")
    return report["tools"]


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
