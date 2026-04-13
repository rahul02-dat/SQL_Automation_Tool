"""
agents/insight_agent.py
-----------------------
InsightAgent — async version using ollama.AsyncClient.
"""

try:
    from ollama import AsyncClient
except ImportError:
    AsyncClient = None

from utils.prompt_compiler import PromptCompiler


class InsightAgent:
    def __init__(self, settings, logger):
        self.settings        = settings
        self.logger          = logger
        self.prompt_compiler = PromptCompiler(settings.PROMPTS_DIR)
        self._client         = AsyncClient(host=settings.OLLAMA_BASE_URL) if AsyncClient else None

    async def generate_insights_async(self, user_input: str, results: list) -> str:
        prompt = self.prompt_compiler.compile_insight_prompt(user_input, results)

        try:
            response = await self._client.chat(
                model    = self.settings.OLLAMA_MODEL,
                messages = [{"role": "user", "content": prompt}],
            )
            insights = response["message"]["content"].strip()
            self.logger.log_system("Insights generated (async).")
            return insights

        except Exception as exc:
            self.logger.log_system(f"Insight generation error: {exc}")
            return f"Error generating insights: {exc}"

    # Synchronous shim kept for backwards compatibility
    def generate_insights(self, user_input: str, results: list) -> str:
        import asyncio
        return asyncio.run(self.generate_insights_async(user_input, results))