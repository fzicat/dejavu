# Déjà Vu CLI — QA & Validation Plan (MVP)

**Version:** 1.0 | **Author:** Seraph | **Scope:** CLI MVP build

---

## 1. Defect Severity Rubric

| Severity | Definition | Gate Action |
|----------|-----------|-------------|
| **Critical** | Crash, data corruption, overnight trades, lookahead bias, wrong prices, credential leak | Block release — must fix |
| **Major** | Wrong indicator value, missing backtest metric, config ignored silently, cache serves stale data >24h | Block release — must fix |
| **Minor** | CLI output formatting, exit code mismatch, unhelpful error message, redundant log lines | Document — ship with caveat or fix |
| **Suggestion** | Nice-to-have output, performance improvements not affecting correctness | Backlog |

---

## 2. Test Matrix

### 2.1 Core CLI Interface (`$ dv ...`)

| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| CLI-1 | No args | `dv` | Print help/usage, exit 0 | Minor |
| CLI-2 | Unknown command | `dv foobar` | Error + exit 1 (not crash) | Minor |
| CLI-3 | Unknown flag | `dv pull --nacho` | Error + exit 1 | Minor |
| CLI-4 | Help flag | `dv --help`, `dv pull --help` | Subcommand-specific help | Minor |

### 2.2 Data Fetching & Caching (`dv pull AAPL`)

| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| PUL-1 | Valid symbol | `dv pull AAPL --days 365` | Fetches OHLCV, saves to `.parquet`, prints progress | Critical |
| PUL-2 | Invalid symbol | `dv pull ZZZZ` | Graceful error, exit 1, no partial parquet | Major |
| PUL-3 | Cache hit (fresh) | `dv pull AAPL` (within 24h of prior pull) | Returns cached data, no network call, prints "cached" indicator | Major |
| PUL-4 | Cache hit (stale) | `dv pull AAPL` (after >24h) | Refetches from yfinance, overwrites parquet | Major |
| PUL-5 | Custom lookback | `dv pull AAPL --days 730` | Returns ~730 trading days of daily data | Major |
| PUL-6 | Network failure | yfinance offline / rate-limited | Retry ≥ 2 times, then error message, no partial parquet | Critical |
| PUL-7 | Data integrity | `dv pull SPY --days 30` → head parquet | Columns: date, open, high, low, close, volume — no NaNs, ascending dates | Critical |

### 2.3 Model Pipeline (`dv train`)

| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| MOD-1 | Default HMM | `dv train AAPL` | Fits 3-state HMM, outputs state sequence JSON | Critical |
| MOD-2 | AR model | `dv train AAPL --model ar --lags 5` | Fits AR(5), outputs state sequence | Critical |
| MOD-3 | HMM custom states | `dv train AAPL --model hmm --states 4` | 4 states in output | Major |
| MOD-4 | Insufficient data | `dv train AAPL --days 10` (default needs more) | Error with hint to increase lookback | Major |
| MOD-5 | Model reproducibility | `dv train AAPL` twice (same version) | Identical state sequence for HMM | Major |
| MOD-6 | AR discretization | `dv train AAPL --model ar` | Output states are integers (not floats) | Critical |

### 2.4 Backtesting (`dv backtest`)

| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| BT-1 | Default backtest | `dv backtest AAPL` | Runs vectorbt, returns metrics (sharpe, DD, total return, trades count) | Critical |
| BT-2 | Custom state | `dv backtest AAPL --state 2` | Only enters when state_sequence == 2 | Critical |
| BT-3 | Custom trigger | `dv backtest AAPL --trigger price_cross_above_vwap` | Entries only when price crosses above VWAP | Critical |
| BT-4 | Custom action | `dv backtest AAPL --action short` | Short positions only | Major |
| BT-5 | No model run | `dv backtest AAPL` before any `dv train` | Trains HMM implicitly OR errors with helpful message | Major |
| BT-6 | Empty state sequence | Backtest with symbol that has no states | Error, no silent pass | Critical |
| BT-7 | Metrics completeness | Any successful backtest | Output includes: sharpe, max_drawdown, win_rate, total_return, num_trades, total_days | Major |

### 2.5 No-Overnight Enforcement

| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| NOO-1 | Intraday data absent | `dv pull AAPL --days 30` | Data is daily EOD only; no intraday timestamps | Critical |
| NOO-2 | Backtest fills | Any `dv backtest` run | All entries/exits occur at same-day close (intraday fills impossible) — verified by comparing entry index timestamps | Critical |
| NOO-3 | vectorbt config | Code review of backtester | `from_signals` uses `close` (daily), not minute/intraday bars | Critical |
| NOO-4 | State assignment | `dv train AAPL` output | Each state maps to a full trading day, not sub-day | Major |

### 2.6 Anti-Lookahead Bias

| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| ALB-1 | VWAP calculation | Code review of indicator logic | VWAP for day T uses only data from day T (not future days) | Critical |
| ALB-2 | Prev day levels | `previous_close`, `previous_high`, `previous_low` | Values from T-1 only; never T+1 leaked into T's signal | Critical |
| ALB-3 | Rolling indicators | RMA, moving averages on volume/returns | Window of size N ending at day T; no data from T+1 | Critical |
| ALB-4 | HMM training | HMM fit on historical returns | Model trained only on data prior to current day in backtest walk-forward | Critical |
| ALB-5 | Backtest signal generation | Code review of entry logic | Signal for day T computed before trade execution on day T (same-day close) | Critical |

