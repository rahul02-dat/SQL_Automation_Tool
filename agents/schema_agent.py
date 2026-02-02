import ollama
from utils.prompt_compiler import PromptCompiler

class SchemaAgent:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)
    
    def validate_schema(self, schema_metadata):
        if not schema_metadata:
            self.logger.log_system("Schema metadata is empty")
            return False
        
        if 'tables' not in schema_metadata or not schema_metadata['tables']:
            self.logger.log_system("No tables found in schema")
            return False
        
        return True
    
    def format_schema(self, schema_metadata):
        schema_lines = []
        schema_lines.append("DATABASE SCHEMA")
        schema_lines.append("=" * 50)
        schema_lines.append("")
        
        for table in schema_metadata['tables']:
            schema_lines.append(f"TABLE: {table['name']}")
            schema_lines.append("-" * 50)
            
            for column in table['columns']:
                col_info = f"  {column['name']} ({column['type']})"
                if column.get('primary_key'):
                    col_info += " [PRIMARY KEY]"
                if column.get('nullable') == False:
                    col_info += " [NOT NULL]"
                schema_lines.append(col_info)
            
            if table.get('foreign_keys'):
                schema_lines.append("")
                schema_lines.append("  Foreign Keys:")
                for fk in table['foreign_keys']:
                    schema_lines.append(f"    {fk['column']} -> {fk['referenced_table']}.{fk['referenced_column']}")
            
            schema_lines.append("")
        
        return "\n".join(schema_lines)