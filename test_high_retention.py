import asyncio
import os
from video_engine import VideoEngine
from pathlib import Path

class Settings:
    def __init__(self, ratio="9:16", subtitles=True, subtitle_style="high_retention", filter="none", music="none"):
        self.ratio = ratio
        self.subtitles = subtitles
        self.subtitle_style = subtitle_style
        self.filter = filter
        self.music = music

async def test_high_retention():
    output_dir = "test_hr"
    project_path = Path(output_dir) / "test_video"
    project_path.mkdir(parents=True, exist_ok=True)

    # Create a dummy image
    from PIL import Image
    dummy_img = Image.new('RGB', (1080, 1920), color = (73, 109, 137))
    (project_path / "keyword").mkdir(exist_ok=True)
    dummy_img.save(project_path / "keyword" / "img.jpg")

    engine = VideoEngine(output_dir)

    # Generate a dummy voiceover
    voice_path = await engine.generate_voiceover("This is a test of high retention subtitles. It should show few words at a time.", 0)

    script_data = [
        {"sentence": "This is a test of high retention subtitles. It should show few words at a time.", "keyword": "keyword"}
    ]

    settings = Settings()
    video_file = engine.create_video(script_data, project_path, media_type="photo", settings=settings)
    print(f"Video created: {video_file}")

if __name__ == "__main__":
    asyncio.run(test_high_retention())
