# Pluto Finance Monthly Close Plan

Status: ACTIVE
Last updated: 2026-04-25
Owner: Pluto Finance

## Summary

Pluto Finance will narrow to one product:

> A local-first monthly finance close for one person or one household.

The product should answer four questions quickly and credibly:

1. What changed this month?
2. Where is money leaking?
3. What should I do next?
4. Am I getting better over time?

This plan turns the earlier CEO review into a concrete execution path.

## Product Bet

The current app already has the right raw ingredients:

- deterministic spend summaries in `src/web/transaction_insights.py`
- month-level breakdowns in `src/web/app.py` + `src/web/templates/monthly_spend.html`
- recurring-charge heuristics in `src/web/subscription_finder.py`
- local CSV/Plaid ingestion in `src/web/app.py`

What is missing is product focus. The app currently mixes:

- local-first finance analysis
- a future hosted-service pitch
- Apple Health analysis
- model/provider controls exposed directly to end users

This plan keeps the finance wedge and removes the rest from the core surface.

## Target User

Primary user:

- an individual who reviews spending manually today
- wants better clarity, not a complex budgeting system
- cares about privacy and prefers local or explicit cloud usage

Core job to be done:

- "At the end of the month, show me what changed, what matters, and what action is worth taking."

## V1 Outcome

Ship a finance experience centered on a monthly close.

The user flow should be:

```text
Connect bank or upload CSV
        |
        v
Load recent transactions
        |
        v
Build deterministic monthly summary
        |
        +--> month-over-month change
        +--> merchant concentration
        +--> recurring charge watchlist
        +--> clear next action
        |
        v
Render one trustworthy "monthly close" surface
```

## In Scope

### 1. Monthly Close Homepage

Repurpose the current Insights page into a monthly close page.

It should show:

- current month total spend
- previous month comparison
- biggest increase or spike
- top merchants/categories
- recurring charges worth reviewing
- one primary recommended action

Existing code to reuse:

- `build_transaction_summary()` in `src/web/transaction_insights.py`
- `build_monthly_spend_summary()` in `src/web/transaction_insights.py`
- `/api/monthly-spend` in `src/web/app.py`

### 2. Recurring Charge Watchlist

Turn subscription detection into a first-class product surface instead of a side panel.

It should support:

- list of recurring merchants
- confidence and estimated monthly cost
- "watch", "review", or "ignore" status stored locally
- explanation of why each merchant was flagged

Existing code to reuse:

- `identify_subscriptions()` in `src/web/subscription_finder.py`

### 3. Trust and Provenance

Make privacy and processing location explicit on every analysis surface.

The user should always know:

- whether analysis ran locally or used OpenAI
- whether the result is deterministic or LLM-generated
- what data range was analyzed
- whether the dataset was truncated

### 4. Hardening the Finance Pipeline

Fix the critical correctness issues before adding new UX.

Must-fix items:

- do not delete cached transaction files after normal requests
- return API failure when finance-tip generation fails
- require explicit user opt-in before using OpenAI
- surface truncation clearly when only part of the dataset was analyzed

## Not In Scope

- Apple Health as a core tab: different product wedge and trust model
- hosted-service waitlist or "we handle everything" messaging: premature until the local-first promise is stable
- broad AI playground controls: wrong abstraction for the main user
- multi-user households with shared accounts: possible later, not needed for v1
- budgeting, goal tracking, and bill-pay workflows: separate products
- any server-side database: keep this phase local-first and file-based

## Existing Flows To Reuse

### Data Loading

- `load_transactions_from_request()` in `src/web/app.py`
- `parse_csv_transactions()` in `src/web/utils.py`
- `parse_transaction_file()` in `src/web/app.py`

Decision:

- reuse this ingestion layer
- do not build a second transaction-loading path

### Deterministic Finance Summaries

- `build_transaction_summary()` in `src/web/transaction_insights.py`
- `build_monthly_spend_summary()` in `src/web/transaction_insights.py`

Decision:

- use deterministic summaries as the primary product engine
- layer LLM advice on top only when explicitly enabled

### Monthly Breakdown UI

- `src/web/templates/monthly_spend.html`

Decision:

- keep this page as the drill-down surface
- do not make it the primary landing page

### Plaid + CSV Entry

- `src/web/templates/plaid_link.html`
- current CSV upload controls in `finance_tip.html` and `monthly_spend.html`

Decision:

- keep both entry paths
- standardize the copy and state handling

## Proposed Architecture

Keep Flask and the current local-first model. Restructure the web layer so the finance product is easier to reason about.

