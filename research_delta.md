# Research Delta: DejaVu CLI v2 — Data Stack, Zero-Cost Backtest, Auto-Labeling

## 1. Data Stack: Free-Only (Alpaca IEX Primary + yahooquery Fallback)

### 1.1 Primary: Alpaca IEX (`alpaca-py`)

| Property | Value |
|---|---|
| Resolution | 1m, 5m, 15m bars |
| Extended Hours | Yes (`extended_hours=true`) |
| Historical Depth | 7+ years (since ~2016–2018) |
| Rate Limits | 200 req/min, ~10k bars per page |
| Coverage | IEX exchange only (~2–3 % of consolidated volume) |
| Cost | Free (no brokerage account required for data-only keys) |

**Risk:** Volume on IEX-only bars is a fraction of true consolidated volume. Absolute volume metrics (e.g., raw relative volume vs. market) will be distorted. Price OHLC and VWAP are less affected but may show wider spreads on illiquid names.

### 1.2 Fallback: yahooquery

| Property | Value |
|---|---|
| Library | `yahooquery` — Python wrapper for Yahoo Finance's unofficial API |
| Resolution | 1m, 5m, 15m, 30m, 60m bars |
| Extended Hours | Limited. Yahoo's intraday endpoint returns extended-hours bars but the `extended_hours` parameter is inconsistent across symbols. |
| Historical Depth | ~60 days for 1m bars, ~730 days for 5m bars |
| Rate Limits | Unofficial — soft limit ~2k req/hr; IP-based blocks possible |
| Coverage | Composite (SIP-equivalent for EOD; intraday source is undocumented) |
| Cost | Free |

**Risk:** Deep intraday history on 1m is capped at ~60 days. This makes `yahooquery` useful as a *recent gap-filler* but not a full-history fallback. For multi-year backtests, if Alpaca is down, there is no free substitute of equivalent depth.

### 1.3 Schema Normalization

Both providers must map to a single canonical schema:

```
timestamp (UTC), open, high, low, close, volume, trade_count, vwap, session_type
```

- `timestamp`: Always UTC. Convert from ET on write.
- `session_type`: Derived from ET hour:
  - 04:00–09:29 ET → `premarket`
  - 09:30–15:59 ET → `regular`
  - 16:00–20:00 ET → `after_hours`
- `trade_count`: Not available from yahooquery → fill with `NaN` or `0` with a schema flag.

### 1.4 Failover Behavior

```
1. Attempt Alpaca fetch.
2. If Alpaca HTTP 4xx/5xx or timeout (>30s):
   a. For intraday bars ≤ 60 days old: use yahooquery.
   b. For bars > 60 days old: serve from local Parquet cache; log a warning.
3. If both providers fail: serve stale cache; flag results as POTENTIALLY_STALE.
4. On recovery: incremental fetch to fill gaps; merge and rewrite Parquet.
```

**Data quality caveat:** When mixing Alpaca IEX and Yahoo intraday, bar-level VWAP and volume will not be comparable across the boundary. Strategies that depend on absolute thresholds (e.g., `volume > 1M`) should be avoided. Relative comparisons (volume vs. same time last N days) are robust.

---

## 2. Timezone & Session Alignment

### Rules
- All timestamps stored as UTC. Session logic computed from ET offsets.
- Standard trading day: 09:30–16:00 ET.
- Premarket: 04:00–09:29 ET.
- After-hours: 16:00–20:00 ET.
- ET offset is UTC-5 (EST) or UTC-4 (EDT). Handle DST transitions explicitly:
  - 2026 DST starts March 8, ends November 1.
  - Do NOT use `pytz.timezone('America/New_York').localize()` with ambiguous datetimes. Use `zoneinfo.ZoneInfo('America/New_York')` (Python 3.9+).

### Implementation
```python
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
utc_ts = ts_utc.astimezone(ET)
hour = utc_ts.hour
minute = utc_ts.minute
```

### Premarket Availability
- Alpaca IEX: Premarket bars exist for most large-cap symbols starting ~04:00 ET, but liquidity may be sparse (zero-volume bars) for symbols outside the Russell 1000. Filter: drop bars where `volume == 0` AND `high == low == open == close`.
- yahooquery: Premarket 1m bars may be absent for many symbols. Do not assume premarket exists. If no bars fall in [04:00–09:29] ET, premarket indicators (premarket hi/lo) are `NaN` for that session.

---

## 3. Zero-Cost MVP Backtest — Implications & Disclosures

### 3.1 What Zero-Cost Means

A zero-cost backtest assumes:
- No commissions
- No slippage (fill at exact close price of the signal bar)
- No market impact (infinite liquidity at mid)
- No borrow cost for shorts (if applicable)

### 3.2 Magnitude of Distortion

For intraday 1m bars on mid-cap stocks:
- **Spread:** Typical NBB-NBO spread on IEX for S&P 500 names is $0.01–$0.03. On a $100 stock, that's 10–30 bps one-way (20–60 bps round-trip).
- **Slippage from market orders:** On a 1m bar with 50k volume, a 100-share market order may slip 1–2 ticks. With 1k shares, slip is 3–8 ticks. Zero-cost ignores this entirely.
- **Result impact:** A strategy showing 15% annualized return at zero cost may be flat or negative after realistic costs on 1m bars with >50 trades/month.

