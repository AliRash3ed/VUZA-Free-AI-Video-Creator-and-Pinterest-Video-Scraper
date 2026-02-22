import asyncio
import os
import re
import json
import random
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from pathlib import Path
import uvicorn

# ═══════════════════════════════════════════════════════════════
# VUZA — Video Utility for Zero-cost Automation
# Built by Ali R. | github.com/AliRash3ed
# ═══════════════════════════════════════════════════════════════

from aesthetic_scraper import PinterestScraper, PexelsScraper, PixabayScraper, VideoDownloader, LLMProcessor, WebScraper
from video_engine import VideoEngine
from youtube_utils import YouTubeUploader

app = FastAPI(title="VUZA — Free AI Video Creator")

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

static_path = BASE_DIR / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")

scraping_status = {
    "is_running": False, "progress": 0,
    "message": "Ready", "mode": "single", "results": []
}

# ── Models ──
class VideoSettings(BaseModel):
    ratio: str = "9:16"
    voice: str = "en-US-ChristopherNeural"
    subtitles: bool = True
    language: str = "en-US"
    subtitle_style: str = "default"
    music: str = "none"
    filter: str = "none"
    vibe: str = "general"
    emoji_subtitles: bool = False
    watermark: bool = False
    logo_path: str = "static/logo.png"

class ApiKeys(BaseModel):
    llm_key: str = ""
    llm_url: str = "https://openrouter.ai/api/v1/chat/completions"
    llm_model: str = ""
    pexels_key: str = ""
    pixabay_key: str = ""
    yt_client_id: str = ""
    yt_client_secret: str = ""
    eleven_key: str = ""

class ScrapeRequest(BaseModel):
    query: Optional[str] = None
    script: Optional[str] = None
    scripts: Optional[List[str]] = None
    source: str = "pinterest"
    media_type: str = "video"
    count: int = 5
    mode: str = "single"
    vibe: str = "aesthetic"
    video_settings: Optional[VideoSettings] = None
    auto_video: bool = True
    yt_upload: bool = False
    api_keys: Optional[ApiKeys] = None

# ── Routes ──
@app.get("/")
async def read_index():
    return FileResponse(static_path / "index.html")

@app.get("/api/status")
async def get_status():
    return scraping_status

@app.post("/api/analyze")
async def analyze_script(request: ScrapeRequest):
    if not request.script:
        raise HTTPException(status_code=400, detail="No script provided")

    api_keys = request.api_keys or ApiKeys()
    llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
    analysis = llm.analyze_for_youtube(request.script)

    if not analysis:
        raise HTTPException(status_code=500, detail="Analysis failed. Check your AI API key.")

    return analysis

class GenerateScriptRequest(BaseModel):
    topic: str
    vibe: str = "general"
    api_keys: Optional[ApiKeys] = None

@app.post("/api/generate_script")
async def generate_script(request: GenerateScriptRequest):
    if not request.topic:
        raise HTTPException(status_code=400, detail="No topic provided")

    api_keys = request.api_keys or ApiKeys()
    llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
    script = llm.generate_full_script(request.topic, vibe=request.vibe)

    if not script:
        raise HTTPException(status_code=500, detail="Script generation failed. Check your AI API key.")

    return {"script": script}

class ScrapeUrlRequest(BaseModel):
    url: str
    api_keys: Optional[ApiKeys] = None

@app.post("/api/scrape_url")
async def scrape_url_endpoint(request: ScrapeUrlRequest):
    if not request.url:
        raise HTTPException(status_code=400, detail="No URL provided")

    scraper = WebScraper()
    content = await scraper.scrape_url(request.url)
    if not content:
        raise HTTPException(status_code=500, detail="Failed to scrape URL.")

    api_keys = request.api_keys or ApiKeys()
    llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
    script = llm.summarize_url(content)

    if not script:
        raise HTTPException(status_code=500, detail="Failed to summarize URL content.")

    return {"script": script}

# ── Helpers ──
def make_scraper(src, output_dir, api_keys=None):
    keys = api_keys or ApiKeys()
    if src == "pinterest": return PinterestScraper(output_dir=output_dir)
    if src == "pexels": return PexelsScraper(output_dir=output_dir, api_key=keys.pexels_key)
    if src == "pixabay": return PixabayScraper(output_dir=output_dir, api_key=keys.pixabay_key)
    return None

async def try_search(scraper, keyword, media_type, count):
    try:
        if media_type == "video":
            return await scraper.search_videos(keyword, num_videos=count)
        else:
            return await scraper.search_images(keyword, num_images=count)
    except: return []

