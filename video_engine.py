import asyncio
import os
import random
import re
import sys
from pathlib import Path
from edge_tts import Communicate
from moviepy import VideoFileClip, ImageClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
from moviepy.video import fx as vfx

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════
# ANTIGRAVITY VIDEO ENGINE (MOVIEPY + EDGE-TTS)
# ═══════════════════════════════════════════════════════════════

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "static/fonts/NotoSansSC-Bold.ttf",
    "static/fonts/NotoSansSC-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "arialbd.ttf",
    "arial.ttf",
]

def resolve_font_path():
    for font_path in FONT_CANDIDATES:
        if os.path.exists(font_path):
            return font_path
    return None

def contains_cjk(text):
    return bool(re.search(r'[\u3400-\u9fff]', text or ""))

def wrap_text_lines(text, draw, font, max_width):
    if not text:
        return [""]

    if contains_cjk(text) and " " not in text:
        lines, current = [], ""
        for char in text:
            candidate = current + char
            if current and draw.textlength(candidate, font=font) > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines

    lines, curr_line = [], []
    for word in text.split():
        candidate = " ".join(curr_line + [word])
        if curr_line and draw.textlength(candidate, font=font) > max_width:
            lines.append(" ".join(curr_line))
            curr_line = [word]
        elif draw.textlength(candidate, font=font) > max_width:
            chunk = ""
            for char in word:
                next_chunk = chunk + char
                if chunk and draw.textlength(next_chunk, font=font) > max_width:
                    lines.append(chunk)
                    chunk = char
                else:
                    chunk = next_chunk
            curr_line = [chunk] if chunk else []
        else:
            curr_line.append(word)
    if curr_line:
        lines.append(" ".join(curr_line))
    return lines or [text]

