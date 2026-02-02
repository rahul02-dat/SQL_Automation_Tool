from pathlib import Path
from datetime import datetime

class Logger:
    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.security_log = self.log_dir / 'security.log'
        self.system_log = self.log_dir / 'system.log'
    
    def log_security(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.security_log, 'a') as f:
            f.write(log_entry)
    
    def log_system(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.system_log, 'a') as f:
            f.write(log_entry)