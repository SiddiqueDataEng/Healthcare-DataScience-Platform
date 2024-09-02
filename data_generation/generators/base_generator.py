"""
Base Generator class — all table generators inherit from this.
"""
import os
import math
import numpy as np
import pandas as pd
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from loguru import logger


class BaseGenerator(ABC):
    """
    Abstract base class for all data generators.

    Subclasses must implement:
        - generate_batch(batch_idx, start_idx, end_idx) -> pd.DataFrame
        - table_name() -> str   (return the snake_case table name)

    Provides:
        - Batch chunking and file writing
        - Reproducible seeding
        - Context management (pass FK ids between generators)
    """

    def __init__(
        self,
        n_records: int,
        seed: int = 42,
        output_dir: str = "./data/raw",
        output_format: str = "parquet",
        batch_size: int = 100_000,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.n_records = n_records
        self.seed = seed
        self.output_dir = Path(output_dir)
        self.output_format = output_format
        self.batch_size = min(batch_size, n_records)
        self.context = context or {}
        self.rng = np.random.default_rng(seed)

        # Faker instance with fixed seed
        from faker import Faker
        self.fake = Faker()
        Faker.seed(seed)

        # Output directory for this table
        self.table_output_dir = self.output_dir / self.table_name()
        self.table_output_dir.mkdir(parents=True, exist_ok=True)

    def table_name(self) -> str:
        """Derive table name from class name. Override in subclasses for explicit naming."""
        return self.__class__.__name__.lower().replace("generator", "")

    @abstractmethod
    def generate_batch(self, batch_idx: int, start_idx: int, end_idx: int) -> pd.DataFrame:
        """Generate a single batch of records. Must return a DataFrame."""
        pass

    def post_process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optional hook: called on each batch before writing. Override to add custom logic."""
        return df

    def generate(self) -> Dict[str, Any]:
        """
        Main entry point. Generates all records in batches and writes to disk.
        Returns updated context dict with generated IDs for downstream generators.
        """
        n_batches = math.ceil(self.n_records / self.batch_size)
        all_ids = []

        for batch_idx in range(n_batches):
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, self.n_records)

            df = self.generate_batch(batch_idx, start_idx, end_idx)
            df = self.post_process(df)

            # Collect primary key IDs for context
            pk_col = self._get_pk_column()
            if pk_col and pk_col in df.columns:
                all_ids.extend(df[pk_col].tolist())

            self._write_batch(df, batch_idx)

        # Update context with this table's IDs
        updated_context = {**self.context}
        pk_col = self._get_pk_column()
        if pk_col and all_ids:
            updated_context[f"{self.table_name()}_ids"] = all_ids

        return updated_context

    def _write_batch(self, df: pd.DataFrame, batch_idx: int):
        """Write a batch dataframe to the output file."""
        filename = f"{self.table_name()}_batch_{batch_idx:04d}"
        filepath = self.table_output_dir / filename

        if self.output_format == "parquet":
            df.to_parquet(f"{filepath}.parquet", index=False, compression="snappy")
        elif self.output_format == "csv":
            mode = "w" if batch_idx == 0 else "a"
            header = batch_idx == 0
            df.to_csv(f"{filepath}.csv", index=False, mode=mode, header=header)
        elif self.output_format == "json":
            df.to_json(f"{filepath}.json", orient="records", lines=True)

    def _get_pk_column(self) -> Optional[str]:
        """Return the primary key column name. Override if different."""
        return None

    # ─── Utility helpers ────────────────────────────────────────────

    def choice(self, options, size=1, p=None):
        """Weighted random choice."""
        return self.rng.choice(options, size=size, p=p)

    def randint(self, low, high, size=1):
        return self.rng.integers(low, high, size=size)

    def uniform(self, low, high, size=1):
        return self.rng.uniform(low, high, size=size)

    def normal(self, mean, std, size=1):
        return np.abs(self.rng.normal(mean, std, size=size))

    def poisson(self, lam, size=1):
        return self.rng.poisson(lam, size=size)

    def random_dates(self, start_date, end_date, size=1):
        """Generate random dates between start and end."""
        start_ts = pd.Timestamp(start_date).value
        end_ts = pd.Timestamp(end_date).value
        random_ts = self.rng.integers(start_ts, end_ts, size=size)
        return pd.to_datetime(random_ts)

    def format_id(self, prefix: str, idx: int, width: int = 7) -> str:
        return f"{prefix}{str(idx).zfill(width)}"
