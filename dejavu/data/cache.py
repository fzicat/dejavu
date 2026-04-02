import os
import json
import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from dejavu.config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self, cache_dir: str = settings.DATA_DIR):
        self.cache_dir = cache_dir
        self.manifest_path = os.path.join(self.cache_dir, "manifest.json")
        os.makedirs(os.path.join(self.cache_dir, "features"), exist_ok=True)
        self.manifest: Dict[str, Any] = self._load_manifest()

    def _load_manifest(self) -> Dict[str, Any]:
        if os.path.exists(self.manifest_path):
            with open(self.manifest_path, "r") as f:
                return json.load(f)
        return {}

    def _save_manifest(self):
        with open(self.manifest_path, "w") as f:
            json.dump(self.manifest, f, indent=4)

    def list_cached(self) -> Dict[str, Any]:
        return self.manifest

    def get_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        key = f"{symbol}_{timeframe}"
        if key in self.manifest:
            file_path = os.path.join(self.cache_dir, "features", f"{key}.parquet")
            if os.path.exists(file_path):
                logger.info(f"Loaded {key} from cache")
                return pd.read_parquet(file_path)
        logger.warning(f"Cache miss for {key}")
        return None

    def save_data(self, symbol: str, timeframe: str, df: pd.DataFrame, metadata: Dict[str, Any]):
        key = f"{symbol}_{timeframe}"
        file_path = os.path.join(self.cache_dir, "features", f"{key}.parquet")
        df.to_parquet(file_path)
        self.manifest[key] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "file": file_path,
            "metadata": metadata
        }
        self._save_manifest()
        logger.info(f"Saved {key} to cache")

    def purge(self, symbol: str) -> bool:
        keys_to_delete = [k for k in self.manifest.keys() if k.startswith(f"{symbol}_")]
        deleted = False
        for k in keys_to_delete:
            file_path = self.manifest[k]["file"]
            if os.path.exists(file_path):
                os.remove(file_path)
            del self.manifest[k]
            deleted = True
        self._save_manifest()
        logger.info(f"Purged cached data for {symbol}")
        return deleted
