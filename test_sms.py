import requests
import os
from dotenv import load_dotenv
from pathlib import Path

# Load env
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / '.env'
load_dotenv(env_path)

api_token = os.getenv('NOTIFY_AFRICA_API_TOKEN')
sender_id = os.getenv('NOTIFY_AFRICA_SENDER_ID')
base_url = os.getenv('NOTIFY_AFRICA_BASE_URL')
phone = "+255712345678" # Test number

print(f"Testing SMS to {phone}")
print(f"URL: {base_url}")
print(f"Token: {api_token}")

payload = {
    "to": phone,
    "message": "Zuristar test SMS",
    "sender_id": sender_id,
    "api_token": api_token
}

try:
    response = requests.post(base_url, json=payload, timeout=15)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Request Error: {e}")

