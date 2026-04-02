from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any, Tuple

class BaseModel(ABC):
    def __init__(self, **params: Any):
        self.params = params
        self.is_fitted = False

    @abstractmethod
    def fit(self, df: pd.DataFrame) -> None:
        """Fit model to historical data."""
        pass

    @abstractmethod
    def infer_states(self, df: pd.DataFrame) -> pd.Series:
        """
        Infer states for the provided dataset based on the fitted model.
        Returns a Pandas Series of state integers aligned with df.index.
        """
        pass
