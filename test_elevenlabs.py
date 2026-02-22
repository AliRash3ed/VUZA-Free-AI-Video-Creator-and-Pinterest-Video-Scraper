import asyncio
from video_engine import VideoEngine
from pathlib import Path

async def test_elevenlabs():
    output_dir = "test_eleven"
    engine = VideoEngine(output_dir)
    engine.set_eleven_key("dummy_key")

    # This should fail with "ElevenLabs API key missing!" if not set,
    # or with a 401 error from ElevenLabs if dummy_key is used.
    res = await engine.generate_voiceover("Hello world", 0, voice="eleven_pNInz6obpg8ndclQU7Nc")
    print(f"Result: {res}")

if __name__ == "__main__":
    asyncio.run(test_elevenlabs())
