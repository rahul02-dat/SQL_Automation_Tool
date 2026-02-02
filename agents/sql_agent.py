import ollama
from utils.prompt_compiler import PromptCompiler

class SQLAgent:
    def __init__(self, settings, logger, schema_text):
        self.settings = settings
        self.logger = logger
        self.schema_text = schema_text
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)
    
    def generate_sql(self, user_input, intent_result):
        prompt = self.prompt_compiler.compile_sql_prompt(
            user_input,
            self.schema_text,
            intent_result
        )
        
        try:
            response = ollama.chat(
                model=self.settings.OLLAMA_MODEL,
                messages=[{'role': 'user', 'content': prompt}]
            )
            
            sql_text = response['message']['content'].strip()
            queries = self._extract_queries(sql_text)
            
            self.logger.log_system(f"Generated {len(queries)} SQL queries")
            
            return queries
            
        except Exception as e:
            self.logger.log_system(f"SQL generation error: {str(e)}")
            return []
    
    def fix_query(self, query, error_message):
        prompt = f"""The following SQL query resulted in an error:

QUERY:
{query}

ERROR:
{error_message}

Please fix the query to resolve this error. Return ONLY the corrected SQL query without any explanation.

CORRECTED QUERY:"""

        try:
            response = ollama.chat(
                model=self.settings.OLLAMA_MODEL,
                messages=[{'role': 'user', 'content': prompt}]
            )
            
            fixed_sql = response['message']['content'].strip()
            queries = self._extract_queries(fixed_sql)
            
            if queries:
                self.logger.log_system("Query fixed successfully")
                return queries[0]
            
            return None
            
        except Exception as e:
            self.logger.log_system(f"Query fix error: {str(e)}")
            return None
    
    def _extract_queries(self, text):
        queries = []
        lines = text.split('\n')
        current_query = []
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                continue
            
            if stripped.startswith('```'):
                continue
            
            if stripped.upper().startswith('SELECT'):
                if current_query:
                    query = ' '.join(current_query)
                    if query:
                        queries.append(query)
                    current_query = []
                current_query.append(stripped)
            elif current_query:
                current_query.append(stripped)
                if stripped.endswith(';'):
                    query = ' '.join(current_query)
                    if query:
                        queries.append(query.rstrip(';'))
                    current_query = []
        
        if current_query:
            query = ' '.join(current_query)
            if query:
                queries.append(query.rstrip(';'))
        
        return queries