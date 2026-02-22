import requests
import json

def test_analyze():
    url = "http://localhost:8000/api/analyze"
    payload = {
        "script": "The future of AI is here. It will change everything.",
        "api_keys": {
            "llm_key": "dummy",
            "llm_url": "https://openrouter.ai/api/v1/chat/completions",
            "llm_model": ""
        }
    }

    try:
        print("🚀 Sending Analyze Request...")
        r = requests.post(url, json=payload)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            print(f"Response: {r.json()}")
        else:
            print(f"Error: {r.text}")
    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    import subprocess
    import time
    proc = subprocess.Popen(["python", "app.py"])
    time.sleep(5)
    test_analyze()
    proc.terminate()
