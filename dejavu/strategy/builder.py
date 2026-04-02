import logging
import re
from typing import Any, Dict, List, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


class StrategyBuilder:
    def __init__(self):
        self.rules: List[Dict[str, str]] = []

    def _normalize_condition(self, condition: str) -> str:
        cleaned = condition.strip()
        cleaned = re.sub(r"^if\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+then\s+(long|exit)\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace("AND", "and").replace("OR", "or")
        cleaned = re.sub(r"\bprice\b", "close", cleaned, flags=re.IGNORECASE)
        if re.search(r"\bstate\b", cleaned, flags=re.IGNORECASE):
            raise ValueError("State conditions are no longer allowed in strategies. Bind model/state at backtest time.")
        return cleaned

    def add_rule(self, condition: str, action: str = "long"):
        normalized_action = action.strip().lower()
        if normalized_action not in {"long", "exit"}:
            raise ValueError("Action must be one of: long, exit")
        normalized_condition = self._normalize_condition(condition)
        self.rules.append({"condition": normalized_condition, "action": normalized_action})
        logger.debug("Added %s rule: %s", normalized_action, normalized_condition)

    def list_rules(self) -> List[Dict[str, str]]:
        return list(self.rules)

    def _evaluate_condition(self, df: pd.DataFrame, condition: str) -> pd.Series:
        try:
            result = df.eval(condition)
            if not isinstance(result, pd.Series):
                raise ValueError("Condition did not evaluate to a Series")
            return result.fillna(False).astype(bool)
        except Exception as exc:
            logger.error("Rule evaluation failed for '%s': %s", condition, exc)
            raise ValueError(f"Invalid rule '{condition}': {exc}") from exc

    def evaluate(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        logger.info("Evaluating %s strategy rules", len(self.rules))
        if not self.rules:
            false_series = pd.Series(False, index=df.index)
            return false_series, false_series

        entries = pd.Series(False, index=df.index)
        exits = pd.Series(False, index=df.index)

        for rule in self.rules:
            mask = self._evaluate_condition(df, rule["condition"])
            if rule["action"] == "long":
                entries = entries | mask
            elif rule["action"] == "exit":
                exits = exits | mask

        if not any(rule["action"] == "exit" for rule in self.rules):
            exits = ~entries

        return entries.astype(bool), exits.astype(bool)
