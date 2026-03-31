"""
main.py  —  Step 1 (Schema RAG) wire-up

Changes from original:
- schema_agent.build_index(schema_metadata) is called once after extraction to
  build the embedding index.
- intent_agent.classify_intent() and sql_agent.generate_sql() now receive
  *schema_agent* instead of a pre-built schema_text string, so they can each
  call get_relevant_schema() per query.
- SQLAgent.__init__ no longer receives schema_text (it's fetched per-query now).
- The single-retry fix_query call is unchanged here (Step 4 will expand it to
  a configurable retry loop).
- All other logic is identical to the original.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from db.connector import DatabaseConnector
from db.schema_extractor import SchemaExtractor
from agents.schema_agent import SchemaAgent
from agents.intent_agent import IntentAgent
from agents.sql_agent import SQLAgent
from agents.insight_agent import InsightAgent
from security.security_gate import SecurityGate
from utils.file_manager import FileManager
from utils.logger import Logger


def main():
    settings = Settings()
    logger = Logger(settings.LOG_DIR)
    file_manager = FileManager(settings.OUTPUT_DIR)

    logger.log_system("Starting NL-SQL")

    # --- Database -----------------------------------------------------------
    db_connector = DatabaseConnector(settings.DB_CONFIG, logger)
    connection = db_connector.connect()

    schema_extractor = SchemaExtractor(connection, logger)
    schema_metadata = schema_extractor.extract()

    # --- Schema Agent (validate + build RAG index) --------------------------
    schema_agent = SchemaAgent(settings, logger)

    if not schema_agent.validate_schema(schema_metadata):
        logger.log_system("Schema validation failed")
        return

    # Build the RAG embedding index once at startup.
    # Falls back to full-schema injection if sentence-transformers isn't installed.
    schema_agent.build_index(schema_metadata)

    # Save full schema to output/ for debugging (unchanged behaviour)
    full_schema_text = schema_agent.format_schema(schema_metadata)
    file_manager.save_schema(full_schema_text)
    logger.log_system("Schema saved")

    # --- Agents & security --------------------------------------------------
    security_gate = SecurityGate(settings, logger)
    intent_agent = IntentAgent(settings, logger)
    sql_agent = SQLAgent(settings, logger)          # NOTE: no schema_text arg now
    insight_agent = InsightAgent(settings, logger)

    print("NL-SQL Ready")
    print("Enter your query (or 'exit' to quit):")

    while True:
        user_input = input("\n> ").strip()

        if user_input.lower() == "exit":
            break
        if not user_input:
            continue

        # --- Security gate --------------------------------------------------
        security_result = security_gate.check(user_input)
        if security_result["status"] == "DISALLOWED":
            logger.log_security(f"Request blocked: {security_result['reason']}")
            print(f"[BLOCKED] {security_result['reason']}")
            continue

        # --- Intent classification (receives schema_agent for RAG lookup) ---
        intent_result = intent_agent.classify_intent(user_input, schema_agent)

        if intent_result["classification"] == "DISALLOWED":
            logger.log_security(f"Intent disallowed: {intent_result['reason']}")
            print(f"[REJECTED] {intent_result['reason']}")
            continue

        if intent_result["classification"] == "INCOMPLETE":
            print(f"[CLARIFICATION NEEDED] {intent_result['question']}")
            continue

        # --- SQL generation (receives schema_agent for RAG lookup) ----------
        # AST validation happens inside generate_sql(); only safe SELECTs come back.
        sql_queries = sql_agent.generate_sql(user_input, intent_result, schema_agent)

        if not sql_queries:
            print("[ERROR] Could not generate valid SQL queries")
            continue

        results = []
        for query in sql_queries:
            result = db_connector.execute_query(query)

            # Single-retry self-heal (Step 4 will expand this to MAX_RETRIES)
            if result["status"] == "error":
                fixed_query = sql_agent.fix_query(query, result["error"])
                if fixed_query:
                    result = db_connector.execute_query(fixed_query)
                    query = fixed_query   # track the actually-executed query

            if result["status"] == "success":
                row_count = len(result["data"])
                if row_count > settings.MAX_RECORDS:
                    print(
                        f"[LIMIT EXCEEDED] Query returned {row_count} records, "
                        f"limit is {settings.MAX_RECORDS}. "
                        "Please refine your request."
                    )
                    break
                results.append(
                    {
                        "query": query,
                        "data": result["data"],
                        "columns": result["columns"],
                    }
                )
            else:
                print(f"[SQL ERROR] {result['error']}")
                break

        if results:
            insights = insight_agent.generate_insights(user_input, results)
            print(f"\n{insights}")
            file_manager.save_insights(user_input, results, insights)

    db_connector.close()
    logger.log_system("Shutdown")


if __name__ == "__main__":
    main()