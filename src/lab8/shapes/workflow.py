"""Shape A — deterministic workflow. Student work.

Signature (do not change):

    run_claim(claim_id, *, seed, store_path, crash_at=None) -> RunResult

Fixed steps, all in Python. Money stays in code (`lab8.tools.compute_compensation`).

1. Open the store. Read the claim through `get_claim_view` (not SELECT *).
2. Missing order_id -> `needs_info`. The ledger is not touched.
3. `lookup_order`. Not visible -> `escalated`. Only allowlisted order fields are kept.
4. Quote from the order row. Delay numbers written in the ticket are never read.
5. Quote 0 -> `denied`, no call to issue_refund.
6. Quote > 0 -> `durability.issue_refund(conn, claim_id, <full quote>)`. The host checks
   approval and the per-order cap (T13, T14) and writes `policy_denied` when it refuses.
7. MockLLM is used once, to draft the reply. It never sees or chooses the amount to write.

Trace contract v1: every return path goes through `finish()`, which writes the trace.
The trace never holds the ticket, the principal, the claim row or the raw order row.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import compute_compensation, get_claim_view, lookup_order, tool_cost
from lab8.trace import Trace

SHAPE = "workflow"

# Order fields that may appear in the trace. No free-text field is copied.
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
        # The model only drafts the reply text. The prompt carries the status, nothing else.
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

    # Step 1 — claim view (allowlisted columns only).
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    trace.add("claim_view", {"found": bool(claim.get("found")), "has_order_id": bool(claim.get("order_id"))})
    if not claim.get("found"):
        return done("failed", 0, "unknown_claim")

    # Step 2 — no order id on the claim. The ticket text is not searched for one.
    if not claim.get("order_id"):
        return done("needs_info", 0, "missing_order_id")

    # Step 3 — order lookup, scoped to the claim's principal.
    budget.add_tool(tool_cost())
    order_view = lookup_order(conn, claim["order_id"], claim["principal_id"])
    if not order_view.get("visible"):
        trace.add("order_lookup", {"visible": False, "reason": order_view.get("reason")})
        return done("escalated", 0, order_view.get("reason"))
    order = order_view["order"]
    trace.add("order_lookup", {"visible": True, "order": _order_for_trace(order)})

    # Step 4 — quote from the order row and the current policy.
    budget.add_tool(tool_cost())
    quote = compute_compensation(conn, order)
    proposal = int(quote["amount_vnd"])
    trace.add("quote", _quote_for_trace(quote))

    # Step 5 — nothing owed: the shape denies and the host is not called.
    if proposal <= 0:
        return done("denied", 0, quote.get("reason"))

    # Step 6 — the host gate. Full quote in, crash_at forwarded, InjectedCrash not caught.
    outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    trace.add("host_refund", _outcome_for_trace(outcome))
    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)


def _order_for_trace(order: dict[str, Any]) -> dict[str, Any]:
    return {key: order[key] for key in _TRACE_ORDER_FIELDS if key in order}


def _quote_for_trace(quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "amount_vnd": int(quote["amount_vnd"]),
        "reason": quote.get("reason"),
        "clause_ids": list(quote.get("clause_ids") or []),
    }


def _outcome_for_trace(outcome: dict[str, Any]) -> dict[str, Any]:
    effect = outcome.get("effect") or {}
    return {
        "ok": bool(outcome["ok"]),
        "reason": outcome["reason"],
        "conflict": bool(outcome["conflict"]),
        "committed_vnd": effect.get("amount_vnd"),
    }


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
