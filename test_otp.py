import requests
import json

url = "http://localhost:8000/api/auth/send-otp/"
data = {
    "email": "greymatter.ga@gmail.com",
    "phone_number": "+255712345678"
}

try:
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {e}")
