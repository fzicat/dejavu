# Research Delta v2: DejaVu CLI — Run-Time State Selection + HLC Charting

## 1. Run-Time Model State Selection — Data/Model/Backtest Implications

### 1.1 The Shift

**Before (strategy-bound):** Model state is baked into the strategy class. To test a different model or state, you code a new strategy variant.

**After (run-time / backtest-time):** Model and state are CLI flags. The backtest engine applies a generic strategy to bars, but filters trades based on the selected state.

```
# Example CLI
dejavu backtest --symbol AAPL --model hmm --state bull_low_vol
dejavu backtest --symbol AAPL --model ar  --state regime_1
```

### 1.2 Implications

| Area | Impact |
|---|---|
| **Model Output** | Must produce a state label for every bar, stored alongside bar data. The backtest engine reads this as a side-channel signal, not as part of strategy logic. |
| **Backtest Engine** | Strategy class becomes stateless with respect to model. It defines entry/exit rules generically. A pre-backtest filter layer masks signals: if `current_state != requested_state`, suppress entries (but allow exits of open positions). |
| **Caching** | Model state series must be cached independently of strategy params so they're reusable across backtest runs with different state selections. |
| **Multi-Model Comparison** | Enables a clean workflow: run backtests for the same symbol across all states of a model, then compare Sharpe/trade-count/drawdown per state. |
| **Exit Logic** | Critical: exits must NOT be filtered by state. If a position is open and the state flips, the exit signal must still fire. The state filter applies to entries only. |

### 1.3 Signal Masking Logic

```
for each bar t:
    current_state = model_states[t]
    
    # Entry signals are gated by selected state
    if current_state == selected_state and generic_entry_signal[t]:
        effective_entry[t] = True
    else:
        effective_entry[t] = False
    
    # Exit signals are ALWAYS passed through
    effective_exit[t] = generic_exit_signal[t]
```

---

## 2. Model State Representation

### 2.1 Dual Representation

Each state must be representable in two forms simultaneously:

| Form | Type | Purpose |
|---|---|---|
| **Numeric** | 0, 1, 2, ... | Fast array operations, vectorbt signal masking, Parquet storage |
| **Label** | `'bull_low_vol'`, `'neutral_chop'`, `'bear_high_vol'` | CLI UX, report headers, chart legend |

### 2.2 Canonical State ID (CSI)

Define a composite key that uniquely identifies a model's state for a given symbol and date:

```
csi = "{model_type}_{symbol}_{model_date}_state_{n}"
```

Example: `hmm_AAPL_20260401_state_2`

### 2.3 Label Map Storage

The `LABEL_MAP` (from `research_delta.md`) must be stored as a companion JSON file alongside the model pickle:

```json
{
  "model_type": "hmm",
  "n_components": 3,
  "feature_names": ["log_return", "realized_vol", "vwap_deviation", "relative_volume"],
  "label_map": {0: "bear_high_vol", 1: "neutral_chop", 2: "bull_low_vol"},
  "fit_date": "2026-04-01T18:00:00Z",
  "symbol": "AAPL",
  "training_window": "2025-01-01/2026-03-31"
}
```

### 2.4 CLI State Specification

The CLI accepts state either by numeric index or by label name. The label map is loaded at backtest startup and resolves ambiguities:

```
--state 2              → resolves to 'bull_low_vol' via label_map
--state bull_low_vol   → resolves to index 2 via label_map inverse
```

Case-insensitive label matching. Partial matches (e.g., `--state bull`) should error with available options:

```
Error: ambiguous state 'bull'. Available states for hmm_AAPL: 0=bear_high_vol, 1=neutral_chop, 2=bull_low_vol
```

---

## 3. HLC Chart with State Shading — Terminal Implementation

### 3.1 Requirements

- HLC bars (open-high-low-close → rendered as candle bodies or high-low lines with tick marks)
- Entry/exit markers (dots or symbols overlaid on bars)
- Background regions colored/marked by model state
- Terminal-native (no GUI, no browser, no X11)
- Fast rendering for 390+ bars per day (1m resolution)

### 3.2 Library Comparison

| Library | Terminal Native | Candlestick/HLC | Scatter/Markers | Background Regions | Dependency Weight | Status |
|---|---|---|---|---|---|---|
| **plotext** | ✅ Yes | ⚠️ Limited (bar plots only, not true candlesticks) | ✅ Yes | ❌ No native support | ~100kB, pure Python | Active, simple |
| **textual** | ✅ Yes (TUI framework) | ❌ No built-in | ⚠️ Via widgets | ⚠️ Custom | ~350kB, rich deps | Active, but overkill |
| **matplotlib + Agg** | ❌ Renders to file | ✅ Full | ✅ Full | ✅ Full | ~50MB, heavy | Requires image viewer |
| **rich + console** | ✅ Yes | ❌ No | ❌ No | ❌ No | ~200kB | Not a charting lib |
| **termplotlib** | ✅ Yes | ❌ Histogram only | ❌ No | ❌ No | ~40kB | Not suitable |
| **blessed + custom** | ✅ Yes | ✅ Full custom | ✅ Full custom | ✅ Full custom | ~80kB, pure Python | DIY approach |
| **asciichartpy** | ✅ Yes | ✅ Line charts only | ❌ Limited | ❌ No | ~10kB | Too simple |

