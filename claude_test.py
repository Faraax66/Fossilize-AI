import anthropic
from dotenv import load_dotenv

load_dotenv()

# Initialize the Anthropic client (reads API key and base URL from .env automatically)
client = anthropic.Anthropic()

# Send a message to Claude
message = client.messages.create(
    model="claude-sonnet-4-6",  # Use "claude-haiku-4-5" for Haiku
    max_tokens=1000,
    messages=[
        {
            "role": "user",
            "content": "Explain how transformers work in AI to a college sophomore. Use an analogy. Keep it under 150 words."
        }
    ],
)

print(message.content[0].text)