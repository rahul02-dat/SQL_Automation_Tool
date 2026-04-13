"""
utils/prompt_compiler.py
------------------------
Loads .txt prompt templates from disk and injects runtime variables.

compile_sql_prompt() now accepts an optional chat_history list so the
LLM can resolve follow-up questions ("What about in New York?").
"""

from pathlib import Path
import json


class PromptCompiler:
    def __init__(self, prompts_dir):
        self.prompts_dir = Path(prompts_dir)

    # ── Internal helpers ──────────────────────────────────────────────────────
    def _load_prompt(self, filename: str) -> str:
        path = self.prompts_dir / filename
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # ── Intent prompt (kept for backwards compatibility) ──────────────────────
    def compile_intent_prompt(
        self,
        user_input: str,
        schema_text: str,
        policies: dict,
    ) -> str:
        template      = self._load_prompt("intent_prompt.txt")
        policies_text = self._format_policies(policies)
        return template.format(
            user_input = user_input,
            schema     = schema_text,
            policies   = policies_text,
        )

    # ── Unified SQL prompt (intent + SQL in one call) ─────────────────────────
    def compile_sql_prompt(
        self,
        user_input: str,
        schema_text: str,
        intent_result: dict,          # kept for API compatibility; not used here
        chat_history: list[dict] | None = None,
    ) -> str:
        """
        Compile the unified sql_prompt.txt template.

        chat_history — list of {"user": "...", "sql": "..."} dicts from
                       the rolling memory buffer in main.py.
        """
        template = self._load_prompt("sql_prompt.txt")

        # ── Format chat history block ─────────────────────────────────────────
        history_lines: list[str] = []
        if chat_history:
            for turn in chat_history:
                history_lines.append(f"  User : {turn.get('user', '')}")
                history_lines.append(f"  SQL  : {turn.get('sql',  '')}")
                history_lines.append("")
        chat_history_text = "\n".join(history_lines) if history_lines else "(none)"
        history_count     = len(chat_history) if chat_history else 0

        # ── Policies ──────────────────────────────────────────────────────────
        policies_text = ", ".join(
            self._get_policies_list()
        )

        return template.format(
            user_input    = user_input,
            schema        = schema_text,
            chat_history  = chat_history_text,
            history_count = history_count,
            policies      = policies_text,
            # Legacy placeholders (kept so old prompts don't break)
            tables        = "",
            columns       = "",
            filters       = "",
        )

    # ── Insight prompt (unchanged) ────────────────────────────────────────────
    def compile_insight_prompt(self, user_input: str, results: list) -> str:
        template     = self._load_prompt("insight_prompt.txt")
        results_text = self._format_results(results)
        return template.format(
            user_input = user_input,
            results    = results_text,
        )

    # ── Formatting helpers ────────────────────────────────────────────────────
    def _format_policies(self, policies: dict) -> str:
        lines: list[str] = []
        if "disallowed_intents" in policies:
            lines.append("Disallowed Intents:")
            for intent in policies["disallowed_intents"]:
                lines.append(f"  - {intent}")
        if "require_explicit" in policies:
            lines.append("\nRequire Explicit:")
            for item in policies["require_explicit"]:
                lines.append(f"  - {item}")
        return "\n".join(lines)

    def _get_policies_list(self) -> list[str]:
        """Return a flat list of disallowed intent names (used in sql_prompt)."""
        # We don't have settings here — return a sensible default.
        # The actual values come from global_policies.yaml at runtime.
        return [
            "modify_data", "delete_data", "create_schema",
            "drop_schema", "access_credentials", "export_full_table",
        ]

    def _format_results(self, results: list) -> str:
        lines: list[str] = []
        for i, result in enumerate(results, 1):
            lines.append(f"Query {i}: {result['query']}")
            lines.append(f"Columns: {', '.join(result['columns'])}")
            lines.append(f"Row Count: {len(result['data'])}")
            lines.append("")
            if result["data"]:
                lines.append("Sample Data (first 5 rows):")
                for row in result["data"][:5]:
                    lines.append(f"  {row}")
                lines.append("")
        return "\n".join(lines)