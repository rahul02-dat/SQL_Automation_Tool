from pathlib import Path
from datetime import datetime

class FileManager:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def save_schema(self, schema_text):
        schema_path = self.output_dir / 'schema.txt'
        
        with open(schema_path, 'w') as f:
            f.write(schema_text)
        
        return schema_path
    
    def save_insights(self, user_input, results, insights):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        insights_path = self.output_dir / f'insights_{timestamp}.txt'
        
        with open(insights_path, 'w') as f:
            f.write("="*70 + "\n")
            f.write("QUERY INSIGHTS\n")
            f.write("="*70 + "\n\n")
            
            f.write(f"User Request: {user_input}\n")
            f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("-"*70 + "\n")
            f.write("SQL QUERIES EXECUTED\n")
            f.write("-"*70 + "\n\n")
            
            for i, result in enumerate(results, 1):
                f.write(f"Query {i}:\n")
                f.write(f"{result['query']}\n\n")
                f.write(f"Columns: {', '.join(result['columns'])}\n")
                f.write(f"Rows returned: {len(result['data'])}\n\n")
            
            f.write("-"*70 + "\n")
            f.write("INSIGHTS\n")
            f.write("-"*70 + "\n\n")
            
            f.write(insights)
            f.write("\n\n")
            
            f.write("="*70 + "\n")
        
        return insights_path