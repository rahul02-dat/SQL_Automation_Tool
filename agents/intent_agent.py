"""
agents/intent_agent.py  —  Step 1 upgrade (Schema RAG integration)

Changes from original:
- classify_intent() now receives a *schema_agent* reference instead of a
  pre-built schema_text string.
- It calls schema_agent.get_relevant_schema(user_input) to retrieve only the
  top-k tables relevant to the current query before compiling the prompt.
- The rest of the parsing logic is unchanged.
"""

import ollama
from utils.prompt_compiler import PromptCompiler


class IntentAgent:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify_intent(self, user_input: str, schema_agent) -> dict:
        """
        Classify the user's intent.

        Parameters
        ----------
        user_input : str
            Raw user query.
        schema_agent : SchemaAgent
            Live SchemaAgent instance with the RAG index already built.
            We call schema_agent.get_relevant_schema(user_input) here so
            only the most relevant table definitions enter the LLM context.
        """
        # --- Schema RAG: fetch only relevant tables -------------------------
        relevant_schema = schema_agent.get_relevant_schema(user_input, top_k=4)

        prompt = self.prompt_compiler.compile_intent_prompt(
            user_input, relevant_schema, self.settings.INTENT_POLICIES
        )

        try:
            response = ollama.chat(
                model=self.settings.OLLAMA_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            result_text = response["message"]["content"].strip()
            return self._parse_intent_response(result_text)

        except Exception as e:
            self.logger.log_system(f"Intent classification error: {str(e)}")
            return {
                "classification": "INCOMPLETE",
                "question": "Could not process your request. Please rephrase.",
                "reason": str(e),
            }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_intent_response(self, response_text: str) -> dict:
        lines = response_text.strip().split("\n")

        classification = None
        reason = None
        question = None
        scope: dict = {}

        for line in lines:
            line = line.strip()
            if line.startswith("CLASSIFICATION:"):
                classification = line.split(":", 1)[1].strip()
            elif line.startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()
            elif line.startswith("QUESTION:"):
                question = line.split(":", 1)[1].strip()
            elif line.startswith("TABLES:"):
                scope["tables"] = [
                    t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()
                ]
            elif line.startswith("COLUMNS:"):
                scope["columns"] = [
                    c.strip() for c in line.split(":", 1)[1].split(",") if c.strip()
                ]
            elif line.startswith("FILTERS:"):
                scope["filters"] = line.split(":", 1)[1].strip()

        if not classification:
            classification = "INCOMPLETE"
            question = "Could not understand your request. Please provide more details."

        return {
            "classification": classification,
            "reason": reason,
            "question": question,
            "scope": scope,
        }