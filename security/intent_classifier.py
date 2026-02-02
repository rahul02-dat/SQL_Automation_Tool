class IntentClassifier:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.disallowed_intents = settings.INTENT_POLICIES.get('disallowed_intents', [])
    
    def classify(self, user_input):
        user_lower = user_input.lower()
        
        modification_keywords = [
            'insert', 'add', 'create', 'update', 'modify', 
            'delete', 'remove', 'drop', 'alter', 'change',
            'truncate', 'rename'
        ]
        
        for keyword in modification_keywords:
            if keyword in user_lower:
                return {
                    'intent': 'modify_data',
                    'allowed': False,
                    'reason': f'Data modification intent detected: {keyword}'
                }
        
        schema_keywords = ['create table', 'drop table', 'alter table', 'create database', 'drop database']
        
        for keyword in schema_keywords:
            if keyword in user_lower:
                return {
                    'intent': 'modify_schema',
                    'allowed': False,
                    'reason': f'Schema modification intent detected: {keyword}'
                }
        
        credential_keywords = ['password', 'credential', 'auth', 'token', 'secret', 'api key']
        
        for keyword in credential_keywords:
            if keyword in user_lower:
                return {
                    'intent': 'access_credentials',
                    'allowed': False,
                    'reason': f'Credential access intent detected: {keyword}'
                }
        
        return {
            'intent': 'query_data',
            'allowed': True,
            'reason': 'Valid query intent'
        }