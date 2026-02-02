from security.injection_detector import InjectionDetector
from security.intent_classifier import IntentClassifier
from security.policy_enforcer import PolicyEnforcer

class SecurityGate:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.injection_detector = InjectionDetector(settings, logger)
        self.intent_classifier = IntentClassifier(settings, logger)
        self.policy_enforcer = PolicyEnforcer(settings, logger)
    
    def check(self, user_input):
        validation_result = self.policy_enforcer.enforce_validation_rules(user_input)
        if not validation_result['valid']:
            return {
                'status': 'DISALLOWED',
                'reason': validation_result['reason'],
                'checkpoint': 'validation'
            }
        
        injection_result = self.injection_detector.detect(user_input)
        if injection_result['detected']:
            return {
                'status': 'DISALLOWED',
                'reason': f"{injection_result['type'].replace('_', ' ').title()} detected: {injection_result['pattern']}",
                'checkpoint': 'injection_detection'
            }
        
        operation_result = self.policy_enforcer.enforce_operation_policy(user_input)
        if not operation_result['allowed']:
            return {
                'status': 'DISALLOWED',
                'reason': operation_result['reason'],
                'checkpoint': 'operation_policy'
            }
        
        intent_result = self.intent_classifier.classify(user_input)
        if not intent_result['allowed']:
            return {
                'status': 'DISALLOWED',
                'reason': intent_result['reason'],
                'checkpoint': 'intent_classification'
            }
        
        return {
            'status': 'ALLOWED',
            'reason': 'All security checks passed',
            'checkpoint': 'complete'
        }