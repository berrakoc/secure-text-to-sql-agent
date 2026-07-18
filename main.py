from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()  # automatically reads OPENAI_API_KEY from .env

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Hello! Please reply with only 'Connection successful ✅'."}
    ]
)

print(response.choices[0].message.content)