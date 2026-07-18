from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()  # .env'deki OPENAI_API_KEY'i otomatik okur

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Merhaba! Sadece 'Bağlantı başarılı ✅' yaz."}
    ]
)

print(response.choices[0].message.content)