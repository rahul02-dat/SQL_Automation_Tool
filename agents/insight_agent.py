import ollama
from utils.prompt_compiler import PromptCompiler

class InsightAgent:
    def __init__(self, settings, logger):
        self.settings = settings
        self.logger = logger
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)
    
    def generate_insights(self, user_input, results):
        prompt = self.prompt_compiler.compile_insight_prompt(user_input, results)
        
        try:
            response = ollama.chat(
                model=self.settings.OLLAMA_MODEL,
                messages=[{'role': 'user', 'content': prompt}]
            )
            
            insights = response['message']['content'].strip()
            
            self.logger.log_system("Insights generated")
            
            return insights
            
        except Exception as e:
            self.logger.log_system(f"Insight generation error: {str(e)}")
            return f"Error generating insights: {str(e)}"