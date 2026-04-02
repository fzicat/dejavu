# Product Concept: DejaVu v2 — CLI Operator Experience

## 1. Product Vision
DejaVu v2 is a terminal-first, interactive quantitative research workstation designed for intraday regime discovery and strategy validation. It empowers a single operator to select a US symbol, infer hidden market states using sequence models (HMM, AR, RNN) on 1–15 minute bars, and backtest indicator-conditional strategies without overnight exposure. Everything is fast, cache-driven, and keyboard-navigable — a REPL-style tool built for flow-state exploration.

## 2. Core User Journey

1. **Launch & Welcome** — Operator launches `dejavu`. A welcome banner appears with a quick summary of the cache state (symbols cached, last update times) and the main menu.
2. **Context Setup** — Operator issues `use [TICKER] [date range]`. DejaVu fetches and caches 1, 5, or 15-minute bar data, along with daily reference data (prev close, prev high/low, VWAP, premarket high/low, relative volume).
3. **Model Selection & Fitting** — Operator issues `model [hmm|ar|rnn] --states 3`. The model fits on the cached data, prints a concise training summary, and stores the state sequence.
4. **Visualization** — Operator issues `show states` to see an ASCII plot of price overlaid with regime bands, or `show summary` for a statistical table of each state's properties.
5. **Strategy Building** — Operator issues `strategy create [name]`, then adds rules like "IF state=bullish AND price > vwap THEN long". Rules are validated interactively.
6. **Backtest** — Operator issues `backtest [strategy_name]`. The engine runs, respecting intraday-only constraints (auto-exit at session close), and prints a metrics card plus an ASCII equity curve.
7. **Review & Iterate** — Operator tweaks the model parameters, creates a new strategy, or switches symbols. All results are stored in session and can be recalled.

## 3. Command Taxonomy

The CLI uses a hierarchical command structure, modeled after tools like `boto`, `click`, or a terminal application with sub-commands:

### 3.1 Session Control
| Command | Description |
|---|---|
| `quit` / `exit` / `Ctrl+C` | Exit the application |
| `help [cmd]` | Show help for the CLI or a specific command |
| `status` | Show active symbol, active model, cached data summary |
| `set --theme [dark|light]` | Toggle terminal color profile |

### 3.2 Context & Data
| Command | Description |
|---|---|
| `use [TICKER] --range 5d --freq 5m` | Set symbol, fetch/cached data |
| `cache --list` | List all locally cached symbols and timestamps |
| `cache --purge [TICKER]` | Remove cached data for one symbol |
| `data --head` | Show first few bars of cached data |

### 3.3 Model Operations
| Command | Description |
|---|---|
| `model list` | Show available models: `hmm`, `ar`, `rnn` |
| `model hmm --states 3 --window 20` | Fit HMM with parameters |
| `model ar --order 4` | Fit Autoregressive model |
| `model rnn --hidden 64 --epochs 50` | Fit RNN/LSTM model |
| `model --active` | Show which model/results are currently active |

### 3.4 Visualization
| Command | Description |
|---|---|
| `show states` | ASCII chart: price with colored/hashed state bands |
| `show summary` | Table: state label, mean return, volatility, duration, transition matrix |
| `show transitions` | State transition probability matrix |
| `show recent` | Print current state and recent state sequence |

### 3.5 Strategy Builder
| Command | Description |
|---|---|
| `strategy list` | List saved strategies |
| `strategy new [name]` | Begin defining a new strategy |
| `... add trigger --state [X]` | Bind rule to a specific state |
| `... add condition price > vwap` | Add indicator condition |
| `... add condition rel_vol > 1.5` | Add relative volume condition |
| `... add action long / short` | Define entry action |
| `... save` | Save and validate strategy |

### 3.6 Backtesting
| Command | Description |
|---|---|
| `backtest --strategy [name] --symbol [TICK]` | Run backtest |
| `backtest --compare [s1,s2]` | Compare two strategies |
| `metrics --show` | Display active backtest metrics card |
| `chart --equity` | ASCII equity curve |
| `chart --trades` | List all simulated trades |

### 3.7 Strategy Triggers: Indicator Mapping

All triggers map to the operator's specified set:

- `vwap`: Price relation to VWAP (`price > vwap`, `price < vwap`, `price crossing vwap`).
- `prev_close`: `price > prev_close`.
- `prev_high`, `prev_low`: Breakout/bounce levels.
- `pm_high`, `pm_low`: Premarket high and low levels.
- `rel_vol`: Relative volume filter (e.g., `rel_vol > 2.0`).

Constraints are enforced automatically: intraday only (1-15m bars), no overnight holds. All positions are liquidated at the session's final bar.

## 4. MVP Scope

### In Scope (v2)
- Interactive CLI with context, subcommands, and tab completion.
- `use [TICKER]` with data fetching from a provider (e.g., Polygon, Alpaca, or Finnhub) and disk caching.
- Three core models: HMM (via `hmmlearn`), AR (via `statsmodels`), RNN (via PyTorch or minimal custom).
- State visualization in the terminal (color-coded ASCII/Unicode, or `rich`/`textual` for tables and panels).
- Strategy definition: state + single indicator trigger -> long/short.
- Backtest engine: intraday, no overnight, basic metrics (Sharpe, MaxDD, Return, Win Rate).
- ASCII equity curve and trade table output via `rich` or `textual`.

### Out of Scope (Deferred)
- Real-time or streaming data (v2+).
- Graphical terminal widgets beyond tables/panels (no full TUI graphs).
- Multi-symbol backtesting / portfolio-level strategies.
- Persistent model storage across sessions (save/load is v3).
- Export of results to external files.

## 5. Open Questions for Frank

1. **Data Provider Preference** — Do you have a preferred intraday data source? Polygon.io, Alpaca, Yahoo Finance (limited intraday), or Finnhub? This affects caching structure and reliability.
2. **State Naming** — Should states be auto-labeled heuristically (e.g., "Up-Trending", "Choppy") based on statistical properties, or simply numbered (State 0, 1, 2) with raw stats shown?
3. **CLI Framework** — Should we build a REPL using `prompt_toolkit` / `cmd2` for a rich interactive shell, or use a subcommand parser like `click` / `typer`? REPL is more fluid for exploration; subcommands are simpler.
4. **Backtest Constraints** — Are transaction costs and slippage assumptions needed for MVP, or can they be flat/zero for now?
5. **Strategy Complexity** — Can a single strategy have multiple state + condition rules, or is each strategy strictly one rule for MVP?
