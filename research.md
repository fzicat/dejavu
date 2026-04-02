# Technical Research Brief: DejaVu CLI — Intraday, No-Overnight, Regime-Driven

## Objective
Define the data, model, backtesting, caching, and risk architecture for a local-first CLI tool that:
- Pulls US equity intraday bars (1–15m), including premarket and regular session
- Runs HMM, Autoregressive, and RNN sequence models for regime/signal generation
- Backtests strategies conditioned on model output with a strict **no-overnight** flat-at-close rule
- Maintains an indicator suite (VWAP, daily hi/lo, premarket hi/lo, prev-day close/hi/lo, relative volume)
- Caches all data locally on disk for reproducibility and speed

Deliverable is a CLI, not a web app. MVP is single-user, local dev.

---

## 1. Market Data Providers (Intraday + Extended Hours)

| Provider | Free Tier Depth | Bars Resolution | Extended Hours Support | Rate Limits | Python Client | Key Risk |
|---|---|---|---|---|---|---|
| **Alpaca (IEX feed)** | 7+ years historical | 1m, 5m, 15m | Yes (`extended_hours=true`) | 200 req/min, ~10k bars/page | `alpaca-py` (official) | IEX-only (~2–3 % of volume) on free tier; SIP requires paid ($99/mo) |
| **Alpaca (SIP feed)** | 7+ years (>15 min old) | 1m, 5m, 15m | Yes (historical only on free tier) | Same | `alpaca-py` | Recent SIP bars are not free; paid needed for live |
| **Polygon / Massive.com** | 2 years (Basic), 5 years ($29) | 1m (Basic), 1s ($29+) | Yes, included in aggregates endpoints on all tiers | 5 calls/min (Basic), unlimited paid | `polygon-api-client` (official) | Basic is end-of-day latency; real-time/delayed bars need Starter ($29/mo) |
| **Tiingo** | Limited free intraday | 1m on paid tiers only | No (intraday is RTH only) | Generous daily but no free intraday bars | `tiingo` | Free tier is EOD only; paid starts $10/mo for intraday |
| **eodhd** | Paid only for intraday | 1m | No documented premarket | Paid | `requests` easy | Not viable for free MVP |

### Recommendation
- **Primary: Alpaca IEX feed (free).** Even though it's only ~2–3% of consolidated volume, 1-minute bars from IEX span 7+ years, include extended hours, and have a first-class Python SDK. For regime-signal experiments this is sufficient.
- **Fallback / Upgrade Path: Polygon Starter ($29/mo).** 5 years of SIP-quality intraday with 15-min delay — enough for backtesting. If Frank ever moves toward live signals, the $99 Alpaca Algo Trader tier fills that gap.

---

## 2. Sequence Models on Intraday Data

### 2.1 Hidden Markov Models (HMM)
- **Libraries:** `hmmlearn` (scikit-learn API, mature, stable). `pomegranate` (faster inference, Cython-backed, less active).
- **Intraday regime modeling:** 1m bars are extremely noisy. Recommended approach is to run HMM on **aggregated features** rather than raw returns: e.g., rolling volatility, signed volume, VWAP deviation, relative volume. This stabilizes state emission distributions.
- **State count:** 2–3 states (bull/bear/flat). More states overfit on intraday.
- **Training:** Baum-Welch on a few thousand bars per symbol is sub-second. Training per-symbol on the fly at startup is feasible.
- **Critical pitfall:** HMM state assignment at time *t* uses data up to *t*. If you train on the full series and then use Viterbi states, you introduce look-ahead bias. Mitigation: **online/walk-forward Viterbi decoding** or retrain with a rolling window that ends at or before each bar.

### 2.2 Autoregressive Models
- **Library:** `statsmodels` (ARIMA/SARIMAX). For intraday daily-seasonal patterns, a simple **AR(p)** or **ARIMA(p,1,0)** on rolling returns is sufficient.
- **Order selection:** Use AIC/BIC on a rolling validation window to pick *p* (typically 1–5 for intraday returns). Intraday returns have very low autocorrelation — AR models will often be statistically insignificant. They're useful for **baseline comparison** rather than alpha generation.
- **Training cost:** Negligible. A few milliseconds per symbol per window.
- **Recommendation:** Include AR but treat it as a reference regime detector. Don't expect it to outperform random on intraday without exogenous features.

