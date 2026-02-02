class ErrorHandler:
    def __init__(self, logger):
        self.logger = logger
    
    def handle_sql_error(self, error, query):
        error_msg = str(error).lower()
        
        if 'no such table' in error_msg:
            return {
                'type': 'table_not_found',
                'message': 'The specified table does not exist in the database',
                'recoverable': False
            }
        
        if 'no such column' in error_msg:
            return {
                'type': 'column_not_found',
                'message': 'The specified column does not exist',
                'recoverable': True
            }
        
        if 'syntax error' in error_msg:
            return {
                'type': 'syntax_error',
                'message': 'SQL syntax error',
                'recoverable': True
            }
        
        if 'ambiguous column' in error_msg:
            return {
                'type': 'ambiguous_column',
                'message': 'Column name is ambiguous, please specify table name',
                'recoverable': True
            }
        
        return {
            'type': 'unknown',
            'message': str(error),
            'recoverable': False
        }
    
    def handle_connection_error(self, error):
        self.logger.log_system(f"Connection error: {str(error)}")
        
        return {
            'type': 'connection_error',
            'message': 'Failed to connect to database',
            'recoverable': False
        }