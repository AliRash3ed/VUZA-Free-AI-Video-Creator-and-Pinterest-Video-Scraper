import asyncio
import os
import re
import json
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

from aesthetic_scraper import PinterestScraper, PexelsScraper, PixabayScraper, VideoDownloader, LLMProcessor
from video_engine import VideoEngine

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

class ApiKeys(BaseModel):
    llm_key: str = ""
    llm_url: str = "https://openrouter.ai/api/v1/chat/completions"
    llm_model: str = ""
    pexels_key: str = ""
    pixabay_key: str = ""

class ScrapeRequest(BaseModel):
    query: Optional[str] = None
    script: Optional[str] = None
    source: str = "pinterest"
    media_type: str = "video"
    count: int = 5
    mode: str = "single"
    vibe: str = "aesthetic"
    video_settings: Optional[VideoSettings] = None
    auto_video: bool = True
    api_keys: Optional[ApiKeys] = None

# ── Routes ──
@app.get("/")
async def read_index():
    return FileResponse(static_path / "index.html")

@app.get("/api/status")
async def get_status():
    return scraping_status

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
    simple = keyword.replace(" aesthetic", "").replace(" lofi art", "")
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
    
    # PHASE 2: AI Re-Ask
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
    
    return []

# ── Main Scraping ──
async def run_scrape(request: ScrapeRequest):
    global scraping_status
    scraping_status.update({"is_running": True, "progress": 0, "results": [], "mode": request.mode})
    
    try:
        source, media_type, count = request.source, request.media_type, request.count
        api_keys = request.api_keys or ApiKeys()
        
        if request.mode == "script":
            words = re.findall(r'\w+', request.script)
            project_name = "_".join(words[:5]).lower() or "unnamed"
        else:
            project_name = re.sub(r'[^\w\-]', '_', request.query).lower()
        
        project_path = DOWNLOAD_DIR / project_name / media_type
        project_path.mkdir(parents=True, exist_ok=True)

        if request.mode == "script":
            scraping_status["message"] = f"🧠 AI analyzing script ({request.vibe})..."
            llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
            keyword_data = llm.extract_keywords(request.script, vibe=request.vibe)
            
            if not keyword_data:
                raise Exception("LLM failed. Check your AI API key in settings.")
            
            total = len(keyword_data)
            batch_size = 3
            for bs in range(0, total, batch_size):
                batch = keyword_data[bs:bs + batch_size]
                scraping_status["message"] = f"🔍 Searching {bs+1}-{min(bs+batch_size, total)}/{total}..."
                
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
                
                scraping_status["progress"] = int(((bs + len(batch)) / total) * 80)

            if request.auto_video:
                scraping_status["message"] = "🎙️ Generating Voiceovers..."
                engine = VideoEngine(output_dir=project_path.parent)
                settings = request.video_settings or VideoSettings()
                voice = settings.voice if settings.voice != "none" else None
                
                if voice:
                    await asyncio.gather(*[engine.generate_voiceover(item["sentence"], idx, voice=voice) for idx, item in enumerate(keyword_data)])
                
                scraping_status["progress"] = 90
                scraping_status["message"] = "🎬 Assembling Video..."
                await asyncio.to_thread(engine.create_video, keyword_data, project_path, media_type, bg_music=None, settings=settings)
                scraping_status["message"] = f"✅ Video ready in {project_name}/"
            else:
                scraping_status["message"] = f"✅ Media saved to {project_name}/ (Video OFF)"
        else:
            query = request.query
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
