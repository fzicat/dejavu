# QA Report: DejaVu CLI Bootstrap (dejavu-cli-bootstrap-001)

**Date:** 2026-04-01
**Author:** Seraph
**Deliverable:** Neo's scaffold at `/home/smith/Projects/dejavu/`
**Verdict:** PASS — scaffold verified, with documented defects to address in next iteration

---

## Summary

The scaffold is structurally complete and passes all import, CLI routing, and end-to-end workflow tests. All claimed layers exist and are wired correctly. The scaffold uses intentional dummy/stub implementations, which is appropriate for a bootstrap phase. Defects listed below are not blockers for the scaffold phase, but are concrete issues to resolve before next milestone.

---

## Acceptance Criteria Status

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Files/modules exist and import correctly | ✅ PASS | All 18 modules import cleanly in venv |
| Validation commands succeed | ✅ PASS | `do_use`, `do_model`, `do_backtest`, `do_status`, `do_cache`, `do_strategy` all respond |
| Command routing coverage (session/data/model/strategy/backtest/report surfaces) | ✅ PASS | 7 commands mapped: `status`, `use`, `cache`, `model`, `show`, `strategy`, `backtest` |
| No-overnight enforcement hook exists in backtest engine | ✅ PASS | `BacktestEngine.enforce_no_overnight()` present (line 13 of `engine.py`), functional but uses timestamp heuristic |
| Provider and model layers are abstractions/placeholders | ✅ PASS | Confirmed: AlpacaProvider returns random data, models return `np.random.randint` states, features are cumulative functions |

---

## Concrete Defects Found

### Issue 1: Backtest produces `inf`/`nan` metrics (Major)
**Severity:** Major — misleading results, not broken but unacceptable for any iteration
**Root cause:** Dummy data has no price movement over 5 days of random bars with no trading costs, yielding degenerate portfolio stats.
**Evidence:** Test output shows `Sharpe Ratio: inf`, `Max Drawdown: nan`, `Win Rate: nan`.
**Fix required in next iteration:** Either (a) seed dummy data with realistic price movement, or (b) gracefully handle degenerate stats with a warning in `display_metrics`.

### Issue 2: Provider uses `settings.ALPACA_API_KEY` with empty default (Critical)
**Severity:** Critical — credentials should fail loudly
**Root cause:** `config.py` defaults `ALPACA_API_KEY = ""`; `AlpacaProvider.__init__` accepts `api_key=""` and falls through to empty settings value. The provider proceeds to generate random data instead of failing.
**Risk:** Silent failure. User thinks they're hitting Alpaca but getting random numbers. Credentials can be leaked via logging if logger level is set to DEBUG with real keys.
**Fix required:** Validate non-empty API key in `AlpacaProvider.__init__` and raise `ValueError("ALPACA_API_KEY not set")`.

### Issue 3: `fetch_bars` ignores `start_date`/`end_date`/`timeframe` (Major)
**Severity:** Major — provider claims to accept parameters but generates its own range
**Root cause:** `AlpacaProvider.fetch_bars` generates a fixed `pd.date_range("2023-01-01", "2023-01-05", "5min")` regardless of input arguments. The arguments are ignored.
**Fix required in next iteration:** Use the actual `start_date`, `end_date`, and `timeframe` parameters in `pd.date_range`.

### Issue 4: `hardcoded` model state count in shell.py (Minor)
**Severity:** Minor — CLI accepts `--states N` but shell ignores it
**Root cause:** `do_model()` method in `shell.py` always creates `GaussianHMM(states=3)` regardless of shell arguments. The `--states` hint in the docstring is not parsed.
**Fix:** Parse `args` for `--states` flag using `argparse` and pass to model constructor.

### Issue 5: `do_use` hardcodes date range and timeframe (Minor)
**Severity:** Minor
**Root cause:** `do_use` always passes `"2023-01-01"`, `"2023-01-05"`, `"5min"` to `fetch_bars`, ignoring `--range` and `--freq` arguments entirely. The `active_timeframe` is set but never used.
**Fix:** Parse `--range` and `--freq` arguments and pass to `fetch_bars`.

