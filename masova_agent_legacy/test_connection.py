import os
from dotenv import load_dotenv
from google import genai

load_dotenv() # Loads the .env file

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
response = client.models.generate_content(
    model="gemini-2.0-flash", 
    contents="Is the MaSoVa system ready for pizza orders?"
)

print(response.text)