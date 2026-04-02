import pandas as pd
import numpy as np
import logging
from dejavu.models.base import BaseModel

logger = logging.getLogger(__name__)

class AutoReg(BaseModel):
    def fit(self, df: pd.DataFrame) -> None:
        logger.info(f"Fitting AR with params: {self.params}")
        # TODO: Implement statsmodels AutoReg fit logic
        self.is_fitted = True

    def infer_states(self, df: pd.DataFrame) -> pd.Series:
        logger.info(f"Inferring states with AR")
        # TODO: Implement strict walk-forward logic. Currently returning dummy states.
        # Random states between 0 and 2
        states = np.random.randint(0, 3, len(df))
        return pd.Series(states, index=df.index, name="state")