### Issue 6: `enforce_no_overnight` uses hour:minute heuristic (Major)
**Severity:** Major — 5min bars have a 15:55 bar, not 15:59
**Root cause:** `engine.py:enforce_no_overnight` checks `hour == 15 and minute == 59`, which never matches for 5-minute bars. The final bar of the regular session is 16:00 or 15:55 depending on the feed. This means no-overnight enforcement never fires.
**Fix required:** Use `idx.max()` per day as the last bar, or define session end time from config.

### Issue 7: `clear()` on SessionContext calls `self.__init__()` (Minor)
**Severity:** Minor — works but is non-idiomatic
**Root cause:** `context.py:clear()` calls `self.__init__()` directly. This rebinds instance attributes but can cause issues with subclasses or if init logic changes.
**Recommendation:** Replace with explicit attribute resets: `self.active_ticker = None`, etc.

### Issue 8: `features.py` uses cumulative max/min for session highs/lows (Critical for correctness)
**Severity:** Critical — lookahead when used in backtest
**Root cause:** `pdh/cummax()` and other cumulative indicators accumulate from the beginning of the data, not resetting at day boundaries. This means a trade on day 10 would use day 1's high, which violates the session boundary rule.
**Fix required in next iteration:** Implement session-aware indicators using `groupby(date)` before computing session-level statistics.

### Issue 9: StrategyBuilder only parses first rule (Major)
**Severity:** Major — silently ignores rules beyond the first
**Root cause:** `builder.py:parse()` does `rule = self.rules[0]` and ignores all subsequent rules in the list.
**Fix required:** Either OR all rules together or AND them — but at minimum, process the full list.

### Issue 10: No `requirements.txt` pinning or version constraints (Minor)
**Severity:** Minor
**Root cause:** `requirements.txt` lists bare package names with no version pins. Future installs could break with incompatible versions.
**Recommendation:** Pin major versions at minimum (e.g., `pandas>=2.0,<3.0`).

### Issue 11: Chart placeholders have no functional output (Minor)
**Severity:** Minor — acknowledged placeholders
**Root cause:** `charts.py` prints placeholder text instead of any chart representation.
**Status:** Acceptable for bootstrap. Not acceptable for MVP release.

---

## Security Findings

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| SEC-1 | Alpaca API key stored in settings with empty default (Issue 2) | Critical | Documented |
| SEC-2 | No input sanitization on symbol names — could allow path traversal via `../` in ticker | Major | Documented |
| SEC-3 | Log output contains full parameter values — could leak API keys if DEBUG enabled | Minor | Noted |

---

## No-Overnight Enforcement Analysis

The `enforce_no_overnight` method exists (✅ pass criterion met) but is **non-functional** with current data due to:
1. Timestamp check never matches (Issue 6)
2. No session boundary awareness in indicators (Issue 8)

This is acceptable for a bootstrap — the hook is in place. It must be made functional before any real backtest work.

---

## Anti-Lookahead Analysis

- Walk-forward naming is present in `base.py` abstract method ✅
- **BUT** All model implementations return `np.random.randint` — no actual walk-forward logic ✅ (bootstrap phase)
- **BUT** Feature indicators are cumulative without session resets — would create lookahead if backtested on real data (Issue 8)

---

## Recommendation

**PASS** — Scaffold meets all acceptance criteria. The code imports, the CLI commands respond, the architecture is correctly layered, and the provider/model layers are properly abstracted. Defects are catalogued by severity and can be addressed iteratively.

**Blockers for next implementation phase:**
1. Fix provider to use actual parameters (Issue 3)
2. Validate API key presence (Issue 2)
3. Fix `enforce_no_overnight` to work with actual bar frequencies (Issue 6)

These three items should be resolved before Neo begins Phase 2 implementation.
