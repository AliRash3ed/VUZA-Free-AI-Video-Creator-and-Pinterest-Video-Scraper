import asyncio
from edge_tts import Communicate

async def test_tts():
    try:
        communicate = Communicate("Hello world", "en-US-ChristopherNeural")
        await communicate.save("test_tts.mp3")
        print("TTS Success")
    except Exception as e:
        print(f"TTS Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_tts())
