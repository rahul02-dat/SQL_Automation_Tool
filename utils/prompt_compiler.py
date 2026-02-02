from pathlib import Path

class PromptCompiler:
    def __init__(self, prompts_dir):
        self.prompts_dir = Path(prompts_dir)
    
    def _load_prompt(self, filename):
        prompt_path = self.prompts_dir / filename
        with open(prompt_path, 'r') as f:
            return f.read()
    
    def compile_intent_prompt(self, user_input, schema_text, policies):
        template = self._load_prompt('intent_prompt.txt')
        
        policies_text = self._format_policies(policies)
        
        return template.format(
            user_input=user_input,
            schema=schema_text,
            policies=policies_text
        )
    
    def compile_sql_prompt(self, user_input, schema_text, intent_result):
        template = self._load_prompt('sql_prompt.txt')
        
        scope = intent_result.get('scope', {})
        tables = ', '.join(scope.get('tables', []))
        columns = ', '.join(scope.get('columns', []))
        filters = scope.get('filters', 'None specified')
        
        return template.format(
            user_input=user_input,
            schema=schema_text,
            tables=tables,
            columns=columns,
            filters=filters
        )
    
    def compile_insight_prompt(self, user_input, results):
        template = self._load_prompt('insight_prompt.txt')
        
        results_text = self._format_results(results)
        
        return template.format(
            user_input=user_input,
            results=results_text
        )
    
    def _format_policies(self, policies):
        lines = []
        
        if 'disallowed_intents' in policies:
            lines.append("Disallowed Intents:")
            for intent in policies['disallowed_intents']:
                lines.append(f"  - {intent}")
        
        if 'require_explicit' in policies:
            lines.append("\nRequire Explicit:")
            for item in policies['require_explicit']:
                lines.append(f"  - {item}")
        
        return '\n'.join(lines)
    
    def _format_results(self, results):
        lines = []
        
        for i, result in enumerate(results, 1):
            lines.append(f"Query {i}: {result['query']}")
            lines.append(f"Columns: {', '.join(result['columns'])}")
            lines.append(f"Row Count: {len(result['data'])}")
            lines.append("")
            
            if result['data']:
                lines.append("Sample Data (first 5 rows):")
                for row in result['data'][:5]:
                    lines.append(f"  {row}")
                lines.append("")
        
        return '\n'.join(lines)