"""
NL-SQL — Natural Language to SQL Agent
Refactored: async pipeline, conversational memory, AST validation, retry loop.
"""

import asyncio
import sys
from pathlib import Path
from collections import deque

sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from db.connector import DatabaseConnector
from db.schema_extractor import SchemaExtractor
from agents.schema_agent import SchemaAgent
from agents.sql_agent import SQLAgent          # now handles intent + SQL in one call
from agents.insight_agent import InsightAgent
from security.security_gate import SecurityGate
from utils.file_manager import FileManager
from utils.logger import Logger

# ── Constants ────────────────────────────────────────────────────────────────
MAX_RETRIES = 3          # maximum self-healing attempts per query
MEMORY_SIZE = 3          # number of past Q&A turns kept in rolling buffer


# ── AST-based SQL safety validation ──────────────────────────────────────────
def _validate_sql_ast(sql: str) -> tuple[bool, str]:
    """
    Parse the generated SQL with sqlglot and verify:
      • the statement is a single SELECT
      • no DML / DDL commands are present anywhere in the AST
    Returns (ok: bool, reason: str).
    """
    try:
        import sqlglot
        from sqlglot import exp

        statements = sqlglot.parse(sql)

        if not statements or len(statements) == 0:
            return False, "No valid SQL statement found."

        if len(statements) > 1:
            return False, f"Multiple statements detected ({len(statements)}). Only one SELECT allowed."

        stmt = statements[0]

        # Root must be a Select expression
        if not isinstance(stmt, exp.Select):
            kind = type(stmt).__name__
            return False, f"Statement type '{kind}' is not allowed. Only SELECT is permitted."

        # Walk the AST and reject any DML/DDL node types
        forbidden_types = (
            exp.Insert, exp.Update, exp.Delete, exp.Drop,
            exp.Create, exp.Alter, exp.TruncateTable,
            exp.Command,          # catches EXEC, EXECUTE, etc.
            exp.Grant, exp.Revoke,
        )
        for node in stmt.walk():
            if isinstance(node, forbidden_types):
                return False, f"Forbidden operation '{type(node).__name__}' found inside the query."

        return True, "OK"

    except ImportError:
        # Fallback: if sqlglot is not installed warn and allow through
        # (operator should install it — pip install sqlglot)
        return True, "sqlglot not installed — AST check skipped."

    except Exception as e:
        return False, f"AST parse error: {e}"


# ── Async pipeline helpers ────────────────────────────────────────────────────
async def _run_query_with_healing(
    sql: str,
    params: list,
    db_connector: DatabaseConnector,
    sql_agent: SQLAgent,
    logger: Logger,
) -> dict | None:
    """
    Execute *sql* (with *params*) against the database.
    On failure, ask the LLM to self-heal up to MAX_RETRIES times,
    passing the full error history so the model can avoid repeating mistakes.
    Returns the successful result dict, or None if all attempts fail.
    """
    error_history: list[str] = []
    current_sql = sql
    current_params = params

    for attempt in range(1, MAX_RETRIES + 1):
        result = db_connector.execute_query(current_sql, current_params)

        if result["status"] == "success":
            result["sql"] = current_sql          # record which sql actually ran
            return result

        error_msg = result["error"]
        error_history.append(f"Attempt {attempt}: {error_msg}")
        logger.log_system(
            f"Query failed (attempt {attempt}/{MAX_RETRIES}): {error_msg}"
        )

        if attempt == MAX_RETRIES:
            logger.log_system("Max retries reached — giving up on this query.")
            break

        # Ask the LLM to fix, passing cumulative error history
        fix_result = await sql_agent.fix_query_async(current_sql, error_history)
        if fix_result is None:
            logger.log_system("LLM could not produce a fix — aborting retry.")
            break

        fixed_sql, fixed_params = fix_result

        # AST-validate the fixed query before executing
        ok, reason = _validate_sql_ast(fixed_sql)
        if not ok:
            logger.log_system(f"Fixed query failed AST check: {reason}")
            error_history.append(f"AST rejection of fix: {reason}")
            break

        current_sql = fixed_sql
        current_params = fixed_params

    return None


