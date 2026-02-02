import sys
import os
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
    
    logger.log_system("Starting secure NL-SQL agent")
    
    db_connector = DatabaseConnector(settings.DB_CONFIG, logger)
    connection = db_connector.connect()
    
    schema_extractor = SchemaExtractor(connection, logger)
    schema_metadata = schema_extractor.extract()
    
    schema_agent = SchemaAgent(settings, logger)
    schema_validation = schema_agent.validate_schema(schema_metadata)
    
    if not schema_validation:
        logger.log_system("Schema validation failed")
        return
    
    schema_text = schema_agent.format_schema(schema_metadata)
    file_manager.save_schema(schema_text)
    logger.log_system("Schema saved")
    
    security_gate = SecurityGate(settings, logger)
    intent_agent = IntentAgent(settings, logger)
    sql_agent = SQLAgent(settings, logger, schema_text)
    insight_agent = InsightAgent(settings, logger)
    
    print("Secure NL-SQL Agent Ready")
    print("Enter your query (or 'exit' to quit):")
    
    while True:
        user_input = input("\n> ").strip()
        
        if user_input.lower() == 'exit':
            break
        
        if not user_input:
            continue
        
        security_result = security_gate.check(user_input)
        
        if security_result['status'] == 'DISALLOWED':
            logger.log_security(f"Request blocked: {security_result['reason']}")
            print(f"[BLOCKED] {security_result['reason']}")
            continue
        
        intent_result = intent_agent.classify_intent(user_input, schema_text)
        
        if intent_result['classification'] == 'DISALLOWED':
            logger.log_security(f"Intent disallowed: {intent_result['reason']}")
            print(f"[REJECTED] {intent_result['reason']}")
            continue
        
        if intent_result['classification'] == 'INCOMPLETE':
            print(f"[CLARIFICATION NEEDED] {intent_result['question']}")
            continue
        
        sql_queries = sql_agent.generate_sql(user_input, intent_result)
        
        if not sql_queries:
            print("[ERROR] Could not generate SQL queries")
            continue
        
        results = []
        for query in sql_queries:
            result = db_connector.execute_query(query)
            
            if result['status'] == 'error':
                fixed_query = sql_agent.fix_query(query, result['error'])
                if fixed_query:
                    result = db_connector.execute_query(fixed_query)
            
            if result['status'] == 'success':
                row_count = len(result['data'])
                
                if row_count > settings.MAX_RECORDS:
                    print(f"[LIMIT EXCEEDED] Query returned {row_count} records, limit is {settings.MAX_RECORDS}")
                    print("Please refine your request to reduce the result set")
                    break
                
                results.append({
                    'query': query if result.get('original_query') is None else result.get('original_query'),
                    'data': result['data'],
                    'columns': result['columns']
                })
            else:
                print(f"[SQL ERROR] {result['error']}")
                break
        
        if results:
            insights = insight_agent.generate_insights(user_input, results)
            print(f"\n{insights}")
            file_manager.save_insights(user_input, results, insights)
    
    db_connector.close()
    logger.log_system("Agent shutdown")

if __name__ == "__main__":
    main()