### 2.7 Indicator Correctness

| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| IND-1 | VWAP | Known OHLCV data vs manual VWAP calc | Matches within float tolerance (<0.001%) | Critical |
| IND-2 | Previous close/high/low | `dv pull SPY --days 3` | T's prev_close matches T-1's close; prev_high matches T-1's high | Critical |
| IND-3 | Relative volume | 30-day window with one outlier day | Relative volume outlier = today_volume / rolling_mean(30d) ± stddev | Major |
| IND-4 | RMA (volume/returns) | Manual calculation vs library | Matches for known input | Major |
| IND-5 | Missing data | Gapped dates in Parquet (holidays) | Indicators compute correctly; no NaNs from gaps | Major |

### 2.8 JSON Output Format

| # | Test | Input | Expected | Severity |
|---|------|-------|----------|----------|
| OUT-1 | `dv train` JSON output | `dv train AAPL --format json` | Valid JSON with `symbol`, `model`, `states` (int array), `params` | Major |
| OUT-2 | `dv backtest` JSON output | `dv backtest AAPL --format json` | Valid JSON with `metrics`, `equity_curve`, `trades` | Major |
| OUT-3 | Prettified JSON | `--json` or `--format json` | `json.dumps(indent=2)` output, parseable | Minor |
| OUT-4 | Table output (default) | No `--format` flag | Human-readable table via `rich` or `PrettyTable` | Minor |
| OUT-5 | Stderr separation | Run with redirect `> out.json 2> err.log` | JSON only on stdout, warnings/errors only on stderr | Minor |

---

## 3. Minimal Validation Commands (Neo's Pre-Handoff Gate)

Neo must run these locally before any handoff. All must exit 0 (or exit 1 with a graceful message for error cases):

### Smoke Tests
```bash
# CLI boots
$ dv --help

# Data fetch + cache
$ dv pull SPY --days 30
$ dv pull SPY --days 30          # should hit cache
$ dv pull ZZZZ 2>&1               # should error gracefully

# Model training
$ dv train SPY
$ dv train SPY --model ar --lags 3

# Backtest
$ dv backtest SPY
$ dv backtest SPY --state 1 --trigger price_cross_above_vwap
$ dv backtest SPY --format json

# Edge cases
$ dv train SPY --days 5          # insufficient data
$ dv backtest ZZZZ               # no data for symbol
```

### Automated Checks
```bash
# JSON validation
$ dv backtest SPY --format json | python -c "import sys,json; json.load(sys.stdin); print('JSON OK')"

# State sequence integrity
$ dv train SPY --format json | python -c "
import sys, json
d = json.load(sys.stdin)
assert 'states' in d
assert all(isinstance(s, int) for s in d['states'])
print(f'States OK: {len(d[\"states\"])} states')
"

# Metrics completeness
$ dv backtest SPY --format json | python -c "
import sys, json
d = json.load(sys.stdin)
for key in ['sharpe', 'max_drawdown', 'num_trades', 'total_return']:
    assert key in d['metrics'], f'Missing metric: {key}'
print('Metrics OK')
"
```

---

## 4. Release Gate Criteria

The following MUST all pass before the CLI can be released to Frank:

| Criterion | Status Required |
|-----------|----------------|
| **All Critical tests PASS** | 100% required |
| **All Major tests PASS** | 100% required (or workarounds documented) |
| **Zero crashes with unhandled exceptions** | All error paths must exit cleanly |
| **No lookahead bias verified by code review** | Seraph sign-off required |
| **No overnight positions in backtest results** | Seraph sign-off required |
| **Parquet files contain valid OHLCV data** | Spot-check 3 symbols required |
| **JSON output is parseable** | Automated validation must pass |
| **Cache invalidation works** | Fresh/stale test must pass |

---

## 5. Security Checklist

| # | Check | Method |
|---|-------|--------|
| SEC-1 | No hardcoded API keys, tokens, or credentials | Static scan of all `.py` files |
| SEC-2 | No credential logging in stderr/stdout | Review all `print()` and `logger` calls |
| SEC-3 | yfinance rate limit handling | Retry logic + backoff present |
| SEC-4 | Path traversal in data directory | Parquet save path uses symbol sanitization (no `/`, `..`) |
| SEC-5 | JSON injection in CLI output | Output is structured data, not raw input echo |
| SEC-6 | Dependencies audited for known CVEs | `pip-audit` or `safety check` on requirements |

---

## 6. QA Execution Order

The QA pass will follow this sequence after Neo's deliverable:

1. **Smoke test** — basic CLI invocation (Section 3 commands)
2. **Data layer tests** — PUL-1 through PUL-7
3. **Model tests** — MOD-1 through MOD-6
4. **Backtest tests** — BT-1 through BT-7
5. **No-overnight verification** — NOO-1 through NOO-4
6. **Anti-lookahead code review** — ALB-1 through ALB-5
7. **Indicator correctness** — IND-1 through IND-5
8. **Security sweep** — SEC-1 through SEC-6
9. **Output format validation** — OUT-1 through OUT-5
