import re

class InjectionDetector:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.sql_injection_patterns = settings.SECURITY_POLICIES.get('injection_patterns', [])
        self.prompt_injection_patterns = settings.SECURITY_POLICIES.get('prompt_injection_patterns', [])
    
    def detect_sql_injection(self, user_input):
        user_lower = user_input.lower()
        
        for pattern in self.sql_injection_patterns:
            if pattern.lower() in user_lower:
                return {
                    'detected': True,
                    'pattern': pattern,
                    'type': 'sql_injection'
                }
        
        suspicious_patterns = [
            r"'\s*or\s*'",
            r"'\s*or\s+\d",
            r"\d\s*=\s*\d",
            r";\s*drop\s+",
            r";\s*delete\s+",
            r"union\s+select",
            r"exec\s*\(",
            r"execute\s*\("
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, user_lower, re.IGNORECASE):
                return {
                    'detected': True,
                    'pattern': pattern,
                    'type': 'sql_injection'
                }
        
        return {
            'detected': False,
            'pattern': None,
            'type': None
        }
    
    def detect_prompt_injection(self, user_input):
        user_lower = user_input.lower()
        
        for pattern in self.prompt_injection_patterns:
            if pattern.lower() in user_lower:
                return {
                    'detected': True,
                    'pattern': pattern,
                    'type': 'prompt_injection'
                }
        
        return {
            'detected': False,
            'pattern': None,
            'type': None
        }
    
    def detect(self, user_input):
        sql_result = self.detect_sql_injection(user_input)
        if sql_result['detected']:
            return sql_result
        
        prompt_result = self.detect_prompt_injection(user_input)
        if prompt_result['detected']:
            return prompt_result
        
        return {
            'detected': False,
            'pattern': None,
            'type': None
        }