# Déjà Vu v2: Architecture Delta (Decoupling & Visuals)

*Authored by: Rama*
*Purpose: To define the architectural delta required to decouple strategy logic from model states, push state selection to execution time, and upgrade terminal visualization to an annotated HLC chart.*

## 1. Domain Model Delta: The Decoupling

**Previous Architecture:** A Strategy was tightly coupled to a specific model state. A rule was defined as: "If State == 'Bullish' AND Price > VWAP -> Long". 
**New Architecture:** A Strategy is now a pure, state-agnostic collection of technical conditions (e.g., "Price > VWAP", "Relative Volume > 2"). The "Regime State" acts as the *Execution Context* applied only at backtest time.

*   **Strategy Entity:** Contains only indicator/price logic. It does not know about HMMs, RNNs, or their states.
*   **Backtest Contract:** `Backtest = Strategy(Data) INTERSECT Context(Model, State)`. A backtest evaluates if the strategy's conditions are met *while* the market is in the target state.

## 2. Module Interface Changes

### 2.1 `dejavu/strategy/builder.py`
*   **Contract Change:** Remove all state-parsing logic. The parser now exclusively evaluates standard technical rules.
*   **Input:** `["close > vwap", "rel_vol > 1.5"]`
*   **Output:** Vectorized Pandas boolean mask representing pure technical signal (`tech_entries`).

### 2.2 `dejavu/strategy/engine.py` (The Backtest Runner)
*   **Contract Change:** `run_backtest()` signature updated.
    *   *Old:* `run_backtest(strategy, features)`
    *   *New:* `run_backtest(strategy, features, model_states_series, target_state_label)`
*   **Execution Logic:** 
    1. Evaluate `tech_entries = strategy.evaluate(features)`.
    2. Evaluate `regime_mask = (model_states_series == target_state_label)`.
    3. Final Signal: `entries = tech_entries & regime_mask`.
    4. Apply zero-fees, no-overnight rules as before via `vectorbt`.
    5. Return `BacktestResult` object, now including the exact index timestamps of executed trades (to feed the new chart module).

### 2.3 `dejavu/shell.py` (The REPL)
*   **Command Re-routing:**
    *   *Remove:* `strategy add trigger --state [X]`
    *   *Update:* `backtest [strategy_name]` -> `backtest [strategy_name] --model [hmm|ar|rnn] --state [target_state]`
    *   *Add:* Context awareness. If an active model and state are set in the session, the `backtest` command can implicitly use them if flags are omitted.

## 3. Visuals: The HLC Chart Contract (`dejavu/ui/charts.py`)

The terminal visualization must condense Price Action, Market Regime, and Trade Execution into a single dense view using the `Rich` library.

### 3.1 `render_annotated_hlc()`
*   **Inputs:** `df` (OHLCV features), `states` (Pandas Series of labels), `trades` (List of entry/exit timestamps/prices - optional).
*   **Construction Steps:**
    1.  **Price Geometry (HLC):** Map the continuous price data to discrete terminal rows/columns. Use Unicode drawing characters for High/Low bars (e.g., `│`) and Close ticks (e.g., `-`).
    2.  **Background Regimes:** Map the `states` series to `Rich` background colors (e.g., `bgcolor="dark_green"` for Bullish, `bgcolor="dark_red"` for Bearish). Apply this color to the full height of the terminal column corresponding to that bar.
    3.  **Trade Markers:** Iterate over `trades`. At the specific row/col intersection of an executed trade, overwrite the HLC character with an explicit marker:
        *   `▲` (bold bright green) for Long Entry.
        *   `▼` (bold bright red) for Exit / Short.
*   **Constraints:** Terminal width is typically 80-120 characters. The chart must automatically downsample the `df` to fit the current `shutil.get_terminal_size()`, picking the most representative HLC values per visual column.

## 4. Command Flow Migration Plan

**Old Workflow (Deprecated):**
```bash
> model hmm --states 3
> strategy new alpha
> strategy add trigger --state Bullish
> strategy add condition close > vwap
> backtest alpha
> chart --equity
```

**New Workflow (Delta Applied):**
```bash
> strategy new alpha
> strategy add condition close > vwap
> model hmm --states 3
> backtest alpha --model hmm --state Bullish
> chart --annotated   # Renders the unified HLC+Regime+Trades view
```

## 5. Implementation Sequence for Neo

Neo, execute this delta in the following order to ensure structural integrity:

### Milestone 1: Domain Decoupling
*   **Task:** Strip state awareness from `strategy/builder.py` and the `strategy create` CLI commands.
*   **Acceptance:** User can build a strategy comprising only technical indicators. Strategy object saves without any model reference.

### Milestone 2: Execution Context Injection
*   **Task:** Modify `engine.py` and `shell.py`. Update the `backtest` command to require/accept `--model` and `--state` arguments. Intersect the technical mask with the regime mask.
*   **Acceptance:** `backtest alpha --model hmm --state Choppy` correctly filters trades, ensuring entries only occur during the 'Choppy' regime.

### Milestone 3: The Unified HLC Chart
*   **Task:** Implement `render_annotated_hlc()` in `ui/charts.py`. Handle downsampling, HLC Unicode mapping, Rich background coloring by state, and overlaying `▲`/`▼` markers. Add `chart --annotated` command.
*   **Acceptance:** Operator executes backtest, then runs `chart --annotated`. Terminal prints a color-coded background corresponding to HMM states, with clear vertical HLC lines and visible trade execution markers.