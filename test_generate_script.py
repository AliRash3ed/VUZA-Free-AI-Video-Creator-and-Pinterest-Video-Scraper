import requests
import json

def test_generate_script():
    url = "http://localhost:8000/api/generate_script"
    payload = {
        "topic": "5 facts about Mars",
        "vibe": "educational",
        "api_keys": {
            "llm_key": "dummy_key", # Won't actually work without a real key
            "llm_url": "https://openrouter.ai/api/v1/chat/completions",
            "llm_model": ""
        }
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_generate_script()
