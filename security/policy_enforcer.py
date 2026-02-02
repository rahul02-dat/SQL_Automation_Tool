class PolicyEnforcer:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.disallowed_operations = settings.SECURITY_POLICIES.get('disallowed_operations', [])
        self.validation_rules = settings.VALIDATION_RULES
    
    def enforce_operation_policy(self, user_input):
        user_upper = user_input.upper()
        
        for operation in self.disallowed_operations:
            if operation in user_upper:
                return {
                    'allowed': False,
                    'reason': f'Disallowed operation detected: {operation}'
                }
        
        return {
            'allowed': True,
            'reason': 'No disallowed operations detected'
        }
    
    def enforce_validation_rules(self, user_input):
        min_length = self.validation_rules.get('min_query_length', 0)
        max_length = self.validation_rules.get('max_query_length', 1000)
        
        if len(user_input) < min_length:
            return {
                'valid': False,
                'reason': f'Query too short (minimum {min_length} characters)'
            }
        
        if len(user_input) > max_length:
            return {
                'valid': False,
                'reason': f'Query too long (maximum {max_length} characters)'
            }
        
        return {
            'valid': True,
            'reason': 'Validation passed'
        }
    
    def enforce_record_limit(self, row_count):
        max_records = self.settings.MAX_RECORDS
        
        if row_count > max_records:
            return {
                'allowed': False,
                'reason': f'Result set exceeds limit ({row_count} > {max_records})',
                'row_count': row_count,
                'limit': max_records
            }
        
        return {
            'allowed': True,
            'reason': 'Within record limit',
            'row_count': row_count,
            'limit': max_records
        }