```text
src/web/app.py
    |
    +--> request parsing / security / route registration
    |
    +--> finance service layer
            |
            +--> transaction loading
            +--> deterministic summaries
            +--> recurring watchlist
            +--> optional LLM advice
```

### Refactor Targets

1. Extract finance route helpers from `src/web/app.py` into smaller modules.
2. Centralize provider selection logic so "local vs OpenAI" is explicit and testable.
3. Separate deterministic analysis from optional LLM enrichment.
4. Add a local persistence file for recurring-watchlist decisions if needed.

Suggested modules:

- `src/web/services/transaction_loader.py`
- `src/web/services/finance_summary.py`
- `src/web/services/provider_selection.py`
- `src/web/services/watchlist_state.py`

This can happen incrementally. The first milestone should fix correctness bugs before any broad file moves.

## Milestones

### Phase 0: Hardening

Goal:

- make the current finance pipeline trustworthy

Tasks:

- fix cached-file deletion in `src/web/app.py`
- fix `/api/finance-tip` success contract
- make OpenAI opt-in explicit in `src/web/llms.py`
- add dataset truncation messaging to finance insights
- add route-level tests for `/api/finance-tip` and `/api/monthly-spend`

Exit criteria:

- repeated requests do not lose cached transaction history
- failed finance-tip generation returns a visible error
- local processing stays local unless the user explicitly opts in

### Phase 1: Monthly Close Surface

Goal:

- replace the current generic insights page with a real monthly close homepage

Tasks:

- redesign `src/web/templates/finance_tip.html` around monthly close
- reuse deterministic summary data before LLM copy
- remove hosted-service waitlist messaging from the main finance flow
- move provider controls behind an advanced or explicit toggle

Exit criteria:

- the landing page answers what changed, what matters, and what to do next without requiring the LLM path

### Phase 2: Recurring Watchlist

Goal:

- make recurring charge review part of the core product loop

Tasks:

- promote subscription findings into a dedicated section or page
- add local user actions: watch, ignore, reviewed
- explain confidence and reason text clearly
- connect monthly close recommendations to watchlist items

Exit criteria:

- a user can review recurring merchants and understand why each one was flagged

### Phase 3: Trust, Provenance, and Polish

Goal:

- make the product feel credible and calm rather than experimental

Tasks:

- add explicit provenance badges to analysis cards
- standardize local/cloud copy across all finance pages
- demote or remove debug surfaces from the default view
- align all finance pages to one visual system and navigation hierarchy

Exit criteria:

- the default user flow feels like a product, not a builder console

## Implementation Sequence

1. Phase 0 hardening
2. Phase 1 monthly close homepage
3. Phase 2 recurring watchlist
4. Phase 3 provenance and polish

Do not reverse this order. New UX on top of silent finance errors will just make a more polished bug.

## Concrete File Plan

### Backend

- `src/web/app.py`
  - fix request lifecycle and endpoint contracts
  - keep routes thin over time
- `src/web/transaction_insights.py`
  - remain source of truth for deterministic summaries
- `src/web/subscription_finder.py`
  - remain source of truth for recurring detection heuristics
- `src/web/llms.py`
  - enforce explicit provider selection

### Frontend

- `src/web/templates/finance_tip.html`
  - becomes the monthly close landing page
- `src/web/templates/monthly_spend.html`
  - remains drill-down analysis
- `src/web/templates/plaid_link.html`
  - remains onboarding entry point
- `src/web/templates/apple_health.html`
  - remove from primary finance navigation in this phase

### Tests

- add route tests for finance APIs
- add regression tests for file lifecycle
- add tests for provider selection behavior
- add tests for truncation warnings and error propagation

## Success Metrics

Product metrics:

- user can complete a monthly close from fresh data in under 2 minutes
- user sees one primary recommended action on every successful run
- recurring-charge review requires no debug table

Engineering metrics:

- finance routes have route-level tests
- no silent fallback on LLM failure
- no accidental cloud routing
- no cached-data deletion after read-only requests

## Open Questions

1. Should recurring-watchlist state be saved in a local JSON file, session storage, or not persisted at all in v1?
2. Should the Apple Health feature be hidden entirely or simply moved out of the default navigation?
3. Should finance-tip remain a separate endpoint, or should it become enrichment on top of monthly-close data?

## First Build Slice

If work starts today, the first PR should do only this:

1. Fix cached transaction deletion.
2. Fix finance-tip error handling.
3. Make OpenAI opt-in explicit.
4. Add route-level tests covering those three contracts.

That is the right first slice because it improves trust, correctness, and product integrity without expanding scope.
