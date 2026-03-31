"""
security/intent_classifier.py  —  Step 2 upgrade (AST-based security)

What changed:
- The broad modification_keywords list (which blocked "add", "create", "change",
  "remove", "rename", "alter") has been REMOVED.  Those words appear in perfectly
  innocent analytical queries (e.g. "When did John create his account?",
  "Show me orders that were changed last week").
- The security gate's pre-LLM check now only blocks the small set of explicit
  multi-word schema phrases (create table, drop table …) and known credential
  terms.  Single generic English words are no longer blocked here.
- The actual enforcement of SELECT-only SQL is delegated entirely to
  SQLAgent._validate_ast() (sqlglot AST check, Step 2), which fires AFTER the
  LLM has produced concrete SQL — at that point we know exactly what the
  database is being asked to do.

What is kept:
- Schema modification phrases (multi-word, very specific, low false-positive risk).
- Credential-access keywords (password, token, secret, api key, credential, auth).
- The standard return shape so SecurityGate needs no changes.
"""


class IntentClassifier:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.disallowed_intents = settings.INTENT_POLICIES.get("disallowed_intents", [])

    def classify(self, user_input: str) -> dict:
        user_lower = user_input.lower()

        # ------------------------------------------------------------------
        # 1. Multi-word schema modification phrases
        #    These are very specific and rarely appear in normal questions.
        # ------------------------------------------------------------------
        schema_phrases = [
            "create table",
            "drop table",
            "alter table",
            "create database",
            "drop database",
            "truncate table",
        ]
        for phrase in schema_phrases:
            if phrase in user_lower:
                return {
                    "intent": "modify_schema",
                    "allowed": False,
                    "reason": f"Schema modification phrase detected: '{phrase}'",
                }

        # ------------------------------------------------------------------
        # 2. Credential-access terms
        #    Still blocked here as a defence-in-depth layer — even if the
        #    LLM were asked to SELECT password columns we don't want the
        #    user asking for them at all.
        # ------------------------------------------------------------------
        credential_keywords = [
            "password",
            "credential",
            "auth token",
            "secret",
            "api key",
            "access key",
        ]
        for keyword in credential_keywords:
            if keyword in user_lower:
                return {
                    "intent": "access_credentials",
                    "allowed": False,
                    "reason": f"Credential access term detected: '{keyword}'",
                }

        # ------------------------------------------------------------------
        # 3. Everything else is allowed through to the LLM + AST validator.
        # ------------------------------------------------------------------
        return {
            "intent": "query_data",
            "allowed": True,
            "reason": "Pre-LLM intent check passed",
        }