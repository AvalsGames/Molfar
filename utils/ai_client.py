import groq
from config import GROQ_API_KEY, GROQ_MODEL

class AIClient:
    def __init__(self):
        self.groq_client = None
        if GROQ_API_KEY:
            self.groq_client = groq.Groq(api_key=GROQ_API_KEY)

    async def ask(self, prompt: str) -> str:
        try:
            if self.groq_client:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model=GROQ_MODEL,
                )
                return chat_completion.choices[0].message.content
            else:
                return "Groq API key not configured."
        except Exception as e:
            return f"Error connecting to AI: {str(e)}"

ai_client = AIClient()