### 3.3 Recommended MVP Path: `plotext` + Custom State Overlay

**Choice: `plotext`**

Why:
- Pure Python, no C dependencies, installs in one line (`pip install plotext`)
- Renders directly to stdout — fits CLI flow perfectly
- Supports bar charts, scatter overlays, and color coding
- Actively maintained, well-documented
- Handles ~500 data points in < 1 second on typical terminal sizes

**Limitation workarounds:**
- plotext does not have native candlesticks. For HLC bars: plot `high` and `low` as vertical bar spans, and render `close` as a colored scatter dot on each bar.
- Background state shading is not native in plotext. Workaround: render state labels as a separate color-coded subplot below the main chart (like an indicator panel). Each state gets a distinct character/color row.

### 3.4 Chart Layout

```
┌─────────────────────────────────────────────────────┐
│  AAPL  1m  2026-04-01  Model: HMM                  │
│                                                     │
│  High ─┤ ║  ║║║  ║║     ║   ║ ║                   │
│        │ ║  ║║║  ║║  ○  ║   ║ ║                   │
│        │ ║  ║║║  ║║  ○  ║   ║ ║  ○ = entry        │
│  Low  ─┤ ║  ║║║  ║║  ○  ║   ║ ║  x = exit         │
│        └─────────────────────────────────▶ time     │
│                                                     │
│  State: ▓▓▓▓▓▓▓▓░░░░░░░░░▓▓▓▓▓▒▒▒▒▒▒▒▒▒▒▒        │
│         bull     neutral       bear                 │
│                                                     │
│  Legend: ▓=bull ░=neutral ▒=bear ○=entry ×=exit    │
└─────────────────────────────────────────────────────┘
```

Implementation:
1. **HLC bars**: plotext's `plt.bar()` for high-low vertical spans; `plt.scatter()` for close price markers (green above open, red below).
2. **Entry/exit dots**: `plt.scatter()` with distinct markers (e.g., `○` for entries, `×` for exits) overlaid at the bar timestamp.
3. **State background**: A separate 1-row subplot using colored block characters (▓░▒) with the plotext color API (`c.color()`).

### 3.5 Alternative: Full Custom with `blessed`

If plotext's chart quality proves insufficient, the full-custom approach using `blessed` gives pixel-level terminal control:

```python
from blessed import Terminal
term = Terminal()
with termfullscreen():
    for x, bar in enumerate(bars):
        # Draw HLC bar character by character
        height = scale(bar['high'] - bar['low'])
        y_top = chart_bottom - height
        term.move(y_top, x)
        print(term.on_blue('│'))  # colored by state
        term.move(bar_y, x)  
        print('●' if entry else '○' if exit else ' ')
```

This is more code but gives true candlesticks, smooth state backgrounds, and precise marker placement. **Recommend as Phase 2 if plotext is insufficient.**

---

## 4. Risk & Performance Concerns

| Risk | Impact | Mitigation |
|---|---|---|
| **Terminal size limits** — 390 1m bars don't fit in a narrow terminal | High | Implement smart downsampling: render every Nth bar when bar count > terminal width. Use OHLC aggregation (max high, min low, first open, last close) for dropped bars. |
| **Wide color gamut issues** — different terminals render colors differently | Medium | Use 8-color palette (standard ANSI) for state shading: green=blue, neutral=cyan, bear=red. Avoid 256-color or RGB for state regions. |
| **plotext scatter overlay misalignment** | Medium | Ensure plotext's x-axis is integer-indexed (not datetime strings) for all layers. Convert bar index → plotext x coordinate consistently. |
| **Rendering latency on large datasets** | Medium | Cap visible range to 1–3 trading days (390–1170 bars). For full history, implement scrolling/paging via `rich.prompt` or page up/down. |
| **State shading row desync from price chart** | Medium | Share x-axis indices between price and state subplot. Validate `len(state_row) == len(price_bars)` before render. |
| **UTF-8 / block characters** — some Windows terminals lack block characters support | Low | Fallback to ASCII (`#`, `=`, `-`) if Unicode blocks are not available. Detect via `sys.stdout.encoding`. |

### Performance Target

- Render 390 bars (1 day, 1m): < 0.5s
- Render with entry/exit markers: < 0.7s
- Render with state overlay row: < 0.8s
- All on a modern laptop CPU, standard terminal size (80×40 minimum)

---

## 5. Summary: MVP Stack Additions

| Component | Choice | Install | Rationale |
|---|---|---|---|
| **CLI charting** | `plotext` | `pip install plotext` | Minimal deps, terminal-native, fast, supports bar+scatter |
| **State overlay** | Color-coded block character row (plotext subplot) | — | Simple, reliable, works within plotext constraints |
| **Downsampling** | Custom OHLC aggregator | — | Required for multi-day views in narrow terminals |
| **Phase 2 (if needed)** | `blessed` full-custom | `pip install blessed` | True candlesticks, smooth backgrounds, but higher code complexity |
