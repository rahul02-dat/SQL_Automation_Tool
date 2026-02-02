import os
import yaml
from pathlib import Path

class Settings:
    def __init__(self):
        self.BASE_DIR = Path(__file__).parent.parent
        self.CONFIG_DIR = self.BASE_DIR / 'config'
        self.PROMPTS_DIR = self.BASE_DIR / 'prompts'
        self.OUTPUT_DIR = self.BASE_DIR / 'output'
        self.LOG_DIR = self.BASE_DIR / 'logs'
        
        self.OUTPUT_DIR.mkdir(exist_ok=True)
        self.LOG_DIR.mkdir(exist_ok=True)
        
        self.OLLAMA_MODEL = 'qwen3:8b'
        self.OLLAMA_BASE_URL = 'http://localhost:11434'
        
        global_policies_path = self.CONFIG_DIR / 'global_policies.yaml'
        with open(global_policies_path, 'r') as f:
            self.global_policies = yaml.safe_load(f)
        
        db_policies_path = self.CONFIG_DIR / 'db_policies.yaml'
        with open(db_policies_path, 'r') as f:
            self.db_policies = yaml.safe_load(f)
        
        self.MAX_RECORDS = self.global_policies['max_records']
        self.SECURITY_POLICIES = self.global_policies['security_policies']
        self.INTENT_POLICIES = self.global_policies['intent_policies']
        self.VALIDATION_RULES = self.global_policies['validation_rules']
        
        self.DB_CONFIG = {
            'type': os.getenv('DB_TYPE', 'sqlite'),
            'path': os.getenv('DB_PATH', str(self.BASE_DIR / 'sample.db')),
            'host': os.getenv('DB_HOST'),
            'port': os.getenv('DB_PORT'),
            'database': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'read_only': True
        }