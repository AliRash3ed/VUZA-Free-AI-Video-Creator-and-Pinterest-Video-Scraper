import asyncio
import os
import random
import re
from pathlib import Path
from edge_tts import Communicate
from moviepy.editor import VideoFileClip, ImageClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
import moviepy.config as mp_config

# ═══════════════════════════════════════════════════════════════
# ANTIGRAVITY VIDEO ENGINE (MOVIEPY + EDGE-TTS)
# ═══════════════════════════════════════════════════════════════

class VideoEngine:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = self.output_dir / "temp"
        self.temp_dir.mkdir(exist_ok=True)

    async def generate_voiceover(self, text, idx, voice="en-US-ChristopherNeural"):
        """Generates TTS audio for a single sentence."""
        try:
            communicate = Communicate(text, voice)
            path = self.temp_dir / f"speech_{idx}.mp3"
            await communicate.save(str(path))
            return str(path)
        except Exception as e:
            print(f"❌ TTS Error: {e}")
            return None

    def create_video(self, script_data, project_path, media_type="video", bg_music=None, settings=None):
        """Assembles the final video from script chunks and downloaded media."""
        print("🎬 Starting Video Assembly...")
        
        final_clips = []
        bg_audio = None
        
        # Load BG Music if needed (Loop it later)
        if bg_music and os.path.exists(bg_music):
            pass # We will add it at the end

        for i, item in enumerate(script_data):
            sentence = item["sentence"]
            keyword = item["keyword"]
            audio_path = str(self.temp_dir / f"speech_{i}.mp3")
            
            if not os.path.exists(audio_path): continue

            # Create Audio Clip
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration + 0.5 # Add padding
            
            # Find Media
            # Find Media (Smart Lookup: if exact folder missing, check partial match)
            # The keyword might have changed due to fallback (e.g. "broken soul aesthetic" -> "broken soul")
            # We search for any folder that contains the core words.
            media_folder = None
            all_folders = [f for f in project_path.iterdir() if f.is_dir()]
            
            # 1. Exact try
            if (project_path / keyword).exists():
                media_folder = project_path / keyword
            
            # 2. Partial try (if keyword is "broken soul aesthetic", try "broken soul")
            if not media_folder:
                 words = keyword.split()
                 for f in all_folders:
                     if words[0] in f.name:
                         media_folder = f; break

            # 3. Random fallback (Use other folders if specific missing)
            if not media_folder and all_folders:
                 media_folder = random.choice(all_folders)
            
            if not media_folder:
                 print(f"⚠️ No media found for: {keyword}")
                 continue

            files = sorted([str(f) for f in media_folder.glob("*") if f.suffix.lower() in ['.mp4', '.jpg', '.jpeg', '.png']])
            if not files: continue

            # Select Visuals (Smart Logic)
            # If duration is long (> 5s), use multiple visuals if available
            visual_clip = None
            
            if media_type == "video":
                # Video Logic
                # If duration > 5s, switch videos every 4s
                if duration > 5:
                    num_vids = int(duration / 4) + 1
                    vid_clips = []
                    segment_duration = duration / num_vids
                    
                    for k in range(num_vids):
                        v_file = files[k % len(files)]
                        clip = VideoFileClip(v_file)
                        # Loop/Trim Logic for sub-clip
                        if clip.duration < segment_duration:
                           clip = clip.loop(duration=segment_duration)
                        else:
                           clip = clip.subclip(0, segment_duration)
                        vid_clips.append(clip.resize(height=1080))
                    
                    visual_clip = concatenate_videoclips(vid_clips)
                    visual_clip = visual_clip.set_audio(audio_clip) # Audio covers whole segment
                else:
                    selected_video = random.choice(files)
                    v_clip = VideoFileClip(selected_video)
                    if v_clip.duration < duration:
                        v_clip = v_clip.loop(duration=duration)
                    else:
                        v_clip = v_clip.subclip(0, duration)
                    visual_clip = v_clip.resize(height=1080)
                    visual_clip = visual_clip.set_audio(audio_clip)

            else:
                # Photo Logic (Ken Burns effect optional, for now simple zoom or static)
                # Photo Logic
                # If duration > 5s, switch photos every 3s
                if duration > 5:
                    num_photos = int(duration / 3) + 1
                    photo_clips = []
                    segment_duration = duration / num_photos
                    for k in range(num_photos):
                        p_file = files[k % len(files)]
                        clip = ImageClip(p_file).set_duration(segment_duration).resize(height=1080)
                        photo_clips.append(clip)
                    visual_clip = concatenate_videoclips(photo_clips)
                    visual_clip = visual_clip.set_audio(audio_clip)
                else:
                    selected_photo = random.choice(files)
                    visual_clip = ImageClip(selected_photo).set_duration(duration)
                    visual_clip = visual_clip.resize(height=1080)
                    visual_clip = visual_clip.set_audio(audio_clip)

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
                        clip = clip.crop(x1=int((cw - new_w)/2), width=new_w)
                    else:
                        # Too tall/narrow, crop height
                        new_h = int(cw * h / w)
                        clip = clip.crop(y1=int((ch - new_h)/2), height=new_h)
                    return clip.resize((w, h))

                visual_clip = crop_center(visual_clip, w, h)
                
            except Exception as e: print(f"Resize Error: {e}")

            # Add Subtitles 
            if settings and settings.subtitles:
                try:
                    from PIL import Image, ImageDraw, ImageFont
                    import numpy as np
                
                    # Check Duration
                    if duration < 0.5: duration = 2 # fallback
                    
                    def make_text_image(txt, w, h):
                        img = Image.new('RGBA', (w, h), (0,0,0,0))
                        draw = ImageDraw.Draw(img)
                        try:
                            font = ImageFont.truetype("arial.ttf", 60)
                        except:
                            font = ImageFont.load_default()
                        
                        # Manual multiline
                        lines = []
                        words = txt.split()
                        curr_line = []
                        for word in words:
                            curr_line.append(word)
                            w_text = draw.textlength(" ".join(curr_line), font=font)
                            if w_text > w * 0.8:
                                curr_line.pop()
                                lines.append(" ".join(curr_line))
                                curr_line = [word]
                        lines.append(" ".join(curr_line))
                        
                        full_text = "\n".join(lines)
                        # Use textbbox instead of textsize (deprecated)
                        left, top, right, bottom = draw.textbbox((0, 0), full_text, font=font)
                        tw, th = right - left, bottom - top
                        
                        x = (w - tw) / 2
                        y = h - th - 150 # Start from bottom
                        
                        # Stroke
                        shadow_color = "black"
                        for adj in range(-2, 3):
                            for adj2 in range(-2, 3):
                                draw.text((x+adj, y+adj2), full_text, font=font, fill=shadow_color, align="center")
                        
                        # Main Text
                        draw.text((x, y), full_text, font=font, fill="white", align="center")
                        return np.array(img)

                    txt_img = make_text_image(sentence, visual_clip.w, visual_clip.h)
                    txt_clip = ImageClip(txt_img).set_duration(duration)
                    visual_clip = CompositeVideoClip([visual_clip, txt_clip])

                except Exception as e:
                    print(f"⚠️ Subtitle Error (PIL): {e}")

            final_clips.append(visual_clip)

        if not final_clips: return None

        # Concatenate
        final_video = concatenate_videoclips(final_clips, method="compose")

        # Add BG Music
        if bg_music and os.path.exists(bg_music):
            bg = AudioFileClip(bg_music).volumex(0.1) # 10% volume
            if bg.duration < final_video.duration:
                bg = bg.loop(duration=final_video.duration)
            else:
                bg = bg.subclip(0, final_video.duration)
            
            final_audio = CompositeAudioClip([final_video.audio, bg])
            final_video = final_video.set_audio(final_audio)

        # Export
        output_filename = self.output_dir / "final_aesthetic_video.mp4"
        final_video.write_videofile(str(output_filename), fps=24, codec='libx264', audio_codec='aac', threads=4)
        print(f"✅ Video Saved: {output_filename}")
        return str(output_filename)
