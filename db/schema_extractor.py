class SchemaExtractor:
    def __init__(self, connection, logger):
        self.connection = connection
        self.logger = logger
    
    def extract(self):
        cursor = self.connection.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        table_names = [row[0] for row in cursor.fetchall()]
        
        tables = []
        
        for table_name in table_names:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            
            columns = []
            for col in columns_info:
                columns.append({
                    'name': col[1],
                    'type': col[2],
                    'nullable': not col[3],
                    'default': col[4],
                    'primary_key': bool(col[5])
                })
            
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            fk_info = cursor.fetchall()
            
            foreign_keys = []
            for fk in fk_info:
                foreign_keys.append({
                    'column': fk[3],
                    'referenced_table': fk[2],
                    'referenced_column': fk[4]
                })
            
            tables.append({
                'name': table_name,
                'columns': columns,
                'foreign_keys': foreign_keys
            })
        
        self.logger.log_system(f"Extracted schema for {len(tables)} tables")
        
        return {
            'tables': tables
        }