"""
db/executor.py
--------------
QueryExecutor — cursor wrapper with secure parameterized query support.

Parameterized execution prevents second-order SQL injection from LLM-generated
queries by keeping user-supplied literal values out of the SQL string itself.
"""


class QueryExecutor:
    """
    Thin wrapper around a SQLite (or compatible) connection cursor.
    Supports both plain queries and parameterized queries.
    """

    def __init__(self, connection, logger):
        self.connection = connection
        self.logger     = logger

    # ── Core execution method ─────────────────────────────────────────────────
    def execute(self, query: str, params: list | tuple | None = None) -> dict:
        """
        Execute *query* against the connection.

        Parameters
        ----------
        query  : SQL string; use ? placeholders for parameterized values.
        params : sequence of values to bind, in placeholder order.
                 Pass None or [] for non-parameterized queries.

        Returns
        -------
        dict with keys:
            status   — "success" | "error"
            data     — list of row tuples (success only)
            columns  — list of column name strings (success only)
            row_count — int (success only)
            error    — error message string (error only)
        """
        if params is None:
            params = []

        # Normalise params: sqlite3 requires a sequence
        if isinstance(params, dict):
            # Named params (:name style) — convert to tuple won't work,
            # pass the dict directly and let sqlite3 handle it.
            bind_params = params
        else:
            bind_params = list(params)

        try:
            cursor = self.connection.cursor()

            if bind_params:
                cursor.execute(query, bind_params)
                self.logger.log_system(
                    f"Parameterized query executed with {len(bind_params)} param(s)."
                )
            else:
                cursor.execute(query)
                self.logger.log_system("Query executed (no parameters).")

            columns  = [desc[0] for desc in cursor.description] if cursor.description else []
            data     = cursor.fetchall()
            row_count = len(data)

            self.logger.log_system(f"Query returned {row_count} row(s).")

            return {
                "status":    "success",
                "data":      data,
                "columns":   columns,
                "row_count": row_count,
            }

        except Exception as exc:
            error_msg = str(exc)
            self.logger.log_system(f"Query execution failed: {error_msg}")
            return {
                "status":    "error",
                "error":     error_msg,
                "data":      [],
                "columns":   [],
                "row_count": 0,
            }