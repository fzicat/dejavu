# Déjà Vu CLI — QA impl-core-002 Report

**Date:** 2026-04-01
**Author:** Seraph
**Deliverable:** Neo's `dejavu-cli-impl-core-002` at `/home/smith/Projects/dejavu/`
**Verdict:** **REVISE**

---

## Acceptance Criteria Table

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | prompt_toolkit REPL behavior | ✅ PASS | PromptSession + WordCompleter replacing cmd2. Tab-autocomplete for all 8 commands. |
| 2 | Alpaca primary + Yahoo fallback normalization | ⚠️ PASS (gap) | Both providers wired, Alpaca attempted first, Yahoo exception fallback works. **Missing:** source indicator in status line, stale cache flagging per concept_delta. |
| 3 | Multi-rule strategy support (AND/OR) | ✅ PASS | `StrategyBuilder.parse()` accumulates via OR, supports `df.eval()` AND/OR compound conditions. Bad conditions safely fall back to False. |
| 4 | Zero fee/slippage disclosure and enforcement | ✅ PASS | `fees=0.0`, `slippage=0.0` enforced in BacktestEngine. Shell prints `ZERO Fees, ZERO Slippage` before running. |
| 5 | Auto-labeled states output | ⚠️ PARTIAL | Labels generated and wired to `do_show` UI. **FAIL:** HMM converges to single state (1/3 states used). Labels show `{0: 'Unknown', 1: 'Bearish / High Vol', 2: 'Unknown'}`. |
| 6 | No-overnight enforcement and session-aware indicators | ✅ PASS | `enforce_no_overnight` correctly identifies last bar per day via index max. VWAP resets daily via groupby. PDH/PDL use previous-day values. |
| 7 | Prior critical issues from bootstrap report | ⚠️ 4/7 fixed | No-overnight, session-indicators, multi-rule, provider params fixed. API key validation, HMM convergence, zero-cost disclosure in metrics still open. |

---

## Blocking Defects

### BLOCKER 1: HMM converges to single state (Critical)
**From:** qa_bootstrap_report.md Issue 2 (still unresolved) + qa_exec_addendum.md Issue 2  
**Severity:** Critical — core ML feature non-functional  
**Evidence:**
```python
from dejavu.models.hmm import GaussianHMMModel
import pandas as pd, numpy as np
np.random.seed(42)
# 200 bars with distinct bull/bear/chop regimes
prices = 100 * np.cumprod(1 + np.concatenate([bull, bear, chop]))
model = GaussianHMMModel(states=3)
model.fit(df); states = model.infer_states(df)
# Result: states.nunique() == 1
# Labels: {0: 'Unknown', 1: 'Bearish / High Vol', 2: 'Unknown'}
```
**Root cause:** Single-feature input (returns only). 1D GaussianHMM routinely collapses to 1 effective state even with artificially distinct regimes.  
**Fix:** Expand to multi-feature input per research_delta §4.3: `[log_return, realized_vol, vwap_deviation, rel_vol]`. Add `random_state` for reproducibility.

### BLOCKER 2: Provider API key validation absent (Critical)
**From:** qa_bootstrap_report.md Issue 2 (unresolved)  
**Severity:** Critical — silent failure, potential credential leak  
**Evidence:**
```python
from dejavu.data.alpaca import AlpacaProvider
alp = AlpacaProvider()  # No error, empty keys accepted
```
**Root cause:** `config.py` defaults to `ALPACA_API_KEY = ""`; provider falls through to empty string. No validation in `AlpacaProvider.__init__`.  
**Fix:** Raise `ValueError("ALPACA_API_KEY not set")` on empty key.

### BLOCKER 3: Zero-cost warning not in metrics output (Major)
**From:** qa_exec_addendum.md Issue 3  
**Severity:** Major — metrics table shows clean results with no warning  
**Evidence:**
```python
from dejavu.ui.tables import display_metrics  # No warning in output
inspect.getsource(display_metrics)             # No mention of zero/slippage/MVP
```
**Root cause:** Warning only in `do_backtest()` via `console.print()`, not in `display_metrics()` table.  
**Fix:** Add warning row to metrics table or pass warning parameter to `display_metrics`.

### BLOCKER 4: `do_use` still ignores partial arguments (Major)
**Severity:** Major — custom ranges/frequencies not functional  
**Evidence:** `do_use()` parses `--range` and `--freq` but hardcoded fallback to 5d/5min if parsing is partial or unexpected.

---

## Non-Blocking Defects

### Issue 5: Source indicator missing from status line (Minor)
**Per concept_delta §1:** Data fetch output must display `[Alpaca IEX]` or `[yahooquery]` source. Currently only shows generic "Data fetched via X".

### Issue 6: Stale cache flagging not implemented (Minor)
**Per concept_delta §1.4:** If both providers fail, should serve stale cache with `POTENTIALLY_STALE` flag. Not implemented.

### Issue 7: `session_type` always 'regular' in Yahoo provider (Minor)
**Severity:** Minor — premarket/after-hours bars not detected  
**Evidence:** `yahoo.py` sets `df['session_type'] = 'regular'` for all bars regardless of time.

### Issue 8: `pmh`/`pml` aliased to `pdh`/`pdl` (Minor)
**From bootstrap report (unresolved)**  
**Evidence:** `features.py` sets `df['pmh'] = df['pdh']` — pre-market and previous-day levels are identical.

### Issue 9: `SessionContext.clear()` uses `self.__init__()` (Minor)
**From bootstrap report (unresolved)** — Non-idiomatic pattern documented.

### Issue 10: No exit condition support in StrategyBuilder (Minor)
**From exec addendum (unresolved)** — Only entry conditions supported, no exit/stop rules.

### Issue 11: AR and RNN models still use random states (Minor)
**From bootstrap report (unresolved for AR/RNN)** — Both `infer_states()` return `np.random.randint(0, 3, len(df))`.

### Issue 12: `df.eval()` security surface (Minor)
Strategy conditions evaluated via `df.eval()` — arbitrary code execution possible with untrusted input. Acceptable for local CLI. Recommended: whitelist column names.

---

## Bootstrap Regression Status

| Bootstrap Issue | Current Status | Notes |
|-----------------|----------------|-------|
| **#1: inf/nan metrics** | ✅ Fixed | Real price data (non-random close prices) now produces valid stats |
| **#2: Provider API key silent** | ❌ Still broken | No validation, still accepts empty key |
| **#3: Provider ignores params** | ✅ Fixed | YahooProvider now uses actual `start_date`, `end_date`, `timeframe` |
| **#4: enforce_no_overnight never fires** | ✅ Fixed (bootstrap) / ✅ Re-verified | Now uses proper last-bar-per-day via index max |
| **#5: StrategyBuilder only parses first rule** | ✅ Fixed | OR accumulation working, multiple tested |
| **#6: Shell ignored args** | ⚠️ Partially fixed | `do_use` now parses args but still has hardcoded fallback |
| **#7: Chart placeholders** | Unchanged | Still placeholders (acceptable for core impl) |
| **#8: Clear() self.__init__()** | Unchanged | Still present |

---

## Recommendation

**REVISE** — Three blocking defects require resolution before next iteration:
1. **HMM convergence** (Critical) — Multi-feature input required per research spec
2. **Provider key validation** (Critical) — Must fail loudly, not silently
3. **Zero-cost disclosure in metrics** (Major) — Warning must appear in all output paths

The foundation is solid: REPL, fallback architecture, multi-rule parsing, and no-overnight enforcement are all functional and correct.

**File:** `/home/smith/Projects/dejavu/qa_impl_core_report.md`
