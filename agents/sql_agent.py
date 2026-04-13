"""
agents/sql_agent.py
-------------------
Unified agent that performs intent classification AND SQL generation in a
single Ollama call.  Uses the async Ollama client for non-blocking I/O.

LLM output contract (JSON):
{
  "classification": "VALID" | "INCOMPLETE" | "DISALLOWED",
  "reason": "...",
  "question": "...",          // only when INCOMPLETE
  "queries": [                // only when VALID
    {
      "sql":    "SELECT ...",
      "params": ["value1", "value2"]   // parameterized values, in order
    }
  ]
}
"""

import json
import asyncio
from pathlib import Path

try:
    from ollama import AsyncClient
except ImportError:                          # graceful degradation during tests
    AsyncClient = None

from utils.prompt_compiler import PromptCompiler


_SYSTEM_PROMPT = """\
You are a precise SQL expert agent.
Your ONLY job is to classify the user's intent and, when valid, produce
safe, read-only SELECT queries against the provided database schema.

RULES:
1. Output ONLY valid JSON — no markdown fences, no prose, no comments.
2. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE,
   GRANT, REVOKE, or any DDL/DML statement.
3. Use parameterized placeholders (?) for every literal value the user
   supplies (names, dates, numbers, etc.).  Collect the corresponding
   values in the "params" array in the same order.
4. If the request is ambiguous or lacks necessary context, set
   classification to INCOMPLETE and provide a helpful clarifying question.
5. If the request violates the policies, set classification to DISALLOWED.
"""


class SQLAgent:
    """
    Unified Intent + SQL agent.

    Replaces the old separate IntentAgent + SQLAgent pair with a single
    async LLM call that returns a structured JSON object.
    """

    def __init__(self, settings, logger):
        self.settings       = settings
        self.logger         = logger
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)
        self._client        = AsyncClient(host=settings.OLLAMA_BASE_URL) if AsyncClient else None

    # ── Main entry: intent classification + SQL generation ────────────────────
    async def generate_async(
        self,
        user_input: str,
        schema_text: str,
        chat_history: list[dict],
    ) -> dict | None:
        """
        Single async LLM call.
        Returns the parsed JSON dict, or None on unrecoverable error.

        chat_history is a list of {"user": "...", "sql": "..."} dicts
        representing recent conversation turns.
        """
        prompt = self.prompt_compiler.compile_sql_prompt(
            user_input    = user_input,
            schema_text   = schema_text,
            intent_result = {},              # not needed — intent is embedded
            chat_history  = chat_history,
        )

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]

        try:
            response = await self._client.chat(
                model    = self.settings.OLLAMA_MODEL,
                messages = messages,
                options  = {"temperature": 0.0},   # deterministic output
            )
            raw = response["message"]["content"].strip()
            self.logger.log_system("LLM response received (intent+SQL).")
            return self._parse_json_response(raw)

        except Exception as exc:
            self.logger.log_system(f"LLM call error (generate_async): {exc}")
            return None

    # ── Self-healing: fix a failed query ─────────────────────────────────────
    async def fix_query_async(
        self,
        original_sql: str,
        error_history: list[str],
    ) -> tuple[str, list] | None:
        """
        Ask the LLM to fix *original_sql* given the accumulated *error_history*.
        Returns (fixed_sql, params) or None.
        """
        errors_block = "\n".join(f"  - {e}" for e in error_history)
        prompt = (
            "The following SQL query failed. Fix it so it executes correctly.\n\n"
            f"ORIGINAL QUERY:\n{original_sql}\n\n"
            f"ERRORS (in order of attempts):\n{errors_block}\n\n"
            "RULES:\n"
            "  • Return ONLY valid JSON — no markdown, no prose.\n"
            "  • Use parameterized placeholders (?) for all literal values.\n"
            "  • Output format:\n"
            '    {"sql": "SELECT ...", "params": ["val1", "val2"]}\n'
            "  • The query must be a SELECT statement only.\n"
        )

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]

        try:
            response = await self._client.chat(
                model    = self.settings.OLLAMA_MODEL,
                messages = messages,
                options  = {"temperature": 0.0},
            )
            raw = response["message"]["content"].strip()
            data = self._safe_json(raw)
            if data and "sql" in data:
                fixed_sql = data["sql"].strip().rstrip(";")
                params    = data.get("params", [])
                self.logger.log_system("Query fixed by LLM.")
                return fixed_sql, params
            return None

        except Exception as exc:
            self.logger.log_system(f"LLM call error (fix_query_async): {exc}")
            return None

    # ── JSON helpers ──────────────────────────────────────────────────────────
    def _parse_json_response(self, raw: str) -> dict | None:
        """
        Parse the LLM's JSON response.
        Strips accidental markdown fences before parsing.
        """
        data = self._safe_json(raw)
        if data is None:
            self.logger.log_system(
                f"Could not parse LLM JSON. Raw output:\n{raw[:300]}"
            )
            # Degrade gracefully — treat as INCOMPLETE
            return {
                "classification": "INCOMPLETE",
                "reason": "LLM returned unparseable output.",
                "question": "Could not understand your request. Please rephrase.",
                "queries": [],
            }

        # Normalise queries list: strip semicolons from SQL
        for q in data.get("queries", []):
            if "sql" in q:
                q["sql"] = q["sql"].strip().rstrip(";")
            if "params" not in q:
                q["params"] = []

        return data

    @staticmethod
    def _safe_json(text: str) -> dict | None:
        """Strip markdown fences then attempt JSON parse."""
        # Remove ```json ... ``` or ``` ... ``` wrappers
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Drop first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract the first {...} block
            start = cleaned.find("{")
            end   = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    pass
        return None