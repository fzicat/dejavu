TASK_ID:   dejavu-cli-architecture-002
FROM:      rama
TO:        smith
TYPE:      deliverable
PRIORITY:  critical
CONTEXT:   System Architecture Blueprint synthesized from Frank's CLI concept and Morpheus's technical research.
PAYLOAD:   

# Déjà Vu v2: Interactive CLI System Architecture

*Authored by: Rama*
*Purpose: To architect a lightning-fast, terminal-first quantitative research workstation. Déjà Vu v2 allows a single operator to explore intraday market regimes and backtest conditional strategies without leaving the keyboard.*

## Core Philosophy
The terminal is an environment of pure focus. Déjà Vu v2 discards the latency of web interfaces in favor of a stateful, REPL-style Command Line Interface (CLI). The architecture is driven by three mandates: **Local Cache Primacy** (never fetch the same bar twice), **Absolute Anti-Lookahead Discipline** (in both model inference and indicator calculation), and **Strict Intraday Execution** (zero overnight risk). 

---

## 1. High-Level Architecture & The REPL Loop

The system is not a collection of isolated scripts, but a cohesive, interactive shell session.

*   **The Interface (The REPL):** Powered by `cmd2` or `prompt_toolkit` to provide a persistent, stateful shell with tab-completion and command history. It maintains a `SessionContext` (active symbol, active model, active strategy).
*   **The Data Engine:** A modular pipeline that ingests 1m/5m/15m bars via **Alpaca (IEX/SIP)**, meticulously tags session boundaries (premarket vs. regular hours), computes custom indicators (VWAP, Relative Volume, Session Highs/Lows), and writes everything to a local **Parquet** cache.
*   **The ML Pipeline (The Oracle):** Computes hidden market regimes. It utilizes `hmmlearn` (HMM) and `statsmodels` (AR) with strict online/walk-forward decoding to prevent future data from leaking into current state predictions. (RNN via `PyTorch` is supported structurally but treated as an experimental Phase 2 module).
*   **The Backtesting Engine:** A high-performance simulation layer powered by `vectorbt`. It consumes the feature matrix and the state signals, evaluates user-defined strategy rules, and enforces the hard "flat-at-close" policy before generating performance metrics.
*   **The Display Layer:** Utilizes the `Rich` library to render beautiful terminal-native outputs: ASCII equity curves, color-coded regime charts, and formatted metric tables.

---

## 2. Directory & File Blueprint (Python Monorepo)

The codebase is structured to isolate the REPL UI from the core quantitative engines.

```text
dejavu_v2/
├── dejavu/
│   ├── __init__.py
│   ├── shell.py              # The main REPL loop (cmd2/prompt_toolkit integration)
│   ├── context.py            # Session state manager (active ticker, loaded data)
│   ├── config.py             # Environment vars & API keys (Pydantic)
│   ├── data/
│   │   ├── fetcher.py        # Alpaca API client with rate-limit handling
│   │   ├── cache.py          # Parquet I/O and manifest.json management
│   │   └── features.py       # Indicator logic (VWAP, RelVol, PDH/L, PMH/L)
│   ├── models/
│   │   ├── base.py           # Abstract interface: train(), infer_walk_forward()
│   │   ├── hmm.py            # GaussianHMM implementation
│   │   ├── ar.py             # AutoReg implementation
│   │   └── rnn.py            # LSTM implementation (Phase 2)
│   ├── strategy/
│   │   ├── builder.py        # Parses CLI rule syntax into boolean logic arrays
│   │   └── engine.py         # vectorbt wrapper; enforces the no-overnight rule
│   └── ui/
│       ├── charts.py         # ASCII plotting logic for price and equity curves
│       └── tables.py         # Rich table formatting for metrics and summaries
├── pyproject.toml            # Poetry/Pip dependencies
├── README.md
└── .env
```

---

## 3. Module Contracts & Pipeline Sequencing

To ensure Neo can build this without ambiguity, the system is broken down into distinct, sequential pipelines.

### 3.1 The Data Pipeline (`data/`)
**Trigger:** Operator types `use AAPL --range 5d --freq 5m`
1.  **Cache Check:** `cache.py` checks `~/.dejavu/data/manifest.json`. If data exists and is fresh, load it into memory. If not, proceed to fetch.
2.  **Fetch:** `fetcher.py` requests raw bars from Alpaca, explicitly including `extended_hours=True`.
3.  **Session Alignment:** Raw data is tagged with a `session_type` column (`premarket`, `regular`, `after_hours`) based on strict ET timestamps.
4.  **Feature Computation:** `features.py` executes a single vectorized pass to calculate:
    *   `vwap`: Resets exactly when `session_type` transitions to `regular`.
    *   `rel_vol`: Compares current bar volume to the rolling 20-day median for that specific time-of-day.
    *   `pdh`, `pdl`, `pmh`, `pml`: Rolling session extremes, forward-filled appropriately.
5.  **Storage:** The enriched DataFrame is saved to `~/.dejavu/data/features/AAPL_5m.parquet` and loaded into the `SessionContext`.

### 3.2 The ML Pipeline (`models/`)
**Trigger:** Operator types `model hmm --states 3`
1.  **Input:** The model class receives the enriched DataFrame from the `SessionContext`.
2.  **Training:** The model fits its parameters (e.g., Baum-Welch for HMM) on the historical feature set (e.g., returns, volatility, rel_vol).
3.  **Strict Inference:** To prevent look-ahead bias, the model executes a walk-forward inference loop. For each bar $t$, it predicts the state $S_t$ using *only* the data available up to $t-1$.
4.  **Output:** An array of integers representing the market regime (e.g., `[0, 0, 1, 2, 2...]`) is appended to the `SessionContext` as a signal column.

### 3.3 The Strategy & Backtest Pipeline (`strategy/`)
**Trigger:** Operator types `strategy new alpha` -> `add trigger --state 1` -> `add condition price > vwap` -> `backtest alpha`
1.  **Rule Parsing:** `builder.py` translates the operator's syntax into vectorized Pandas boolean masks. e.g., `entries = (data['state'] == 1) & (data['close'] > data['vwap'])`.
2.  **No-Overnight Enforcement:** `engine.py` intercepts the boolean masks. It creates an `is_last_bar` mask identifying 15:59 ET. It forces `entries = entries & ~is_last_bar` and `exits = exits | is_last_bar`.
3.  **Simulation:** The modified signals and the price data are passed to `vectorbt.Portfolio.from_signals()`.
4.  **Reporting:** `ui/tables.py` extracts stats (Sharpe, Drawdown, Cumulative Return) and renders a Rich table. `ui/charts.py` renders an ASCII equity curve to `stdout`.

---

## 4. Unresolved Decisions (Escalated to Frank)

Before Neo begins coding, we require clarification on the following parameters from the concept document:

1.  **Data Provider:** `concept.md` mentions Polygon, Alpaca, or Finnhub. `research.md` strongly recommends the **Alpaca IEX feed** for the free MVP (despite lower volume) due to its 7-year intraday depth. Do you approve Alpaca as the primary integration?
2.  **State Naming:** Should the CLI attempt heuristic auto-labeling (e.g., analyzing State 0's mean return to label it "Bullish"), or stick to raw numerical outputs (State 0, State 1) with the stats table provided alongside?
3.  **Strategy Complexity:** For the MVP, is a strategy strictly defined as *one* regime state + *one* indicator condition, or must the parser support complex `AND/OR` chaining immediately?
4.  **Execution Assumptions:** Should the `vectorbt` engine default to zero slippage/commission for pure signal validation, or bake in realistic defaults (e.g., $0.005/share) from day one?