async def universal_search(keyword, media_type, count, primary_source, project_path, api_keys=None, vibe="aesthetic", sentence="", llm=None):
    keywords = [keyword]
    simple = keyword.replace(" aesthetic", "").replace(" lofi art", "").replace(" futuristic", "").replace(" black and white", "")
    if simple != keyword: keywords.append(simple)
    words = simple.split()
    if len(words) > 1: keywords.append(words[0])

    all_sources = ["pinterest", "pexels", "pixabay"]
    ordered = [primary_source] + [s for s in all_sources if s != primary_source]

    # PHASE 1: Parallel search
    tasks, labels = [], []
    for src in ordered:
        scraper = make_scraper(src, project_path, api_keys)
        for k in keywords:
            tasks.append(try_search(scraper, k, media_type, count))
            labels.append(f"{src}:{k}")

    results = await asyncio.gather(*tasks)
    for idx, res in enumerate(results):
        if res:
            if idx > 0: print(f"  ✅ [{labels[idx]}] found {len(res)} files")
            return res

    # PHASE 2: AI Re-Ask (Keyword Optimization)
    if llm and sentence and llm.api_key:
        print(f"  🧠 AI Re-Ask for '{keyword}'...")
        try:
            import requests as req
            r = req.post(llm.api_url,
                headers={"Authorization": f"Bearer {llm.api_key}", "Content-Type": "application/json"},
                data=json.dumps({
                    "model": llm.models[0],
                    "messages": [
                        {"role": "system", "content": "These keywords found NO stock footage. Give ONE ultra-simple 1-2 word keyword that will DEFINITELY have results. Reply ONLY the keyword."},
                        {"role": "user", "content": f"Sentence: {sentence}\nFailed: {', '.join(keywords)}\nNew keyword:"}
                    ]
                }), timeout=15)
            if r.status_code == 200:
                new_kw = r.json()["choices"][0]["message"]["content"].strip().strip('"').strip("'").lower()
                print(f"  🆕 AI suggested: '{new_kw}'")
                for src in ["pexels", "pixabay"]:
                    scraper = make_scraper(src, project_path, api_keys)
                    res = await try_search(scraper, new_kw, media_type, count)
                    if res: return res
        except Exception as e: print(f"  ⚠️ AI Re-Ask failed: {e}")

    # PHASE 3: INSANE AI IMAGE GENERATION FALLBACK (Pollinations.ai - 100% Free)
    if llm and sentence:
        print(f"  🎨 No stock found. Generating AI Image for: '{sentence[:50]}...'")
        try:
            description = llm.generate_image_description(sentence)
            prompt = quote(f"{description} {vibe} high quality cinematic 4k")
            url = f"https://image.pollinations.ai/prompt/{prompt}?width=1080&height=1920&nologo=true&seed={random.randint(1,99999)}"

            import requests
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                out_folder = project_path / "ai_generated"
                out_folder.mkdir(parents=True, exist_ok=True)
                file_path = out_folder / f"ai_{random.randint(1000,9999)}.jpg"
                file_path.write_bytes(r.content)
                print(f"  ✨ AI Image generated: {file_path.name}")
                return [str(file_path)]
        except Exception as e:
            print(f"  ❌ AI Image Fallback failed: {e}")

    return []

