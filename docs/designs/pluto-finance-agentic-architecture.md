# Pluto Finance Agentic Architecture (Future TODO)

Status: PROPOSED (not implemented)  
Last updated: 2026-04-25  
Owner: Pluto Finance

## Purpose

Capture a concrete plan to evolve the current finance pipeline into an agentic architecture with clear role boundaries, traceable decisions, and deterministic bookkeeping.

This document is a future implementation TODO, not an active build plan yet.

## Why This Exists

Current behavior is strong but centralized:

- route handlers in `src/web/app.py` orchestrate too much logic directly
- deterministic rules and LLM calls are mixed in endpoint flows
- there is limited decision traceability per transaction

An agentic layout can improve:

- maintainability (smaller, focused modules)
- correctness auditing (explicit bucket decisions + reasons)
- extensibility (new financial analyses without route bloat)

## Principles

1. Deterministic math is source of truth for totals and ledger-like outputs.
2. LLM agents can enrich, but cannot silently override bookkeeping rules.
3. Every agent returns structured output with confidence and reasons.
4. Supervisor orchestration stays explicit and testable.
5. Keep local-first behavior by default; cloud usage remains opt-in.

## Proposed Agents

### 1) Ingestion Agent

Responsibilities:

- load transactions from CSV, fresh Plaid fetch, or cached file
- normalize required fields (`date`, `datetime`, `merchant/name`, `amount`, `account`)
- emit data quality summary

Primary existing logic to reuse:

- `load_transactions_from_request()` in `src/web/app.py`
- `parse_csv_transactions()` in `src/web/utils.py`
- `parse_transaction_file()` in `src/web/app.py`

### 2) Normalization Agent

Responsibilities:

- normalize merchant strings and account labels
- resolve outflow sign convention
- produce canonical transaction payload for downstream agents

Primary existing logic to reuse:

- `detect_outflow_sign()` in `src/web/transaction_insights.py`
- `merchant_text()` and normalization helpers in `src/web/transaction_insights.py`

### 3) Transaction Classification Agent

Responsibilities:

- classify transactions into category/subcategory/confidence
- use deterministic merchant rules where possible
- use LLM classification when enabled by caller

Primary existing logic to reuse:

- `categorize_transactions()` in `src/web/llms.py`

### 4) Bookkeeper Agent

Responsibilities:

- decide include/exclude for monthly spend and savings
- assign bucket per transaction:
  - `expense`
  - `savings`
  - `internal_move`
  - `inflow`
  - `savings_offset`
- compute monthly spend/savings totals from deterministic rules

Primary existing logic to reuse:

- `is_internal_money_move()` in `src/web/transaction_insights.py`
- `is_savings_allocation()` in `src/web/transaction_insights.py`
- `is_vanguard_sell_inflow()` in `src/web/transaction_insights.py`
- `build_monthly_spend_summary()` in `src/web/transaction_insights.py`

### 5) Subscription Agent

Responsibilities:

- identify recurring merchants and estimated monthly impact
- return confidence and evidence for recurring classification

Primary existing logic to reuse:

- `identify_subscriptions()` in `src/web/subscription_finder.py`

### 6) Insight Agent

Responsibilities:

- synthesize summaries and user-facing actions
- optionally call RAG query flow for question answering

Primary existing logic to reuse:

- `build_transaction_summary()` in `src/web/transaction_insights.py`
- `generate_finance_tip()` in `src/web/finance_tip.py`
- `TransactionRAGPipeline` in `src/web/transaction_rag.py`

### 7) QA/Audit Agent

Responsibilities:

- verify reconciliation and invariants before response
- flag low-confidence/high-impact decisions
- produce machine-readable warnings

Invariant examples:

- no transaction belongs to conflicting buckets
- `expense + savings + internal_move + inflow` decisions cover all analyzed records
- month totals equal the sum of included transaction amounts

## Orchestration Model

Use one Supervisor per request. Suggested flow:

1. Ingestion Agent
2. Normalization Agent
3. Parallel fan-out:
   - Transaction Classification Agent
   - Subscription Agent
4. Bookkeeper Agent
5. Insight Agent
6. QA/Audit Agent
7. Supervisor assembles final API response

## Shared Data Contract (Draft)

All agents read/write a shared `AnalysisContext` payload with versioning.

Minimum fields:

- `request_id`
- `analysis_window` (`lookback_days`, `selected_month`)
- `transactions_raw`
- `transactions_normalized`
- `classification_output`
- `bookkeeper_output`
- `subscription_output`
- `insight_output`
- `audit_output`
- `warnings`

Each agent result object should include:

- `agent_name`
- `success`
- `confidence` (`high|medium|low`)
- `reasons` (short list)
- `timing_ms`

## Suggested Code Shape (Future)

```text
src/web/agents/
  base.py
  context.py
  supervisor.py
  ingestion_agent.py
  normalization_agent.py
  classification_agent.py
  bookkeeper_agent.py
  subscription_agent.py
  insight_agent.py
  audit_agent.py

src/web/services/
  monthly_close_orchestrator.py
```

Routes in `src/web/app.py` should call orchestrator functions instead of embedding full business logic.

## Phased TODO Plan

### Phase 0: Scaffolding (no behavior changes)

- [ ] Add `agents/` package with base interfaces and context object
- [ ] Add supervisor skeleton and structured trace logging
- [ ] Keep current endpoints behavior-identical

### Phase 1: Monthly Spend Migration

- [ ] Move `/api/monthly-spend` internals behind supervisor
- [ ] Implement Bookkeeper Agent using existing deterministic helpers
- [ ] Add regression tests to verify parity with current endpoint outputs

### Phase 2: Classification + Subscriptions

- [ ] Implement Classification Agent wrapper over current LLM categorizer
- [ ] Implement Subscription Agent wrapper over `identify_subscriptions()`
- [ ] Add confidence + reason outputs for both

### Phase 3: Insights + Audit

- [ ] Implement Insight Agent wrapper for summary/tip flow
- [ ] Implement QA/Audit Agent invariants and warning model
- [ ] Add response `decision_trace` and `warnings`

### Phase 4: RAG Integration

- [ ] Add Query Agent path using `TransactionRAGPipeline`
- [ ] Enable supervisor-driven question answering with citations
- [ ] Add tests for citation and fallback behavior

## Acceptance Criteria for First Implementation Slice

For the first PR that starts this architecture:

1. `/api/monthly-spend` behavior is unchanged for existing test fixtures.
2. A structured per-agent trace is returned internally (or logged) for debugging.
3. Deterministic bookkeeping logic remains in control of totals.
4. Cloud model usage remains explicit opt-in.

## Risks and Mitigations

- Risk: Over-engineering before value is proven.  
  Mitigation: migrate one endpoint at a time with strict parity tests.

- Risk: LLM outputs drift and introduce inconsistencies.  
  Mitigation: keep Bookkeeper and Audit deterministic.

- Risk: Latency increases from extra orchestration.  
  Mitigation: run classification/subscription in parallel and cache stable transforms.

## Open Questions

1. Should agent traces be returned to UI, logs only, or toggled by debug mode?
2. Should user-configurable rule overrides exist for bookkeeping decisions?
3. Should long-running analyses be asynchronous with job IDs, or remain request/response?

## Start Here Later

When implementation begins, first do:

1. create `src/web/agents/base.py`, `context.py`, `supervisor.py`
2. wrap existing monthly spend logic into `bookkeeper_agent.py`
3. add parity tests for `/api/monthly-spend`

Then migrate additional agents incrementally.