async def process_query(
    user_input: str,
    settings: Settings,
    db_connector: DatabaseConnector,
    schema_agent: SchemaAgent,
    schema_metadata: dict,
    sql_agent: SQLAgent,
    insight_agent: InsightAgent,
    security_gate: SecurityGate,
    file_manager: FileManager,
    logger: Logger,
    memory: deque,
) -> None:
    """Full async pipeline for a single user query."""

    # ── 1. Security gate (fast, synchronous) ─────────────────────────────────
    security_result = security_gate.check(user_input)
    if security_result["status"] == "DISALLOWED":
        logger.log_security(f"Request blocked: {security_result['reason']}")
        print(f"\n[BLOCKED] {security_result['reason']}")
        return

    # ── 2. RAG-lite schema: inject only relevant tables ───────────────────────
    relevant_schema = schema_agent.filter_schema(schema_metadata, user_input)
    schema_text = schema_agent.format_schema(relevant_schema)

    # ── 3. Single LLM call: intent + SQL (async) ─────────────────────────────
    chat_history = list(memory)          # snapshot of rolling buffer
    llm_result = await sql_agent.generate_async(user_input, schema_text, chat_history)

    if llm_result is None:
        print("\n[ERROR] LLM did not return a usable response.")
        return

    classification = llm_result.get("classification", "INCOMPLETE")
    reason         = llm_result.get("reason", "")
    question       = llm_result.get("question", "")
    sql_queries    = llm_result.get("queries", [])      # list of {sql, params}

    # ── 4. Handle intent outcome ──────────────────────────────────────────────
    if classification == "DISALLOWED":
        logger.log_security(f"Intent disallowed: {reason}")
        print(f"\n[REJECTED] {reason}")
        return

    if classification == "INCOMPLETE":
        print(f"\n[CLARIFICATION NEEDED] {question}")
        return

    if not sql_queries:
        print("\n[ERROR] No SQL queries were generated.")
        return

    # ── 5. Execute queries (with AST validation + self-healing) ───────────────
    results: list[dict] = []

    for item in sql_queries:
        raw_sql = item.get("sql", "")
        params  = item.get("params", [])

        if not raw_sql:
            continue

        # AST validation before first execution
        ok, ast_reason = _validate_sql_ast(raw_sql)
        if not ok:
            logger.log_system(f"Generated query failed AST check: {ast_reason}")
            print(f"\n[SECURITY] Generated query blocked by AST validator: {ast_reason}")
            continue

        result = await _run_query_with_healing(
            raw_sql, params, db_connector, sql_agent, logger
        )

        if result is None:
            print(f"\n[SQL ERROR] Query could not be executed after {MAX_RETRIES} attempts.")
            continue

        row_count = len(result["data"])
        if row_count > settings.MAX_RECORDS:
            print(
                f"\n[LIMIT EXCEEDED] Query returned {row_count} records "
                f"(limit: {settings.MAX_RECORDS}). Please refine your request."
            )
            continue

        results.append({
            "query":   result["sql"],
            "data":    result["data"],
            "columns": result["columns"],
        })

    if not results:
        return

    # ── 6. Generate insights (async) ──────────────────────────────────────────
    insights = await insight_agent.generate_insights_async(user_input, results)
    print(f"\n{insights}")
    file_manager.save_insights(user_input, results, insights)

    # ── 7. Update rolling memory buffer ──────────────────────────────────────
    # Store the first successfully executed query alongside the user question
    memory.append({
        "user":  user_input,
        "sql":   results[0]["query"] if results else "",
    })


# ── Entry-point ───────────────────────────────────────────────────────────────
async def main() -> None:
    settings     = Settings()
    logger       = Logger(settings.LOG_DIR)
    file_manager = FileManager(settings.OUTPUT_DIR)

    logger.log_system("Starting NL-SQL (async refactor)")

    # Database setup (synchronous — happens once at startup)
    db_connector = DatabaseConnector(settings.DB_CONFIG, logger)
    connection   = db_connector.connect()

    schema_extractor = SchemaExtractor(connection, logger)
    schema_metadata  = schema_extractor.extract()

    schema_agent = SchemaAgent(settings, logger)
    if not schema_agent.validate_schema(schema_metadata):
        logger.log_system("Schema validation failed — exiting.")
        return

    # Save full schema to disk (for reference / debugging)
    full_schema_text = schema_agent.format_schema(schema_metadata)
    file_manager.save_schema(full_schema_text)

    # Agents
    security_gate = SecurityGate(settings, logger)
    sql_agent     = SQLAgent(settings, logger)          # unified intent + SQL agent
    insight_agent = InsightAgent(settings, logger)

    # Rolling conversational memory (last MEMORY_SIZE turns)
    memory: deque[dict] = deque(maxlen=MEMORY_SIZE)

    print("NL-SQL Ready  (async mode)")
    print("Enter your query (or 'exit' to quit):\n")

    while True:
        try:
            user_input = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if user_input.lower() in ("exit", "quit"):
            break

        if not user_input:
            continue

        await process_query(
            user_input    = user_input,
            settings      = settings,
            db_connector  = db_connector,
            schema_agent  = schema_agent,
            schema_metadata = schema_metadata,
            sql_agent     = sql_agent,
            insight_agent = insight_agent,
            security_gate = security_gate,
            file_manager  = file_manager,
            logger        = logger,
            memory        = memory,
        )

    db_connector.close()
    logger.log_system("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())