# ── Main Scraping ──
async def run_scrape(request: ScrapeRequest):
    global scraping_status
    scraping_status.update({"is_running": True, "progress": 0, "results": [], "mode": request.mode})

    try:
        source, media_type, count = request.source, request.media_type, request.count
        api_keys = request.api_keys or ApiKeys()

        if request.mode == "script":
            scripts = request.scripts if request.scripts else ([request.script] if request.script else [])
            for script_idx, script in enumerate(scripts):
                words = re.findall(r'\w+', script)
                project_name = "_".join(words[:5]).lower() or f"unnamed_{script_idx}"

                project_path = DOWNLOAD_DIR / project_name / media_type
                project_path.mkdir(parents=True, exist_ok=True)

                scraping_status["message"] = f"🧠 AI analyzing script {script_idx+1}/{len(scripts)}..."
                llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
                keyword_data = llm.extract_keywords(script, vibe=request.vibe)

                if not keyword_data:
                    continue # Skip failed scripts

                total = len(keyword_data)
                batch_size = 3
                for bs in range(0, total, batch_size):
                    batch = keyword_data[bs:bs + batch_size]
                    scraping_status["message"] = f"🔍 Searching {script_idx+1}/{len(scripts)} | {bs+1}-{min(bs+batch_size, total)}/{total}..."

                    search_tasks = [
                        universal_search(
                            keyword=item["keyword"], media_type=media_type, count=count,
                            primary_source=source, project_path=project_path, api_keys=api_keys,
                            vibe=request.vibe, sentence=item["sentence"], llm=llm
                        ) for item in batch
                    ]
                    batch_results = await asyncio.gather(*search_tasks)

                    for idx, res_files in enumerate(batch_results):
                        item = batch[idx]
                        rel_paths = []
                        for f in (res_files or []):
                            try: rel_paths.append("/" + str(Path(f).relative_to(BASE_DIR)).replace("\\", "/"))
                            except: rel_paths.append(str(f))
                        scraping_status["results"].append({"keyword": item["keyword"], "sentence": item["sentence"], "files": rel_paths})

                    scraping_status["progress"] = int(((script_idx) / len(scripts)) * 100 + ((bs + len(batch)) / total) * (100 / len(scripts)) * 0.8)

                if request.auto_video:
                    scraping_status["message"] = f"🎙️ Generating Voiceovers {script_idx+1}/{len(scripts)}..."
                    engine = VideoEngine(output_dir=project_path.parent)
                    if api_keys.eleven_key:
                        engine.set_eleven_key(api_keys.eleven_key)
                    settings = request.video_settings or VideoSettings()
                    voice = settings.voice if settings.voice != "none" else None

                    if voice:
                        sem = asyncio.Semaphore(3)
                        async def sem_voiceover(text, i):
                            async with sem:
                                return await engine.generate_voiceover(text, i, voice=voice)
                        await asyncio.gather(*[sem_voiceover(item["sentence"], idx) for idx, item in enumerate(keyword_data)])

                    scraping_status["message"] = f"🎬 Assembling Video {script_idx+1}/{len(scripts)}..."
                    bg_music = None
                    if settings.music != "none":
                        bg_music = str(BASE_DIR / "static" / "music" / settings.music)

                    # Ensure vibe is passed in settings
                    settings.vibe = request.vibe

                    video_file = await asyncio.to_thread(engine.create_video, keyword_data, project_path, media_type, bg_music=bg_music, settings=settings)

                    # Generate Thumbnail
                    thumb_file = engine.generate_thumbnail(video_file, project_name.replace("_", " ").title())
                    if thumb_file:
                        try:
                            thumb_rel = "/" + str(Path(thumb_file).relative_to(BASE_DIR)).replace("\\", "/")
                            scraping_status["results"].append({"keyword": "THUMBNAIL", "files": [thumb_rel]})
                        except: pass

                    scraping_status["message"] = f"✅ Video ready in {project_name}/"

                    if request.yt_upload and video_file and api_keys.yt_client_id and api_keys.yt_client_secret:
                        scraping_status["message"] = "📤 Uploading to YouTube..."
                        try:
                            uploader = YouTubeUploader(api_keys.yt_client_id, api_keys.yt_client_secret)
                            # Get metadata from AI if available, otherwise fallback
                            title = project_name.replace("_", " ").title()
                            description = "Automated video created with VUZA."
                            tags = []

                            # Try to get metadata from previous AI analysis if it was run
                            # (Actually we don't have a good way to store it here unless we re-run it or pass it)
                            # For now, we'll use the project name.

                            await asyncio.to_thread(uploader.upload_video, video_file, title, description, tags)
                            scraping_status["message"] += " (Uploaded to YouTube!)"
                        except Exception as e:
                            scraping_status["message"] += f" (Upload Failed: {e})"
                else:
                    scraping_status["message"] = f"✅ Media saved to {project_name}/ (Video OFF)"
        else:
            query = request.query
            project_name = re.sub(r'[^\w\-]', '_', query).lower()
            project_path = DOWNLOAD_DIR / project_name / media_type
            project_path.mkdir(parents=True, exist_ok=True)

            scraping_status["message"] = f"🔍 Searching for '{query}'..."
            res_files = await universal_search(keyword=query, media_type=media_type, count=count, primary_source=source, project_path=project_path, api_keys=api_keys)
            rel_paths = []
            for f in res_files:
                try: rel_paths.append("/" + str(Path(f).relative_to(BASE_DIR)).replace("\\", "/"))
                except: rel_paths.append(str(f))
            scraping_status["results"] = [{"keyword": query, "files": rel_paths}]
            scraping_status["message"] = "✅ Done!"

        scraping_status["progress"] = 100
    except Exception as e:
        scraping_status["message"] = f"❌ Error: {str(e)}"
        import traceback; traceback.print_exc()
    finally:
        scraping_status["is_running"] = False

@app.post("/api/scrape")
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    print(f"📥 VUZA Request: Mode={request.mode}, Source={request.source}, Vibe={request.vibe}")
    if scraping_status["is_running"]:
        return JSONResponse(status_code=400, content={"message": "Already running."})
    background_tasks.add_task(run_scrape, request)
    return {"message": "Started"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