### 3.3 Required Warning Disclosure

The CLI must print the following warning (or its equivalent in any report output):

```
⚠️  WARNING: This backtest uses ZERO transaction costs (no commission, no slippage).
    Real-world performance will be lower, potentially significantly so for
    high-frequency or high-turnover strategies. On 1-minute intraday data,
    realistic costs of 5–15 bps round-trip can eliminate marginal edges entirely.
    Re-run with --slippage and --commission flags before deploying capital.
```

### 3.4 Recommendation

Build slippage/commission knobs into vectorbt from day one (they are native to its API), but default them to zero for the MVP simplicity. The warning above is the minimum. Add sensible defaults (`--slippage 0.001 --commission 0.001`) in a post-MVP update.

---

## 4. Auto-Labeling HMM Regime States

### 4.1 The Problem

`hmmlearn` returns states labeled `0, 1, 2, ...` with no inherent semantic meaning. After fitting, state `0` might be "low-vol bull" on one run and "high-vol crash" on another. This makes downstream strategy logic (e.g., "only trade in state X") non-deterministic across retraining.

### 4.2 Solution: Heuristic Labeling from Emission Statistics

After fitting the HMM, extract the emission parameters and assign human-readable labels via a deterministic heuristic:

```python
import numpy as np
from hmmlearn import hmm

model = hmm.GaussianHMM(n_components=3, covariance_type='diag', n_iter=1000)
model.fit(X)  # X = features[:, [log_return, volatility]]

# Emission means: shape (n_components, n_features)
means = model.means_      # e.g., [[-0.001, 0.02], [0.001, 0.005], [0.0, 0.015]]
variances = model.covars_  # emission variances

# Heuristic: sort by (mean_return ascending, volatility ascending)
# Higher mean return → more bullish. Higher volatility → more turbulent.
state_scores = means[:, 0] - means[:, 1]  # crude: return minus vol penalty
ranking = np.argsort(state_scores)  # 0 = worst, n-1 = best

LABEL_MAP = {
    ranking[0]: 'bear_high_vol',
    ranking[1]: 'neutral_chop',
    ranking[2]: 'bull_low_vol',
}
```

### 4.3 Feature Selection for Stable Labeling

Do NOT use raw price or raw returns as the sole feature. Recommended feature vector:

| Feature | Compute | Rationale |
|---|---|---|
| Log return | `log(close_t / close_{t-1})` | Primary mean signal |
| Realized vol | `std(returns, window=20)` on 1m bars | Volatility regime signal |
| VWAP deviation | `(close - vwap) / vwap` | Intraday position relative to fair price |
| Relative volume | `volume / median_volume_same_time` | Confirms conviction behind moves |

With 4 features, `covariance_type='diag'` keeps parameter count manageable even on limited data.

### 4.4 Labeling Stability Across Retraining

To ensure labels are consistent after each retrain:
1. After fitting, apply the same deterministic heuristic (sort states by `mean_return - volatility_penalty`).
2. Store the `LABEL_MAP` dictionary alongside the `.pkl` model file.
3. Strategy logic references label names (`'bull_low_vol'`), never raw state integers.

### 4.5 Number of States

| `n_components` | Behavior | Recommendation |
|---|---|---|
| 2 | Bullish vs. bearish (or calm vs. turbulent) — very clean | Good starting point |
| 3 | Adds "neutral/choppy" or "accumulation" state | **Recommended default** — sufficient for strategy differentiation |
| 4+ | Overfits on intraday; states become transient noise | Avoid for MVP |

Use BIC (Bayesian Information Criterion) to validate: `model.bic(X)`. If BIC decreases at n=4, it's statistically justified, but still consider 3 as a practical cap for the MVP.

---

## 5. Risk Summary

| Risk | Impact | Mitigation |
|---|---|---|
|yahooquery 1m history limited to ~60 days | High | Use only as gap-filler for recent bars; primary history is Alpaca |
| IEX volume ≠ consolidated volume | Medium | Use relative volume (self-compare) only; avoid absolute volume thresholds |
| Premarket bars sparse or absent for small-caps | Medium | Filter symbol universe to names with ≥N premarket trades; use 5m resolution for premarket |
| Zero-cost backtest overstates returns | High | Mandatory UI warning; build slippage/commission parameters; make defaults explicit |
| HMM state label flip on retrain | High | Deterministic labeling heuristic above; store label map with model |
| Session boundary mis-tagging across DST | Medium | Use `zoneinfo` (Python 3.9+); test around DST boundaries with known dates |

---

## 6. Open Questions for Frank

1. **HMM state count:** Default to 3 (bull/neutral/bear) or allow CLI override per-symbol?
2. **Fallback depth:** Is ~60 days from yahooquery acceptable for the fallback, or should we add a third free source (e.g., Tiingo EOD for long-term context)?
3. **Slippage defaults:** Should sensible defaults (e.g., 1 bp slippage) ship with v2.1 or stay out entirely of MVP?
