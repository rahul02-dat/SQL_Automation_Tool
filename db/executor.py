class QueryExecutor:
    def __init__(self, connection, logger):
        self.connection = connection
        self.logger = logger
    
    def execute(self, query):
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            data = cursor.fetchall()
            
            self.logger.log_system(f"Query executed successfully: {len(data)} rows")
            
            return {
                'status': 'success',
                'data': data,
                'columns': columns,
                'row_count': len(data)
            }
            
        except Exception as e:
            self.logger.log_system(f"Query execution failed: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'data': [],
                'columns': [],
                'row_count': 0
            }