import asyncio
import requests
import json
import time

def test_full_flow():
    # Note: This requires a valid LLM API key to fully test AI features.
    # We will just test the server response.

    url = "http://localhost:8000/api/scrape"
    payload = {
        "mode": "script",
        "script": "The future is bright.\nCyberpunk cities are cool.",
        "vibe": "futuristic",
        "source": "pexels",
        "media_type": "video",
        "count": 1,
        "auto_video": True,
        "video_settings": {
            "ratio": "9:16",
            "voice": "en-US-ChristopherNeural",
            "subtitles": True,
            "language": "en-US",
            "subtitle_style": "yellow_box",
            "music": "serenity.mp3",
            "filter": "grayscale"
        },
        "api_keys": {
            "llm_key": "dummy", # Will fail LLM analysis but test the flow
            "llm_url": "https://openrouter.ai/api/v1/chat/completions",
            "llm_model": ""
        }
    }

    try:
        print("🚀 Sending Scrape Request...")
        r = requests.post(url, json=payload)
        print(f"Status: {r.status_code}, Response: {r.json()}")

        if r.status_code == 200:
            print("⏳ Polling status...")
            for _ in range(5):
                res = requests.get("http://localhost:8000/api/status")
                print(f"Status: {res.json()['message']}, Progress: {res.json()['progress']}%")
                if not res.json()['is_running']:
                    break
                time.sleep(2)
    except Exception as e:
        print(f"Test Failed: {e}")

if __name__ == "__main__":
    # Start server in background
    import subprocess
    proc = subprocess.Popen(["python", "app.py"])
    time.sleep(5)
    test_full_flow()
    proc.terminate()