### 2.3 RNN (LSTM / GRU)
- **Framework:** PyTorch or Keras. For a CLI, **PyTorch** is preferred — lighter dependencies and better control over the training loop without pulling in the full TensorFlow runtime.
- **Feasibility:** Training a 1-layer 32-unit LSTM on 10k bars of 1m returns takes ~30 seconds on CPU, ~5s on a modern GPU. Training **per-symbol for 500 symbols** would take hours on CPU. For MVP: train on a **single watchlist of 10–20 symbols**.
- **Risk:** Extremely high overfitting risk on 1m bars. Dropout, small hidden size, and early stopping on a validation fold are mandatory.
- **Recommendation:** RNN is an **experimental tier** for the MVP. Start with HMM + AR for day-one signals. Add RNN once the data pipeline, caching, and backtest are proven.

| Model | Per-Symbol Train Time (CPU) | Intraday Viability | Overfit Risk | Recommendation |
|---|---|---|---|---|
| HMM | <1s | High (with aggregated features) | Medium | Primary signal generator |
| AR(p)/ARIMA | <10ms | Low–Medium (baseline) | Low | Baseline comparison |
| LSTM/GRU | 5–30s | Experimental | High | Phase 2, experimental tier |

---

## 3. Backtesting Engine

### 3.1 Candidate Evaluation

| Engine | Intraday Support | Custom Indicators | No-Overnight Rule | Performance | Maintenance | Notes |
|---|---|---|---|---|---|---|
| **vectorbt** | Yes (any freq) | Full custom via numba | Manual flat-at-close logic in signal series | Excellent (numba-vectorized) | Active | Best fit if strategy logic maps to vectorized signals |
| **Backtrader** | Yes | Strategy class with full custom | Built-in `cheat-on-open` + `close=True` flattening | Good (event-driven) | Slow but active | Easier for complex per-bar state logic |
| **Custom NumPy/Pandas** | Full control | Full control | Manual | Fast if well-written | N/A | High dev time; reinvents slippage/commission |
| **bt** | Limited | Limited | Manual | Good | Dormant | Not recommended for intraday |
| **Zipline-reloaded** | Yes | Restricted to pipeline API | Manual | Good | Community fork | Overengineered for a CLI |

### 3.2 Recommendation
- **vectorbt** for the MVP. Reasoning:
  1. Regime-based strategies are fundamentally **signal → position** mappings. vectorbt excels at generating all combinations of entry/exit rules against a signal series.
  2. The no-overnight flat rule is implemented by forcing position = 0 at the last bar of each session (e.g., 15:59 for 1m bars). In vectorbt this is `entries = entries & ~is_last_bar_of_session` and a matching `exits = is_last_bar_of_session`.
  3. Custom indicators (VWAP, rel vol, etc.) can be computed as Pandas series, then fed as signal features directly into vectorbt's `from_signal()` or `Portfolio.from_simulated()` API.

- **Alternative:** If the regime strategy requires complex per-bar state that vectorbt's functional style can't express, **Backtrader** is the fallback. Its event-driven loop makes enforcing "flatten at close" trivial via `self.close()` in a `next()` hook on the last bar.

---

## 4. Indicator Suite

All indicators below are computable from OHLCV1m bars with no external data dependency:

| Indicator | Formula / Approach | Session Boundary Note |
|---|---|---|
| **VWAP** | `cumsum(typical_price × volume) / cumsum(volume)`, reset at each regular session open | Must reset at market open (09:30 ET), not at midnight. Include premarket bars in pre-VWAP if desired. |
| **Daily Hi/Lo** | Rolling max/min over current session bars | Track from 09:30 ET (or 04:00 ET if session includes premarket). |
| **Premarket Hi/Lo** | Rolling max/min over [04:00, 09:29] ET | Only available once session is underway; not at open of premarket. |
| **Prev-day Close/Hi/Lo** | Cached from previous session's last bar and extremes | Requires a session boundary aware data loader. |
| **Relative Volume** | `current_bar_volume / median_volume_same_time_of_day_last_N_days` | Requires multi-day alignment of 1m bars. N=20 is standard. |

Implementation note: All indicators should be computed in a **single pass** over the bar DataFrame, with session boundaries determined from the index (or a separate market-calendar mapping). No external calendar library (like `trading_calendars`) is needed for MVP — hardcode the ET session windows.

---

## 5. Caching / Storage Strategy

### 5.1 Format: Parquet (not SQLite, not CSV)

| Format | Read Speed | Write Speed | Incremental Update | Appends | Schema Evolution |
|---|---|---|---|---|---|
| **Parquet** | Excellent (columnar, memory-mapped) | Good | Requires rewriting file or partition | Not natively appendable | Additive columns OK |
| SQLite | Good for random row queries | Slower | Easy | Easy | Easy |
| CSV | Slow | Slow | Easy | Easy | Hard |

For a data pipeline that writes once (per symbol per day) and reads many times (for model training, backtesting, indicator computation), **Parquet is the right choice**.

### 5.2 Schema

