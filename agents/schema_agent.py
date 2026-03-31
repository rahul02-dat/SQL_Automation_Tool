"""
agents/schema_agent.py  —  Schema RAG (Step 1 upgrade)

Changes from original:
- Added SchemaRAG inner-class that embeds each table's schema text using
  sentence-transformers/all-MiniLM-L6-v2 (runs fully locally, ~80 MB).
- SchemaAgent.build_index() must be called once after extract() to build the
  FAISS-style cosine index (pure NumPy, no FAISS dependency needed).
- SchemaAgent.retrieve(query, top_k=4) returns only the top-k most relevant
  table schemas as a single formatted string.
- format_schema() is kept unchanged so the full schema can still be saved
  to output/schema.txt for debugging.
"""

from __future__ import annotations

import numpy as np
from utils.prompt_compiler import PromptCompiler


# ---------------------------------------------------------------------------
# Optional import — graceful fallback if sentence-transformers isn't installed
# ---------------------------------------------------------------------------
try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ST_AVAILABLE = False


class SchemaRAG:
    """
    Lightweight RAG index over table schemas.

    Each table is represented as a short text blob:
        "TABLE customers COLUMNS customer_id INTEGER, name TEXT, ..."

    At query time we embed the user query with the same model and return the
    top-k tables by cosine similarity.
    """

    EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, logger):
        self.logger = logger
        self._model = None
        self._table_texts: list[str] = []      # one entry per table
        self._table_meta: list[dict] = []      # raw table dicts from schema_metadata
        self._embeddings: np.ndarray | None = None  # shape (n_tables, dim)

    # ------------------------------------------------------------------
    # Index building
    # ------------------------------------------------------------------

    def build(self, schema_metadata: dict) -> None:
        """Embed every table and store vectors in memory."""
        if not _ST_AVAILABLE:
            self.logger.log_system(
                "sentence-transformers not installed — Schema RAG disabled, "
                "falling back to full-schema injection."
            )
            return

        self._model = SentenceTransformer(self.EMBED_MODEL)
        self._table_meta = schema_metadata.get("tables", [])
        self._table_texts = [self._table_to_text(t) for t in self._table_meta]

        if not self._table_texts:
            return

        self._embeddings = self._model.encode(
            self._table_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,   # unit vectors → dot product = cosine
        )
        self.logger.log_system(
            f"Schema RAG index built: {len(self._table_texts)} tables embedded."
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int = 4) -> list[dict]:
        """
        Return up to top_k table dicts most relevant to *query*.
        Falls back to all tables if the index is unavailable.
        """
        if self._embeddings is None or self._model is None:
            return self._table_meta          # fallback: return everything

        query_vec = self._model.encode(
            [query], convert_to_numpy=True, normalize_embeddings=True
        )[0]                                 # shape (dim,)

        scores = self._embeddings @ query_vec  # cosine similarity for each table
        top_indices = np.argsort(scores)[::-1][:top_k]

        retrieved = [self._table_meta[i] for i in top_indices]
        names = [t["name"] for t in retrieved]
        self.logger.log_system(f"Schema RAG retrieved tables: {names}")
        return retrieved

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _table_to_text(table: dict) -> str:
        """Convert a table dict to a short descriptive string for embedding."""
        col_parts = ", ".join(
            f"{c['name']} {c['type']}" for c in table.get("columns", [])
        )
        fk_parts = ""
        if table.get("foreign_keys"):
            fk_strs = [
                f"{fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}"
                for fk in table["foreign_keys"]
            ]
            fk_parts = " FK: " + "; ".join(fk_strs)
        return f"TABLE {table['name']} COLUMNS {col_parts}{fk_parts}"


# ---------------------------------------------------------------------------
# SchemaAgent — public API consumed by main.py and the other agents
# ---------------------------------------------------------------------------

class SchemaAgent:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)
        self._rag = SchemaRAG(logger)
        self._schema_metadata: dict = {}

    # ------------------------------------------------------------------
    # One-time startup methods
    # ------------------------------------------------------------------

    def validate_schema(self, schema_metadata: dict) -> bool:
        if not schema_metadata:
            self.logger.log_system("Schema metadata is empty")
            return False
        if "tables" not in schema_metadata or not schema_metadata["tables"]:
            self.logger.log_system("No tables found in schema")
            return False
        return True

    def build_index(self, schema_metadata: dict) -> None:
        """
        Call this once after extract() and validate_schema().
        Stores metadata and builds the RAG embedding index.
        """
        self._schema_metadata = schema_metadata
        self._rag.build(schema_metadata)

    # ------------------------------------------------------------------
    # Per-query retrieval (used by IntentAgent and SQLAgent)
    # ------------------------------------------------------------------

    def get_relevant_schema(self, query: str, top_k: int = 4) -> str:
        """
        Return a formatted schema string containing only the top-k tables
        most relevant to *query*.  This is what gets injected into LLM prompts.
        """
        relevant_tables = self._rag.retrieve(query, top_k=top_k)
        return self._format_tables(relevant_tables)

    # ------------------------------------------------------------------
    # Full schema (kept for file-saving / debugging)
    # ------------------------------------------------------------------

    def format_schema(self, schema_metadata: dict) -> str:
        """Return the complete schema as a human-readable string."""
        return self._format_tables(schema_metadata.get("tables", []))

    # ------------------------------------------------------------------
    # Internal formatter (shared by both methods above)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tables(tables: list[dict]) -> str:
        lines = ["DATABASE SCHEMA", "=" * 50, ""]
        for table in tables:
            lines.append(f"TABLE: {table['name']}")
            lines.append("-" * 50)
            for column in table.get("columns", []):
                col_info = f"  {column['name']} ({column['type']})"
                if column.get("primary_key"):
                    col_info += " [PRIMARY KEY]"
                if column.get("nullable") is False:
                    col_info += " [NOT NULL]"
                lines.append(col_info)
            if table.get("foreign_keys"):
                lines.append("")
                lines.append("  Foreign Keys:")
                for fk in table["foreign_keys"]:
                    lines.append(
                        f"    {fk['column']} -> "
                        f"{fk['referenced_table']}.{fk['referenced_column']}"
                    )
            lines.append("")
        return "\n".join(lines)