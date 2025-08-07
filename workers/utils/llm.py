import os
import httpx
import logging
import openai

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "claude-3-sonnet")

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json"
}

openai_client = openai.AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)


async def generate_followup_reply(prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        raise ValueError("OpenRouter API key missing.")
    try:
        response = await openai_client.chat.completions.create(
            model="mistralai/mixtral-8x7b-instruct",
            messages=[
                # {
                #     "role": "system",
                #     "content": "You are a calm, respectful legal assistant who writes short, clear follow-up emails in response to site owners who may be using protected content."
                # },
                {
                    "role": "user",
                    "content": prompt.strip()
                }
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logging.exception(f"[LLM] Failed to generate reply: {e}")
        return "Dear site owner,\n\nThank you for your reply. We are reviewing it and will get back to you soon.\n\nRegards,\nThird Chair Bot"
