# DejaVu v2 — CLI UX Delta v2 (Strategy/Model Decoupling + HLC Chart)

## 1. Problem Statement
In the previous spec, a strategy definition bundled model state into its rules (e.g., `IF state=up_trend AND price > vwap THEN long`). This tightly couples strategy logic to a single model's state inference, reducing reusability and forcing operators to duplicate strategies for each model/state combination. The new model cleanly separates **strategy logic** from **model/state context**, and the operator binds them at backtest time.

## 2. New Strategy UX (State-Independent)

Strategies now define pure price/indicator rules with no reference to model states.

### Example Strategy Definition
```
strategy new momentum_breakout
rule 1: IF price > vwap AND rel_vol > 1.5 THEN long
rule 2: IF price < prev_close THEN exit
strategy save
```

Key changes:
- `IF state=...` is no longer valid inside a strategy definition. The strategy builder will reject it.
- A strategy is now a reusable logic module. The same strategy can be tested against any model/state combination.

## 3. New Backtest Interaction UX

The `backtest` command is now the binding point for strategy + model + state.

### Interactive Flow (prompt_toolkit REPL)
```
> backtest
  Strategy: momentum_breakout    ← tab-completable from saved strategies
  Model:     hmm                 ← tab-completable from fitted models
  State:     Up-Trend            ← tab-completable from active model's inferred states
  Date:      5d (default)        ← optional override
  → Running backtest...
```

### One-Line Shorthand
Operators can skip prompts with explicit arguments:
```
> backtest --strategy momentum_breakout --model hmm --state "Up-Trend" --range 10d
```

### Multi-Run Comparison
Quick comparison across states or models:
```
> backtest --strategy momentum_breakout --model hmm --all-states    ← runs across all inferred states
> backtest --compare --strategy momentum_breakout --models hmm,rnn  ← runs same strategy w/ both models
```

## 4. HLC Chart Command

### New Chart Type: `chart hlc`

A new visualization command that renders an HLC (High-Low-Close) bar or candlestick chart with:

- **Default**: Price bars for the active symbol/date range. If a model has been fitted and a backtest has run, the background is automatically colored by model state bands, and entry/exit markers are overlaid.
- **Model State Background**: Colored or shaded regions behind the price bars, each corresponding to an inferred state. A legend maps colors to auto-labeled states (e.g., `[███] Up-Trend`, `[░░░] Choppy`, `[▓▓▓] Down-Trend`).
- **Entry/Exit Dots**: Green `▲` dots for entries, red `▼` dots for exits, plotted at the time-price coordinate of the trade.
- **Optional Flags**:
  - `--no-states`: Suppress state background coloring, show raw price only.
  - `--no-trades`: Suppress entry/exit markers.
  - `--overlay vwap`: Add VWAP as a dashed line overlay.
  - `--export ascii`: Force a pure ASCII/Unicode fallback for environments without color support.

### Example Output (conceptual)
```
> backtest --strategy momentum_breakout --model hmm --state "Up-Trend"
→ Running... done.
  Sharpe: 1.42 | MaxDD: -3.2% | Return: +8.1% | Trades: 14

> chart hlc --overlay vwap
  N   V   A   D   I   A           ▲          ▲
       [░░░░░░]   [████████Up-Trend████]   [▓▓▓]   [███]   [░░░]     ▲    ▲
  ──────────────────────────────────────────────────────────────
  (HLC bars rendered across state-colored background with green/red trade markers)
```

## 5. Updated End-to-End CLI Flow

```
1. dejavu                          → Launch REPL
2. use AAPL --range 10d --freq 5m  → Fetch/cache data
3. model hmm --states 3            → Fit model, auto-label states
4. show states                     → Preview state visualization
5. strategy new momentum_breakout  → Define state-agnostic rules
   rule 1: IF price > vwap AND rel_vol > 1.5 THEN long
   rule 2: IF price < prev_close THEN exit
   strategy save
6. backtest                        → Bind strategy + model + state
   → Interactive prompts: strategy / model / state
7. [Results: metrics card + trade table]
8. chart hlc --overlay vwap        → View annotated HLC chart
9. backtest --strategy momentum_breakout --model rnn --state "Trending Up"  → Compare
```

## 6. Migration Notes (Operator Impact)

| Old Behavior | New Behavior |
|---|---|
| Strategies include `state=X` in their rules | Strategies are state-agnostic; binding happens at `backtest` time |
| `strategy show` displays state conditions | `strategy show` displays only price/indicator rules |
| Backtest is automatic after strategy save | Backtest is an explicit command with strategy/model/state triplet |
| No chart command | New `chart hlc` with state background + entry/exit overlay |

**Operator action required**: Any previously saved strategies that included `IF state=...` conditions will fail validation on load. Those `state=` clauses must be stripped during the migration pass or removed manually.

## 7. Open Questions for Frank

1. **Default State Selection** — When the operator runs `backtest` interactively without specifying `--state`, should the CLI default to the most frequently occurring state on the date range, or simply pick State 0? (Recommendation: prompt the operator — don't default silently.)
2. **Simultaneous Entry on Multiple States** — If `--all-states` is used and a strategy triggers on overlapping bars across states, should the backtest allow concurrent "virtual" positions (per-state portfolios), or should states be treated as mutually exclusive regimes (bar belongs to one state, one trade)? (Recommendation: mutually exclusive — a bar has one state.)
3. **Chart Width Constraint** — Terminal width varies. Should the HLC chart auto-downsample (e.g., max 120 bars visible) for readability, or attempt to render all bars with horizontal scrolling? (Recommendation: auto-downsample for the visible window, with a hint showing total bars and downsample rate.)
