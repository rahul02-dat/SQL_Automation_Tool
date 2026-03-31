"""
agents/sql_agent.py  —  Step 1 (Schema RAG) + Step 2 (AST Security) upgrade

Step 1 changes:
- __init__ no longer accepts a static schema_text string.
- generate_sql() accepts a *schema_agent* reference and calls
  schema_agent.get_relevant_schema(user_input) to inject only relevant tables.

Step 2 changes:
- After the LLM produces a query, _validate_ast() parses it with sqlglot.
- Any statement whose AST root is NOT a SELECT is rejected before execution.
- This replaces the fragile English-keyword blocking in IntentClassifier that
  caused false positives (e.g. "When did John *create* his account?").
- fix_query() also runs the repaired query through the same AST check.
"""

from __future__ import annotations

import ollama
from utils.prompt_compiler import PromptCompiler

# ---------------------------------------------------------------------------
# Optional sqlglot import — graceful fallback if not installed
# ---------------------------------------------------------------------------
try:
    import sqlglot
    import sqlglot.expressions as exp
    _SQLGLOT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SQLGLOT_AVAILABLE = False


class SQLAgent:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)

        if not _SQLGLOT_AVAILABLE:
            self.logger.log_system(
                "sqlglot not installed — AST validation disabled. "
                "Install with: pip install sqlglot"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_sql(self, user_input: str, intent_result: dict, schema_agent) -> list[str]:
        """
        Generate and return validated SELECT queries.

        Parameters
        ----------
        schema_agent : SchemaAgent
            Live instance; we call get_relevant_schema() for focused context.
        """
        # --- Schema RAG: inject only relevant tables -----------------------
        relevant_schema = schema_agent.get_relevant_schema(user_input, top_k=4)

        prompt = self.prompt_compiler.compile_sql_prompt(
            user_input, relevant_schema, intent_result
        )

        try:
            response = ollama.chat(
                model=self.settings.OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            sql_text = response["message"]["content"].strip()
            raw_queries = self._extract_queries(sql_text)

            # --- Step 2: AST validation ------------------------------------
            safe_queries = []
            for q in raw_queries:
                validation = self._validate_ast(q)
                if validation["valid"]:
                    safe_queries.append(q)
                else:
                    self.logger.log_system(
                        f"AST validation blocked query: {validation['reason']}"
                    )

            self.logger.log_system(
                f"Generated {len(raw_queries)} queries, "
                f"{len(safe_queries)} passed AST validation."
            )
            return safe_queries

        except Exception as e:
            self.logger.log_system(f"SQL generation error: {str(e)}")
            return []

    def fix_query(self, query: str, error_message: str) -> str | None:
        """Ask the LLM to repair a failing query, then re-validate via AST."""
        prompt = (
            f"The following SQL query resulted in an error:\n\n"
            f"QUERY:\n{query}\n\n"
            f"ERROR:\n{error_message}\n\n"
            "Please fix the query to resolve this error. "
            "Return ONLY the corrected SQL query without any explanation.\n\n"
            "CORRECTED QUERY:"
        )

        try:
            response = ollama.chat(
                model=self.settings.OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            fixed_sql = response["message"]["content"].strip()
            queries = self._extract_queries(fixed_sql)

            if not queries:
                return None

            fixed = queries[0]

            # Re-validate the repaired query
            validation = self._validate_ast(fixed)
            if not validation["valid"]:
                self.logger.log_system(
                    f"Repaired query failed AST validation: {validation['reason']}"
                )
                return None

            self.logger.log_system("Query fixed and validated successfully")
            return fixed

        except Exception as e:
            self.logger.log_system(f"Query fix error: {str(e)}")
            return None

    # ------------------------------------------------------------------
    # Step 2: AST-based security validation
    # ------------------------------------------------------------------

    def _validate_ast(self, query: str) -> dict:
        """
        Parse *query* with sqlglot and reject anything that is not a SELECT.

        Returns
        -------
        dict with keys:
            valid  : bool
            reason : str   (empty string when valid)
        """
        if not _SQLGLOT_AVAILABLE:
            # Can't validate — allow through (rely on DB read-only mode as
            # the last line of defence)
            return {"valid": True, "reason": ""}

        try:
            statements = sqlglot.parse(query)
        except sqlglot.errors.ParseError as exc:
            return {"valid": False, "reason": f"SQL parse error: {exc}"}

        if not statements:
            return {"valid": False, "reason": "No SQL statement found in LLM output"}

        for stmt in statements:
            if stmt is None:
                continue
            # The root expression type determines the statement kind.
            if not isinstance(stmt, exp.Select):
                blocked_type = type(stmt).__name__
                return {
                    "valid": False,
                    "reason": (
                        f"Non-SELECT statement blocked by AST validator: "
                        f"{blocked_type}"
                    ),
                }

        return {"valid": True, "reason": ""}

    # ------------------------------------------------------------------
    # SQL extraction (unchanged from original)
    # ------------------------------------------------------------------

    def _extract_queries(self, text: str) -> list[str]:
        queries = []
        lines = text.split("\n")
        current_query: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("```"):
                continue

            if stripped.upper().startswith("SELECT"):
                if current_query:
                    q = " ".join(current_query)
                    if q:
                        queries.append(q)
                    current_query = []
                current_query.append(stripped)
            elif current_query:
                current_query.append(stripped)
                if stripped.endswith(";"):
                    q = " ".join(current_query)
                    if q:
                        queries.append(q.rstrip(";"))
                    current_query = []

        if current_query:
            q = " ".join(current_query)
            if q:
                queries.append(q.rstrip(";"))

        return queries