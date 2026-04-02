# Déjà Vu v2: Final System Architecture & Implementation Guide

*Authored by: Rama*
*Purpose: To provide the definitive, locked architectural blueprint and implementation sequence for the Déjà Vu v2 CLI. This document incorporates Frank's final directives and serves as the exact build specification for Neo.*

## 1. Locked Directives (Frank's Resolutions)

The following architectural decisions are now locked for the MVP:
1.  **Data Provider:** Strictly free data. **Alpaca IEX feed** is the primary source. If Alpaca fails or returns insufficient data, seamlessly fall back to **`yahooquery`**.
2.  **CLI Framework:** **`prompt_toolkit`**. The application will function as a rich, interactive REPL with custom auto-completion, syntax highlighting, and persistent bottom-toolbar status.
3.  **Backtest Execution:** **Zero slippage and zero commission.** The MVP focuses on pure mathematical signal validation.
4.  **Strategy Complexity:** **Multi-rule parser required.** Strategies must support complex boolean chaining (e.g., `(state == 'Bullish') AND (price > vwap) OR (rel_vol > 2.0)`).
5.  **State Naming:** **Heuristic Auto-labeling.** Raw integer states (0, 1, 2) must be automatically mapped to human-readable labels (e.g., "Bullish", "Bearish", "Choppy") based on their statistical properties.

---

## 2. Updated Module Contracts

Based on the locked directives, the following module contracts dictate exactly how components must be built and interact.

### 2.1 The REPL Shell (`dejavu/shell.py`)
*   **Framework:** Built entirely on `prompt_toolkit.PromptSession`.
*   **Contract:** Must implement a custom `Completer` that dynamically reads from the `SessionContext` (e.g., autocompleting cached tickers, available models, and saved strategies).
*   **UI:** Must utilize a bottom toolbar to constantly display `Active Symbol`, `Active Model`, and `Cache Status`.

### 2.2 Dual-Source Data Fetcher (`dejavu/data/fetcher.py`)
*   **Contract:** Implements a `fetch_bars(symbol, timeframe, lookback)` function with a strict fallback hierarchy.
*   **Primary (Alpaca IEX):** Attempt to fetch via `alpaca-py`. Ensure `extended_hours=True`.
*   **Fallback (`yahooquery`):** If Alpaca returns an error or empty DataFrame, instantly pivot to `yahooquery.Ticker(symbol).history(interval=timeframe)`. Note: Yahoo restricts intraday history (max 60 days for 1m/5m). The fetcher must warn the user if the requested lookback exceeds the provider's limit.
*   **Normalization:** Both sources must be normalized into a standard schema: `[timestamp, open, high, low, close, volume, session_type]`.

### 2.3 Model Auto-Labeling (`dejavu/models/base.py` & `hmm.py`)
*   **Contract:** After `train()` executes, an internal `_assign_labels()` method must run.
*   **Logic:** 
    1. Calculate the mean forward return and volatility for each hidden state over the training set.
    2. Sort the states heuristically. Example for 3 states:
       - Highest mean return -> `"Bullish"`
       - Lowest mean return -> `"Bearish"`
       - Middle mean return (or highest volatility) -> `"Choppy"`
*   **Output:** The `infer()` method now returns a Pandas Series of string labels, not integers.

### 2.4 Multi-Rule Strategy Builder (`dejavu/strategy/builder.py`)
*   **Contract:** Parses natural-language-like boolean expressions into vectorized Pandas masks.
*   **Implementation:** Must use Python's `ast.parse` or a robust `pyparsing` grammar to safely evaluate strings like `"state == 'Bullish' and close > vwap"`.
*   **Safety:** **Never use raw `eval()`**. Use `pandas.eval()` applied specifically to the context of the enriched features DataFrame, or manually traverse the AST to construct the boolean mask.

### 2.5 Zero-Friction Backtest Engine (`dejavu/strategy/engine.py`)
*   **Contract:** Wraps `vectorbt.Portfolio.from_signals()`.
*   **Enforcement 1 (No Overnight):** Must automatically inject the flat-at-close logic: `entries = entries & ~is_1559` and `exits = exits | is_1559`.
*   **Enforcement 2 (Zero Fees):** Must explicitly instantiate the portfolio with `fees=0.0` and `slippage=0.0`.

---

## 3. Implementation Sequence & Milestones (For Neo)

Neo, execute the build in this exact sequence. Do not proceed to the next milestone until the Acceptance Checks pass.

### Milestone 1: The REPL Core & Context
*   **Tasks:** Set up Poetry/Pip environment. Implement `config.py` (Pydantic), `context.py` (Session state), and the base `prompt_toolkit` loop in `shell.py`.
*   **Acceptance Check:** User can launch `dejavu`, type `quit` to exit, and see a bottom toolbar showing empty state. Tab completion works for basic commands (`use`, `model`, `strategy`).

### Milestone 2: Dual-Source Data Engine
*   **Tasks:** Implement `fetcher.py` (Alpaca -> yahooquery fallback) and `cache.py` (Parquet I/O). Implement `features.py` to calculate session-aware VWAP, rel_vol, and session highs/lows.
*   **Acceptance Check:** `use AAPL --range 5d --freq 5m` successfully fetches data, falls back if Alpaca lacks a key, writes to Parquet, and populates the `SessionContext` with enriched features.

### Milestone 3: The Oracle (Models & Labels)
*   **Tasks:** Implement `models/hmm.py` using `hmmlearn`. Implement the walk-forward inference loop. Implement the heuristic `_assign_labels()` logic based on state statistics.
*   **Acceptance Check:** `model hmm --states 3` trains instantly, applies "Bullish/Bearish" text labels, and `show summary` prints a Rich table validating the statistical logic.

### Milestone 4: Strategy Parser & Simulation
*   **Tasks:** Implement `builder.py` using `pandas.eval` or AST for multi-rule parsing. Implement `engine.py` using `vectorbt`, forcing the no-overnight rule and zero fees.
*   **Acceptance Check:** Operator creates strategy `(state == 'Bullish') and (close > vwap)`. `backtest [name]` runs without error and confirms 0 positions held across midnight boundaries.

### Milestone 5: Visuals & Polish
*   **Tasks:** Implement `ui/charts.py` and `ui/tables.py` using `Rich` for ASCII rendering of the equity curve and price/regime chart.
*   **Acceptance Check:** `show states` prints a beautiful terminal chart. `metrics --show` outputs a flawless table. System is ready for Frank's hands-on validation.