```
data/
  raw/
    {symbol}/
      {date}_1m.parquet        # OHLCV + extended_hours flag
  features/
    {symbol}/
      {session_date}_indicators.parquet   # precomputed indicators
  models/
    {symbol}/
      hmm_{date}.pkl
      ar_{date}.pkl
  backtests/
    {symbol}_{strategy}_{date}.parquet    # results
```

Each `raw` parquet file contains columns: `timestamp, open, high, low, close, volume, trade_count, vwap, session_type` where `session_type ∈ {premarket, regular, after_hours}`.

### 5.3 Invalidation / Freshness Policy
- **Daily bars:** Invalidate and re-fetch at 08:00 ET each trading day.
- **Intraday bars:** If the file for today exists, fetch only bars after the file's latest timestamp (incremental). Alpaca supports `start` parameter for exactly this.
- **Model files:** Regenerate when new indicator data arrives. Keep a hash/md5 of the input feature set in the model filename or a companion `.json` to detect stale models.
- **Backtest results:** Cache is the source of truth. Invalidate when the strategy parameters or the underlying bar data changes.

### 5.4 Freshness Metadata

Store a lightweight `manifest.json` at the root of `data/`:
```json
{
  "AAPL": {
    "last_fetch": "2026-04-01T12:00:00Z",
    "latest_bar": "2026-04-01T15:59:00-04:00",
    "data_provider": "alpaca-iex",
    "bars_count": 157842
  }
}
```

---

## 6. Technical Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| **IEX-only data misses volume signal** (primary: Alpaca free) | Medium | High | Use relative volume ratio (symbol vs. itself) rather than absolute volume. If SIP is required, upgrade to Polygon Starter ($29/mo). |
| **Premarket gaps / sparse bars** | High | Medium | Pre-market 1m bars are often empty for low-liquidity names. Filter to symbols with ≥X premarket trades per bar, or fall back to 5m for premarket only. |
| **Look-ahead bias in HMM state assignment** | Critical | Medium | Use **strictly forward-looking decoding**: train on data up to t-1, predict state for bar t. Or use an online Viterbi that only processes completed bars. Never fit Viterbi on the full series then slice. |
| **Session boundary errors in VWAP / daily hi-lo** | High | Medium | Implement a session-boundary marker function that tags each bar as `premarket / regular / after_hours`. All indicator resets use this marker, not a fixed time. |
| **Overfitting RNN on 1m bars** | High | High | Treat RNN as experimental. Use walk-forward validation. Cap hidden units at 32. Use dropout ≥ 0.2. Report out-of-sample Sharpe, not in-sample. |
| **Backtest assumes zero slippage & commission** | Medium | High | Default to $0.005/share slippage + $0.003/share commission in vectorbt. These are configurable but must default to realistic values. |
| **Model overtrading (whipsaw)** | Medium | High | Add a minimum holding period filter (e.g., no flip within N bars of last trade). This is a strategy-level parameter, not a model parameter. |
| **Data API rate limits during bulk fetch** | Medium | Medium | Implement an exponential backoff + retry queue. Cache aggressively. Fetch one symbol at a time with a configurable delay. |

---

## 7. Stack Recommendation (MVP)

| Layer | Choice | Rationale |
|---|---|---|
| **CLI Framework** | `click` or `typer` | `typer` is simpler for subcommands (`dejavu fetch`, `dejavu train`, `dejavu backtest`) |
| **Data Provider** | Alpaca IEX (free), Polygon Starter ($29) fallback | Free intraday + extended hours, official SDK |
| **Data Format** | Parquet + `manifest.json` | Columnar, fast reads, incremental friendly |
| **HMM** | `hmmlearn` | Mature, sklearn-compatible, sub-second training |
| **Autoregressive** | `statsmodels` | Standard library for AR/ARIMA |
| **RNN** | PyTorch (optional, Phase 2) | No full TF dependency, CPU-fast for small models |
| **Indicators** | Custom NumPy/Pandas functions | Full control, no external library needed |
| **Backtesting** | `vectorbt` | Vectorized, signal-driven, parameter sweep ready |
| **Calendar** | Hardcoded ET session windows | No external dependency for MVP |
| **Python Version** | 3.11+ | Performance improvements over 3.10, wide library support |

### Suggested Open Decision Points for Frank

1. **Data provider:** Is the Alpaca IEX free tier (~2–3% volume) acceptable for the MVP, or should we plan for a $29/mo Polygon Starter tier from the start?
2. **Scope:** How many symbols in the initial watchlist? If >50, RNN training will be a bottleneck.
3. **Backtest realism:** Should default slippage/commission be built in, or should the MVP start with zero-cost to keep things simple?
4. **Premarket granularity:** Should premarket bars be 1m like RTH, or is 5m sufficient for premarket to avoid sparse-bar noise?
