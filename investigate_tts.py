import asyncio
from edge_tts import Communicate
import os

async def generate_many_tts():
    text = "This is a test sentence for the VUZA video creator tool. We are testing for potential TTS errors."
    voice = "en-US-ChristopherNeural"
    tasks = []
    for i in range(20):
        communicate = Communicate(text, voice)
        tasks.append(communicate.save(f"test_{i}.mp3"))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            print(f"Task {i} failed: {res}")
        else:
            print(f"Task {i} success")
            os.remove(f"test_{i}.mp3")

if __name__ == "__main__":
    asyncio.run(generate_many_tts())
