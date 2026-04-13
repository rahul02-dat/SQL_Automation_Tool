"""
agents/schema_agent.py
----------------------
SchemaAgent with RAG-lite dynamic schema injection.

filter_schema() scores every table in the schema against the user's query
using lightweight keyword matching (table names, column names, synonyms)
and returns only the top-N most relevant tables, dramatically shrinking
the context window fed to the LLM.
"""

import re
from utils.prompt_compiler import PromptCompiler

# Maximum number of tables to inject into the LLM prompt
MAX_RELEVANT_TABLES = 5


class SchemaAgent:
    def __init__(self, settings, logger):
        self.settings        = settings
        self.logger          = logger
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)

    # ── Schema validation ─────────────────────────────────────────────────────
    def validate_schema(self, schema_metadata: dict) -> bool:
        if not schema_metadata:
            self.logger.log_system("Schema metadata is empty.")
            return False
        if "tables" not in schema_metadata or not schema_metadata["tables"]:
            self.logger.log_system("No tables found in schema.")
            return False
        return True

    # ── RAG-lite: keyword relevance filter ────────────────────────────────────
    def filter_schema(
        self,
        schema_metadata: dict,
        user_query: str,
        top_n: int = MAX_RELEVANT_TABLES,
    ) -> dict:
        """
        Score each table in *schema_metadata* by how many of its names
        (table name + column names) appear as substrings in *user_query*.
        Return a filtered schema dict containing only the top-*top_n* tables.

        Scoring heuristic (higher = more relevant):
          +3  table name found in query
          +2  column name found in query
          +1  partial token overlap (≥4 chars) between query tokens and names
          +5  bonus if query token is a known relational word for a table
              (e.g. "order" → orders table, "customer" → customers table)
        """
        if not schema_metadata.get("tables"):
            return schema_metadata

        query_lower   = user_query.lower()
        # Tokenise: split on non-alphanumeric characters, keep tokens ≥ 3 chars
        query_tokens  = set(re.split(r"[^a-z0-9]", query_lower))
        query_tokens  = {t for t in query_tokens if len(t) >= 3}

        scored_tables = []

        for table in schema_metadata["tables"]:
            score      = 0
            table_name = table["name"].lower()

            # ── Table-name match ──────────────────────────────────────────────
            if table_name in query_lower:
                score += 3

            # Singular/plural fuzzy bonus (e.g. "order" matches "orders")
            for token in query_tokens:
                # exact token == table name or table name starts with token
                if table_name == token or table_name.startswith(token):
                    score += 5
                    break
                # partial overlap: token inside table_name (e.g. "item" → "order_items")
                if token in table_name and len(token) >= 4:
                    score += 2

            # ── Column-name match ─────────────────────────────────────────────
            for col in table.get("columns", []):
                col_name = col["name"].lower()
                if col_name in query_lower:
                    score += 2
                for token in query_tokens:
                    if col_name == token or col_name.startswith(token):
                        score += 1
                        break

            # ── Foreign-key bonus: pull in referenced tables later ────────────
            # (handled by always including tables referenced from high-score tables)

            scored_tables.append((score, table))

        # Sort descending by score
        scored_tables.sort(key=lambda x: x[0], reverse=True)

        # Always take at least 1 table; cap at top_n
        top_tables = [t for _, t in scored_tables[:top_n]]

        # Expand: if a top table has foreign keys, include referenced tables
        # (up to the hard cap) so JOINs are always possible
        top_names = {t["name"] for t in top_tables}
        for table in top_tables[:]:
            for fk in table.get("foreign_keys", []):
                ref = fk.get("referenced_table", "")
                if ref and ref not in top_names and len(top_tables) < top_n + 2:
                    for _, candidate in scored_tables:
                        if candidate["name"] == ref:
                            top_tables.append(candidate)
                            top_names.add(ref)
                            break

        included_names = [t["name"] for t in top_tables]
        self.logger.log_system(
            f"RAG-lite schema filter: {len(top_tables)}/{len(schema_metadata['tables'])} "
            f"tables selected → {included_names}"
        )

        return {"tables": top_tables}

    # ── Schema formatting (unchanged from original) ───────────────────────────
    def format_schema(self, schema_metadata: dict) -> str:
        lines = [
            "DATABASE SCHEMA",
            "=" * 50,
            "",
        ]

        for table in schema_metadata.get("tables", []):
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
                        f"    {fk['column']} → {fk['referenced_table']}.{fk['referenced_column']}"
                    )

            lines.append("")

        return "\n".join(lines)