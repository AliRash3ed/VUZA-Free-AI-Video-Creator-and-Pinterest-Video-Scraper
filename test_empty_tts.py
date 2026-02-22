import asyncio
from edge_tts import Communicate
import os

async def test_empty_tts():
    text = ""
    voice = "en-US-ChristopherNeural"
    try:
        communicate = Communicate(text, voice)
        await communicate.save("test_empty.mp3")
        print("Success")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_empty_tts())