def chunk_subtitle_text(text, words_per_chunk=3, cjk_chars_per_chunk=8):
    if contains_cjk(text) and " " not in text:
        return [text[i:i + cjk_chars_per_chunk] for i in range(0, len(text), cjk_chars_per_chunk)] or [text]

    words = text.split()
    return [" ".join(words[i:i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)] or [text]

def apply_ken_burns(clip, duration):
    """Applies a slow zoom-in effect (Ken Burns)."""
    return clip

def apply_zoom_in(clip, duration):
    """Dramatic zoom in."""
    return clip.resized(lambda t: 1 + 0.3 * t / duration)

def apply_zoom_out(clip, duration):
    """Dramatic zoom out."""
    return clip.resized(lambda t: 1.3 - 0.3 * t / duration)

def apply_slide_left(clip, duration):
    """Slides the clip from right to left."""
    w, h = clip.size
    return clip.with_position(lambda t: (max(0, w * (1 - 5*t/duration)), "center"))

def apply_glitch(clip, duration):
    """Simulates a glitch effect by random shifting."""
    return clip

class SubtitleHelper:
    @staticmethod
    def insert_emojis(text):
        """Inserts emojis based on common keywords for higher retention."""
        emoji_map = {
            "money": "💰", "cash": "💸", "rich": "🤑", "success": "🏆", "win": "🥇",
            "happy": "😊", "love": "❤️", "sad": "😢", "angry": "😡", "fear": "😨",
            "space": "🚀", "stars": "✨", "future": "🤖", "tech": "💻", "ai": "🧠",
            "ocean": "🌊", "beach": "🏖️", "sun": "☀️", "night": "🌙", "fire": "🔥",
            "water": "💧", "earth": "🌍", "nature": "🌿", "forest": "🌲", "mountain": "🏔️",
            "food": "🍕", "health": "🥗", "fitness": "💪", "gym": "🏋️", "sport": "⚽",
            "book": "📚", "idea": "💡", "learn": "🧠", "school": "🏫", "work": "💼",
            "travel": "✈️", "plane": "🛫", "car": "🚗", "city": "🏙️", "home": "🏠",
            "time": "⏰", "fast": "⚡", "slow": "🐌", "stop": "🛑", "go": "🚦"
        }
        words = text.split()
        for i, word in enumerate(words):
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word in emoji_map:
                words[i] = f"{word} {emoji_map[clean_word]}"
        return " ".join(words)

class VideoEngine:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.output_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)
        self.eleven_key = None

    def set_eleven_key(self, key):
        self.eleven_key = key

    async def generate_voiceover(self, text, idx, voice="en-US-ChristopherNeural", language="en-US"):
        """Generates TTS audio for a single sentence with retries. Supports Edge-TTS and ElevenLabs."""
        if not text or not text.strip():
            return None

        # Language-based voice fallback if voice is not provided or "default"
        if not voice or voice == "default":
            voice_defaults = {
                "en-US": "en-US-ChristopherNeural",
                "en-GB": "en-GB-RyanNeural",
                "es-ES": "es-ES-AlvaroNeural",
                "fr-FR": "fr-FR-HenriNeural",
                "de-DE": "de-DE-ConradNeural",
                "it-IT": "it-IT-DiegoNeural",
                "hi-IN": "hi-IN-MadhurNeural",
                "ur-PK": "ur-PK-AsadNeural",
                "zh-CN": "zh-CN-YunyangNeural",
                "ja-JP": "ja-JP-KeitaNeural"
            }
            voice = voice_defaults.get(language, "en-US-ChristopherNeural")

        if voice.startswith("eleven_"):
            return await self._generate_elevenlabs(text, idx, voice.replace("eleven_", ""))

        max_retries = 3
        for attempt in range(max_retries):
            try:
                communicate = Communicate(text, voice)
                path = self.temp_dir / f"speech_{idx}.mp3"
                await communicate.save(str(path))
                return str(path)
            except Exception as e:
                print(f"⚠️ TTS Attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt) # Exponential backoff
                else:
                    print(f"❌ TTS Error after {max_retries} attempts: {e}")
                    return None

    async def _generate_elevenlabs(self, text, idx, voice_id):
        """Generates TTS using ElevenLabs API."""
        if not self.eleven_key:
            print("⚠️ ElevenLabs API key missing!")
            return None

        import requests
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.eleven_key
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.5}
        }

        try:
            path = self.temp_dir / f"speech_{idx}.mp3"
            response = await asyncio.to_thread(requests.post, url, json=data, headers=headers)
            if response.status_code == 200:
                with open(path, "wb") as f:
                    f.write(response.content)
                return str(path)
            else:
                print(f"❌ ElevenLabs Error: {response.text}")
                return None
        except Exception as e:
            print(f"⚠️ ElevenLabs Exception: {e}")
            return None

    def generate_thumbnail(self, video_path, title):
        """Generates a viral thumbnail from the video."""
        print(f"🖼️ Generating Thumbnail for: {title}")
        try:
            clip = VideoFileClip(video_path)
            # Take a frame at 1/3 of the video
            frame_t = clip.duration / 3
            frame_path = self.output_dir / "thumbnail_raw.jpg"
            clip.save_frame(str(frame_path), t=frame_t)

            # Use PIL to add text
            from PIL import Image, ImageDraw, ImageFont
            img = Image.open(frame_path)
            draw = ImageDraw.Draw(img)
            w, h = img.size

            # Title text
            try:
                font_path = resolve_font_path()
                font = ImageFont.truetype(font_path, 120) if font_path else ImageFont.load_default()
            except:
                font = ImageFont.load_default()

            # Draw shadow/outline
            tw = draw.textlength(title[:30], font=font)
            tx, ty = (w - tw) / 2, h / 2
            for off in range(-5, 6):
                draw.text((tx+off, ty+off), title[:30], font=font, fill="black")
            draw.text((tx, ty), title[:30], font=font, fill="yellow")

            thumb_path = self.output_dir / "thumbnail.jpg"
            img.save(thumb_path)
            clip.close()
            return str(thumb_path)
        except Exception as e:
            print(f"⚠️ Thumbnail generation failed: {e}")
            return None

    def create_video(self, script_data, project_path, media_type="video", bg_music=None, settings=None):
        """Assembles the final video from script chunks and downloaded media."""
        print("🎬 Starting Video Assembly...")

        final_clips = []
        watermark_clip = None

        # Load Watermark if available
        if settings and getattr(settings, 'watermark', False):
            logo_path = getattr(settings, 'logo_path', "static/logo.png") # default
            if os.path.exists(logo_path):
                watermark_clip = ImageClip(logo_path).with_duration(10).resized(width=150).with_opacity(0.5)
        bg_audio = None

        # Load BG Music if needed (Loop it later)
        if bg_music and os.path.exists(bg_music):
            pass # We will add it at the end

        for i, item in enumerate(script_data):
            sentence = item["sentence"]
            keyword = item["keyword"]
            audio_path = str(self.temp_dir / f"speech_{i}.mp3")

            if not os.path.exists(audio_path) or os.path.getsize(audio_path) <= 0:
                print(f"❌ Missing TTS for scene {i + 1}: {audio_path}")
                return None

            # Create Audio Clip
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration + 0.5 # Add padding

            # Use the exact scene assets collected by the pipeline; no cross-scene fallback.
            media_folder = None
            explicit_files = [
                str(Path(f)) for f in item.get("_files", [])
                if Path(f).exists() and Path(f).stat().st_size > 0
            ]

            # 1. Exact try
            if (project_path / keyword).exists():
                media_folder = project_path / keyword
            else:
                safe_keyword = re.sub(r'[^\w\-]', '_', keyword)[:40]
                if safe_keyword and (project_path / safe_keyword).exists():
                    media_folder = project_path / safe_keyword

            if not media_folder:
                if explicit_files:
                    files = explicit_files
                else:
                    print(f"❌ No exact media folder found for scene {i + 1}: {keyword}")
                    return None
            else:
                files = sorted([str(f) for f in media_folder.glob("*") if f.suffix.lower() in ['.mp4', '.jpg', '.jpeg', '.png', '.webp']])

            files = [f for f in files if os.path.getsize(f) > 0]
            if not files:
                print(f"❌ Empty media folder for scene {i + 1}: {keyword}")
                return None

            # Select Visuals (Smart Logic)
            # If duration is long (> 5s), use multiple visuals if available
            visual_clip = None

            image_exts = {'.jpg', '.jpeg', '.png', '.webp'}
            video_exts = {'.mp4', '.mov', '.m4v', '.webm'}
            video_files = [f for f in files if Path(f).suffix.lower() in video_exts]
            image_files = [f for f in files if Path(f).suffix.lower() in image_exts]
            preferred_files = video_files if media_type == "video" and video_files else (image_files or files)
            segment_seconds = 4 if preferred_files == video_files else 3

            def build_visual_clip(file_path, clip_duration):
                suffix = Path(file_path).suffix.lower()
                if suffix in video_exts:
                    clip = VideoFileClip(file_path)
                    if clip.duration < clip_duration:
                        clip = clip.with_effects([vfx.Loop(duration=clip_duration)])
                    else:
                        clip = clip.subclipped(0, clip_duration)
                    return clip.resized(height=1080)

                clip = ImageClip(file_path).with_duration(clip_duration).resized(height=1080)
                return apply_ken_burns(clip, clip_duration)

            if duration > 5 and len(preferred_files) > 1:
                num_segments = int(duration / segment_seconds) + 1
                segment_duration = duration / num_segments
                visual_clip = concatenate_videoclips([
                    build_visual_clip(preferred_files[k % len(preferred_files)], segment_duration)
                    for k in range(num_segments)
                ])
            else:
                visual_clip = build_visual_clip(random.choice(preferred_files), duration)

            # Crop/Resize Logic based on Ratio
            try:
                ratio = settings.ratio if settings else "9:16"
                w, h = 1080, 1920
                if ratio == "16:9": w, h = 1920, 1080
                elif ratio == "1:1": w, h = 1080, 1080

                # Resize keeping aspect ratio then crop
                def crop_center(clip, w, h):
                    cw, ch = clip.size
                    if cw / ch > w / h:
                        # Too wide, crop width
                        new_w = int(ch * w / h)
                        clip = clip.cropped(x1=int((cw - new_w)/2), width=new_w)
                    else:
                        # Too tall/narrow, crop height
                        new_h = int(cw * h / w)
                        clip = clip.cropped(y1=int((ch - new_h)/2), height=new_h)
                    return clip.resized((w, h))

                visual_clip = crop_center(visual_clip, w, h)

            except Exception as e: print(f"Resize Error: {e}")

            # Apply Vibe-based filters (from VideoSettings or vibe field)
            vibe = getattr(settings, 'vibe', 'general')
            if vibe == "futuristic":
                visual_clip = visual_clip.multiply_color([0.7, 1.2, 1.4]) # Cyan/Blue tint
            elif vibe == "black_and_white":
                visual_clip = visual_clip.with_effects([vfx.BlackAndWhite()])

            # Apply Filter
            if settings and settings.filter != "none":
                if settings.filter == "grayscale":
                    visual_clip = visual_clip.with_effects([vfx.BlackAndWhite()])
                elif settings.filter == "sepia":
                    visual_clip = visual_clip.image_transform(lambda im: (im @ [
                        [0.393, 0.769, 0.189],
                        [0.349, 0.686, 0.168],
                        [0.272, 0.534, 0.131]
                    ]).clip(0, 255).astype('uint8'))
                elif settings.filter == "invert":
                    visual_clip = visual_clip.with_effects([vfx.InvertColors()])

            # Keep suspense videos visually stable: no random shake/glitch/zoom.
            trans_type = random.choice(["fade", "none"])
            if trans_type == "fade":
                visual_clip = visual_clip.with_effects([vfx.FadeIn(0.5), vfx.FadeOut(0.5)])

            try:
                visual_clip = crop_center(visual_clip, w, h)
            except Exception as e:
                print(f"Post-transition resize error: {e}")

            visual_clip = visual_clip.with_audio(audio_clip)

            # Add Subtitles
            if settings and settings.subtitles:
                try:
                    from PIL import Image, ImageDraw, ImageFont
                    import numpy as np

                    # Check Duration
                    if duration < 0.5: duration = 2 # fallback

                    style = settings.subtitle_style if settings else "default"

                    def make_text_image(txt, w, h, current_style="default"):
                        img = Image.new('RGBA', (w, h), (0,0,0,0))
                        draw = ImageDraw.Draw(img)

                        font_size = 70 if current_style == "bold_outline" else 100 if current_style == "high_retention" else 60
                        try:
                            font_path = resolve_font_path()
                            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
                        except:
                            font = ImageFont.load_default()

                        # Manual multiline
                        lines = wrap_text_lines(txt, draw, font, w * 0.8)

                        full_text = "\n".join(lines)
                        left, top, right, bottom = draw.textbbox((0, 0), full_text, font=font)
                        tw, th = right - left, bottom - top

                        x = (w - tw) / 2
                        y = (h - th) / 2 if current_style == "high_retention" else h - th - 200 # Center or Bottom

                        if current_style == "yellow_box":
                            padding = 20
                            draw.rectangle([x - padding, y - padding, x + tw + padding, y + th + padding], fill="yellow")
                            draw.text((x, y), full_text, font=font, fill="black", align="center")
                        elif current_style == "bold_outline":
                            stroke_width = 5
                            draw.text((x, y), full_text, font=font, fill="white", stroke_width=stroke_width, stroke_fill="black", align="center")
                        elif current_style == "minimal":
                            draw.text((x, y), full_text, font=font, fill="white", align="center")
                        elif current_style == "high_retention":
                            # Big bold text with shadow and random colors (Yellow, Green, White)
                            shadow_color = "black"
                            for adj in range(-4, 5):
                                for adj2 in range(-4, 5):
                                    draw.text((x+adj, y+adj2), full_text, font=font, fill=shadow_color, align="center")

                            color = random.choice(["#ffdd00", "#00ff00", "#ffffff"]) # Yellow, Green, White
                            draw.text((x, y), full_text, font=font, fill=color, align="center")
                        else: # Default
                            shadow_color = "black"
                            for adj in range(-2, 3):
                                for adj2 in range(-2, 3):
                                    draw.text((x+adj, y+adj2), full_text, font=font, fill=shadow_color, align="center")
                            draw.text((x, y), full_text, font=font, fill="white", align="center")

                        return np.array(img)

                    if style == "high_retention":
                        # Break sentence into 3-word chunks for punchy effect
                        display_text = sentence
                        if getattr(settings, 'emoji_subtitles', False):
                            display_text = SubtitleHelper.insert_emojis(sentence)

                        chunks = chunk_subtitle_text(display_text)
                        chunk_duration = duration / len(chunks)

                        subs_clips = []
                        for idx, chunk in enumerate(chunks):
                            t_img = make_text_image(chunk, visual_clip.w, visual_clip.h, style)
                            t_clip = ImageClip(t_img).with_duration(chunk_duration).with_start(idx * chunk_duration)
                            t_clip = t_clip.with_opacity(0.98)
                            subs_clips.append(t_clip)

                        visual_clip = CompositeVideoClip([visual_clip] + subs_clips)
                    else:
                        display_text = sentence
                        if getattr(settings, 'emoji_subtitles', False):
                            display_text = SubtitleHelper.insert_emojis(sentence)

                        txt_img = make_text_image(display_text, visual_clip.w, visual_clip.h, style)
                        txt_clip = ImageClip(txt_img).with_duration(duration)
                        visual_clip = CompositeVideoClip([visual_clip, txt_clip])

                except Exception as e:
                    print(f"⚠️ Subtitle Error (PIL): {e}")

            final_clips.append(visual_clip)

        if len(final_clips) != len(script_data):
            print(f"❌ Scene assembly incomplete: expected {len(script_data)}, got {len(final_clips)}")
            return None
        if not final_clips: return None

        # Concatenate
        final_video = concatenate_videoclips(final_clips, method="compose")

        # Overlay Watermark
        if watermark_clip:
            watermark_clip = watermark_clip.with_duration(final_video.duration)
            # Position at top right
            watermark_clip = watermark_clip.with_position(("right", "top"))
            final_video = CompositeVideoClip([final_video, watermark_clip])

        # Add BG Music
        if bg_music and os.path.exists(bg_music):
            from moviepy import CompositeAudioClip
            bg = AudioFileClip(bg_music).with_volume_scaled(0.1) # 10% volume
            if bg.duration < final_video.duration:
                from moviepy.audio import fx as afx
                bg = bg.with_effects([afx.AudioLoop(duration=final_video.duration)])
            else:
                bg = bg.subclipped(0, final_video.duration)

            final_audio = CompositeAudioClip([final_video.audio, bg])
            final_video = final_video.with_audio(final_audio)

        # Export
        output_filename = self.output_dir / "final_aesthetic_video.mp4"
        final_video.write_videofile(str(output_filename), fps=24, codec='libx264', audio_codec='aac', threads=4)
        if not output_filename.exists() or output_filename.stat().st_size <= 0:
            print(f"❌ Video export failed or empty: {output_filename}")
            return None
        print(f"✅ Video Saved: {output_filename}")
        return str(output_filename)
