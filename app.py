import asyncio
import base64
import os
import re
import json
import random
import sys
from urllib.parse import quote
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from pathlib import Path
import uvicorn

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# ═══════════════════════════════════════════════════════════════
# VUZA — Video Utility for Zero-cost Automation
# Built by Ali R. | github.com/AliRash3ed
# ═══════════════════════════════════════════════════════════════

from aesthetic_scraper import PinterestScraper, PexelsScraper, PixabayScraper, VideoDownloader, LLMProcessor, WebScraper
from video_engine import VideoEngine
from youtube_utils import YouTubeUploader

app = FastAPI(title="VUZA — 中文悬疑短视频自动生成工具")

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

static_path = BASE_DIR / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")

scraping_status = {
    "is_running": False, "progress": 0,
    "message": "就绪", "mode": "single", "results": [],
    "status": "idle", "final_video": None, "error": None
}

# ── Models ──
class VideoSettings(BaseModel):
    ratio: str = "9:16"
    voice: str = "zh-CN-YunyangNeural"
    subtitles: bool = True
    language: str = "zh-CN"
    subtitle_style: str = "high_retention"
    music: str = "cinematic.mp3"
    filter: str = "none"
    vibe: str = "suspense_cn"
    emoji_subtitles: bool = False
    watermark: bool = False
    logo_path: str = "static/logo.png"

class ApiKeys(BaseModel):
    llm_key: str = ""
    llm_url: str = "https://openrouter.ai/api/v1/chat/completions"
    llm_model: str = ""
    seedream_key: str = ""
    seedream_url: str = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    seedream_model: str = "doubao-seedream-4-5-251128"
    pexels_key: str = ""
    pixabay_key: str = ""
    yt_client_id: str = ""
    yt_client_secret: str = ""
    eleven_key: str = ""

class ScrapeRequest(BaseModel):
    query: Optional[str] = None
    script: Optional[str] = None
    scripts: Optional[List[str]] = None
    source: str = "ai"
    media_type: str = "photo"
    count: int = 5
    mode: str = "single"
    vibe: str = "suspense_cn"
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
        raise HTTPException(status_code=400, detail="请先输入脚本")

    api_keys = request.api_keys or ApiKeys()
    llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
    analysis = llm.generate_viral_metadata(request.script)

    if not analysis:
        raise HTTPException(status_code=500, detail=llm.last_error or "分析失败，请检查 AI API Key")

    return analysis

class GenerateScriptRequest(BaseModel):
    topic: str
    vibe: str = "general"
    api_keys: Optional[ApiKeys] = None

@app.post("/api/generate_script")
async def generate_script(request: GenerateScriptRequest):
    if not request.topic:
        raise HTTPException(status_code=400, detail="请先输入主题")

    api_keys = request.api_keys or ApiKeys()
    llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
    script = llm.generate_full_script(request.topic, vibe=request.vibe)

    if not script:
        raise HTTPException(status_code=500, detail=llm.last_error or "脚本生成失败，请检查 AI API Key")

    return {"script": script}

class ScrapeUrlRequest(BaseModel):
    url: str
    api_keys: Optional[ApiKeys] = None

@app.post("/api/scrape_url")
async def scrape_url_endpoint(request: ScrapeUrlRequest):
    if not request.url:
        raise HTTPException(status_code=400, detail="请先粘贴链接")

    scraper = WebScraper()
    content = await scraper.scrape_url(request.url)
    if not content:
        raise HTTPException(status_code=500, detail="链接内容提取失败")

    api_keys = request.api_keys or ApiKeys()
    llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
    script = llm.summarize_url(content)

    if not script:
        raise HTTPException(status_code=500, detail="链接内容总结失败")

    return {"script": script}

# ── Helpers ──
def make_scraper(src, output_dir, api_keys=None):
    keys = api_keys or ApiKeys()
    if src == "pinterest": return PinterestScraper(output_dir=output_dir)
    if src == "pexels": return PexelsScraper(output_dir=output_dir, api_key=keys.pexels_key)
    if src == "pixabay": return PixabayScraper(output_dir=output_dir, api_key=keys.pixabay_key)
    return None

def local_script_segments(script):
    """Split a Chinese narration script into stable scene rows without calling an LLM."""
    cleaned = (script or "").replace("\r", "\n").strip()
    rows = []
    for raw_line in cleaned.split("\n"):
        line = re.sub(r'^\s*[\-\*\d\.\)\uff08\uff09、]+\s*', '', raw_line).strip()
        if not line:
            continue
        if len(line) <= 42:
            rows.append(line)
            continue
        parts = re.split(r'(?<=[。！？!?；;])\s*', line)
        rows.extend([p.strip() for p in parts if p.strip()])

    if not rows:
        rows = [p.strip() for p in re.split(r'(?<=[。！？!?；;])\s*', cleaned) if p.strip()]

    return [
        {"sentence": sentence, "keyword": f"scene_{idx + 1:03d}"}
        for idx, sentence in enumerate(rows)
    ]

SEEDREAM_IMAGE_SEMAPHORE = asyncio.Semaphore(3)
POLLINATIONS_IMAGE_SEMAPHORE = asyncio.Semaphore(1)
ALLOW_POLLINATIONS_FALLBACK = os.environ.get("ALLOW_POLLINATIONS_FALLBACK", "").lower() in {"1", "true", "yes"}
_UNSET = object()

def set_status(status=None, message=None, progress=None, error=_UNSET, final_video=_UNSET, **extra):
    if status:
        scraping_status["status"] = status
        scraping_status["is_running"] = status == "running"
    if message is not None:
        scraping_status["message"] = message
    if progress is not None:
        scraping_status["progress"] = progress
    if error is not _UNSET:
        scraping_status["error"] = error
    if final_video is not _UNSET:
        scraping_status["final_video"] = final_video
    if extra:
        scraping_status.update(extra)

def relative_download_path(path):
    return "/" + str(Path(path).relative_to(BASE_DIR)).replace("\\", "/")

def safe_scene_folder(project_path, keyword):
    safe_keyword = re.sub(r'[^\w\-]', '_', keyword)[:40] or "scene"
    return project_path / safe_keyword

def validate_scene_images(keyword_data, project_path):
    missing = []
    for idx, item in enumerate(keyword_data, start=1):
        explicit_files = [
            Path(f) for f in item.get("_files", [])
            if Path(f).exists() and Path(f).stat().st_size > 0
        ]
        folder = safe_scene_folder(project_path, item["keyword"])
        folder_files = [
            f for f in folder.glob("*")
            if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".m4v", ".webm"} and f.stat().st_size > 0
        ] if folder.exists() else []
        files = explicit_files or folder_files
        if not files:
            missing.append(f"第 {idx} 个分镜（{item['keyword']}）")
    if missing:
        raise RuntimeError(f"分镜素材不完整：应有 {len(keyword_data)} 个分镜图/视频，缺少 {len(missing)} 个：{'; '.join(missing[:5])}")

def validate_tts_files(engine, scene_count):
    missing = []
    for idx in range(scene_count):
        path = engine.temp_dir / f"speech_{idx}.mp3"
        if not path.exists() or path.stat().st_size <= 0:
            missing.append(idx + 1)
    if missing:
        raise RuntimeError(f"TTS 文件不完整：应有 {scene_count} 个，缺少/为空 {len(missing)} 个：{missing[:8]}")

def validate_final_video(video_file):
    if not video_file:
        raise RuntimeError("视频合成失败：create_video 没有返回 mp4 路径。")
    video_path = Path(video_file)
    if video_path.suffix.lower() != ".mp4" or not video_path.exists() or video_path.stat().st_size <= 0:
        raise RuntimeError(f"视频合成失败：create_video 返回的 mp4 不存在或为空：{video_file}")
    return video_path

def normalize_seedream_url(url):
    url = (url or "").strip().rstrip("/")
    if not url:
        url = "https://ark.cn-beijing.volces.com/api/v3"
    if url.endswith("/images/generations"):
        return url
    return f"{url}/images/generations"

def file_to_data_url(path):
    path = Path(path)
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/webp" if suffix == ".webp" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

async def generate_seedream_image(prompt_text, file_path, api_keys, reference_image=None):
    if not api_keys or not api_keys.seedream_key:
        raise RuntimeError("AI 生图模式需要 Seedream API Key，当前未配置 seedream_key。")

    import requests
    url = normalize_seedream_url(api_keys.seedream_url)
    model = (api_keys.seedream_model or "doubao-seedream-4-5-251128").strip()
    headers = {
        "Authorization": f"Bearer {api_keys.seedream_key}",
        "Content-Type": "application/json",
    }
    base_payload = {
        "model": model,
        "prompt": prompt_text[:1800],
        "size": "1080x1920",
        "response_format": "url",
        "watermark": False,
        "sequential_image_generation": "disabled",
    }

    base_payloads = [base_payload, {**base_payload, "size": "2K"}]
    payloads = []
    if reference_image and Path(reference_image).exists():
        ref_data = file_to_data_url(reference_image)
        for payload in base_payloads:
            payloads.extend([
                {**payload, "image": [ref_data]},
                {**payload, "image": ref_data},
                payload,
            ])
    else:
        payloads = base_payloads

    def save_response(response):
        data = response.json()
        first = (data.get("data") or [{}])[0]
        image_url = first.get("url")
        b64 = first.get("b64_json")
        if image_url:
            image_response = requests.get(image_url, timeout=180)
            image_response.raise_for_status()
            file_path.write_bytes(image_response.content)
            return str(file_path)
        if b64:
            file_path.write_bytes(base64.b64decode(b64))
            return str(file_path)
        raise RuntimeError(f"Seedream returned no image data: {json.dumps(data, ensure_ascii=False)[:240]}")

    def post_once(payload):
        response = requests.post(url, headers=headers, json=payload, timeout=180)
        if response.status_code != 200:
            try:
                detail = response.json()
            except Exception:
                detail = response.text[:240]
            raise RuntimeError(f"Seedream HTTP {response.status_code}: {detail}")
        return save_response(response)

    for idx, payload in enumerate(payloads, start=1):
        for attempt in range(1, 3):
            try:
                return await asyncio.to_thread(post_once, payload)
            except Exception as e:
                print(f"  ❌ Seedream image failed (payload {idx}/{len(payloads)}, try {attempt}/2): {e}")
                if "429" in str(e):
                    await asyncio.sleep(8 * attempt)
                else:
                    break
    raise RuntimeError("Seedream 生图失败：所有请求 payload 与重试均未返回图片。")

async def generate_ai_image(sentence, project_path, llm=None, vibe="suspense_cn", character_profile="", label="scene", seed=None, api_keys=None, reference_image=None, image_prompt=None):
    """Generate one vertical AI image for a sentence and save it locally."""
    safe_label = re.sub(r'[^\w\-]', '_', label)[:40] or "scene"
    out_folder = project_path / safe_label
    out_folder.mkdir(parents=True, exist_ok=True)

    description = image_prompt or (await asyncio.to_thread(llm.generate_image_description, sentence) if llm else sentence)
    if safe_label == "main_character_reference":
        style = (
            "vertical 9:16 protagonist reference portrait, realistic Chinese web drama character, "
            "clear face, upper body, simple dark background, consistent clothing, no text, no watermark, high detail"
        )
        prompt_text = f"{description}. {style}"
    else:
        style = (
            "vertical 9:16 cinematic suspense frame, realistic Chinese web drama still, "
            "dark moody lighting, coherent composition, no text, no watermark, high detail"
        )
        prompt_text = f"{description}. {style}"

    if character_profile and safe_label != "main_character_reference":
        prompt_text = f"Same protagonist: {character_profile}. Scene: {description}. {style}"

    image_seed = seed if seed is not None else random.randint(1, 999999)

    import requests
    file_path = out_folder / f"ai_{safe_label}_{image_seed}.jpg"

    if api_keys and api_keys.seedream_key:
        async with SEEDREAM_IMAGE_SEMAPHORE:
            return await generate_seedream_image(
                prompt_text,
                file_path,
                api_keys,
                reference_image=reference_image if safe_label != "main_character_reference" else None
            )

    if not ALLOW_POLLINATIONS_FALLBACK:
        raise RuntimeError("AI 生图模式需要 seedream_key；当前默认不 fallback 到 Pollinations。")

    def fetch_image(url):
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "image" not in content_type.lower() and len(response.content) < 5000:
            raise RuntimeError(f"AI image API returned non-image response: {response.text[:160]}")
        file_path.write_bytes(response.content)
        return str(file_path)

    prompts = [prompt_text[:1200]]
    if character_profile and safe_label != "main_character_reference":
        prompts.append(f"{description}. {style}"[:1200])
    prompts.append(f"{sentence}. vertical 9:16 cinematic suspense frame, realistic, no text, no watermark"[:1200])

    async with POLLINATIONS_IMAGE_SEMAPHORE:
        for attempt, prompt_variant in enumerate(prompts, start=1):
            prompt = quote(prompt_variant)
            attempt_seed = image_seed if attempt == 1 else image_seed + attempt
            url = f"https://image.pollinations.ai/prompt/{prompt}?width=720&height=1280&nologo=true&model=flux&seed={attempt_seed}"
            try:
                return await asyncio.to_thread(fetch_image, url)
            except Exception as e:
                print(f"  ❌ AI image generation failed ({safe_label}, try {attempt}/{len(prompts)}): {e}")
                wait_seconds = 12 * attempt if "429" in str(e) else 1.5 * attempt
                await asyncio.sleep(wait_seconds)
        return None

async def try_search(scraper, keyword, media_type, count):
    if not scraper:
        return []
    try:
        if media_type == "video":
            return await scraper.search_videos(keyword, num_videos=count)
        else:
            return await scraper.search_images(keyword, num_images=count)
    except: return []

async def universal_search(keyword, media_type, count, primary_source, project_path, api_keys=None, vibe="aesthetic", sentence="", llm=None, character_profile="", character_seed=None, character_reference=None, image_prompt=None):
    if primary_source == "ai":
        print(f"  🎨 AI image source for: '{sentence[:40]}...'")
        image_path = await generate_ai_image(
            sentence or keyword, project_path, llm=llm, vibe=vibe,
            character_profile=character_profile, label=keyword, seed=character_seed,
            api_keys=api_keys, reference_image=character_reference, image_prompt=image_prompt
        )
        return [image_path] if image_path else []

    keywords = [keyword]
    simple = keyword.replace(" aesthetic", "").replace(" lofi art", "").replace(" futuristic", "").replace(" black and white", "")
    if simple != keyword: keywords.append(simple)
    words = simple.split()
    if len(words) > 1: keywords.append(words[0])

    all_sources = ["pexels", "pixabay", "pinterest"]
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

    # Optional legacy fallback. Disabled by default; enable explicitly with ALLOW_POLLINATIONS_FALLBACK=1.
    if ALLOW_POLLINATIONS_FALLBACK and llm and sentence:
        print(f"  🎨 No stock found. Generating AI Image for: '{sentence[:50]}...'")
        try:
            image_path = await generate_ai_image(
                sentence, project_path, llm=llm, vibe=vibe,
                character_profile=character_profile, label=keyword, seed=character_seed,
                api_keys=api_keys, reference_image=character_reference, image_prompt=image_prompt
            )
            if image_path:
                print(f"  ✨ AI Image generated: {Path(image_path).name}")
                return [image_path]
        except Exception as e:
            print(f"  ❌ AI Image Fallback failed: {e}")

    return []

# ── Main Scraping ──
async def run_scrape(request: ScrapeRequest):
    global scraping_status
    set_status(
        "running",
        message="开始处理...",
        progress=0,
        error=None,
        final_video=None,
        results=[],
        mode=request.mode
    )

    try:
        source, media_type, count = request.source, request.media_type, request.count
        api_keys = request.api_keys or ApiKeys()

        if source == "ai" and (not api_keys.llm_key or not api_keys.seedream_key):
            missing = []
            if not api_keys.llm_key:
                missing.append("llm_key")
            if not api_keys.seedream_key:
                missing.append("seedream_key")
            raise RuntimeError(f"AI 生图模式需要同时配置 DeepSeek/兼容 LLM API Key 与 Seedream API Key，缺少：{', '.join(missing)}。当前默认不 fallback 到 Pollinations。")

        if request.mode == "single" and source == "ai" and request.auto_video:
            topic = (request.query or "").strip()
            if not topic:
                raise RuntimeError("主题到视频需要先输入主题 query。")
            set_status(message="🧠 DeepSeek 正在根据主题生成完整脚本...", progress=3, mode="script")
            llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
            generated_script = await asyncio.to_thread(llm.generate_full_script, topic, request.vibe)
            if not generated_script:
                raise RuntimeError(llm.last_error or "DeepSeek 没有生成可用脚本。")
            request.mode = "script"
            request.script = generated_script
            request.scripts = [generated_script]

        if request.mode == "script":
            scripts = request.scripts if request.scripts else ([request.script] if request.script else [])
            if not scripts:
                raise RuntimeError("脚本模式需要提供 script 或 scripts。")
            for script_idx, script in enumerate(scripts):
                words = re.findall(r'\w+', script)
                project_name = "_".join(words[:5]).lower() or f"unnamed_{script_idx}"

                project_path = DOWNLOAD_DIR / project_name / media_type
                project_path.mkdir(parents=True, exist_ok=True)

                llm = None
                if source == "ai":
                    scraping_status["message"] = f"🧩 正在本地拆分分镜 {script_idx+1}/{len(scripts)}..."
                    keyword_data = local_script_segments(script)
                    llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
                else:
                    scraping_status["message"] = f"🧠 AI 正在分析脚本 {script_idx+1}/{len(scripts)}..."
                    llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
                    keyword_data = llm.extract_keywords(script, vibe=request.vibe)

                if not keyword_data:
                    raise RuntimeError((llm.last_error if llm else "") or "没有生成可用的分镜，请检查脚本是否为空。")

                character_profile = ""
                character_seed = None
                character_reference_path = None
                if source == "ai":
                    image_provider = "Seedream 4.5"

                    scraping_status["message"] = f"🧠 DeepSeek 正在生成主角设定 {script_idx+1}/{len(scripts)}..."
                    character_profile = llm.generate_character_profile(script)
                    if not character_profile:
                        raise RuntimeError(llm.last_error or "DeepSeek 没有生成可用主角设定。")

                    scraping_status["message"] = f"🧠 DeepSeek 正在生成画面提示词 {script_idx+1}/{len(scripts)}..."
                    prompted_data = await asyncio.to_thread(llm.generate_scene_prompts, keyword_data, character_profile, request.vibe)
                    if not prompted_data:
                        raise RuntimeError(llm.last_error or "DeepSeek 没有生成可用的画面提示词，未开始生图。")
                    keyword_data = prompted_data

                    scraping_status["message"] = f"🎨 {image_provider} 正在生成主角参考图 {script_idx+1}/{len(scripts)}..."
                    character_seed = random.randint(1, 999999)
                    ref_path = await generate_ai_image(
                        f"Character reference portrait for the protagonist. {character_profile}",
                        project_path,
                        llm=None,
                        vibe=request.vibe,
                        character_profile=character_profile,
                        label="main_character_reference",
                        seed=character_seed,
                        api_keys=api_keys
                    )
                    if ref_path:
                        character_reference_path = ref_path
                        try:
                            ref_rel = "/" + str(Path(ref_path).relative_to(BASE_DIR)).replace("\\", "/")
                            scraping_status["results"].append({
                                "keyword": "主角人物参考",
                                "sentence": character_profile,
                                "files": [ref_rel]
                            })
                        except Exception:
                            pass

                total = len(keyword_data)
                batch_size = 3 if source == "ai" and api_keys.seedream_key else (1 if source == "ai" else 3)
                for bs in range(0, total, batch_size):
                    batch = keyword_data[bs:bs + batch_size]
                    action = "Seedream 4.5 正在并行生成分镜图" if source == "ai" else "正在搜索素材"
                    scraping_status["message"] = f"🔍 {action} {script_idx+1}/{len(scripts)} | {bs+1}-{min(bs+batch_size, total)}/{total}..."

                    search_tasks = [
                        universal_search(
                            keyword=item["keyword"], media_type=media_type, count=count,
                            primary_source=source, project_path=project_path, api_keys=api_keys,
                            vibe=request.vibe, sentence=item["sentence"], llm=llm,
                            character_profile=character_profile, character_seed=character_seed,
                            character_reference=character_reference_path,
                            image_prompt=item.get("image_prompt")
                        ) for item in batch
                    ]
                    batch_results = await asyncio.gather(*search_tasks)

                    for idx, res_files in enumerate(batch_results):
                        item = batch[idx]
                        rel_paths = []
                        valid_files = []
                        for f in (res_files or []):
                            if not f or not Path(f).exists() or Path(f).stat().st_size <= 0:
                                continue
                            valid_files.append(str(f))
                            try: rel_paths.append("/" + str(Path(f).relative_to(BASE_DIR)).replace("\\", "/"))
                            except: rel_paths.append(str(f))
                        if rel_paths:
                            item["_files"] = valid_files
                            scraping_status["results"].append({"keyword": item["keyword"], "sentence": item["sentence"], "files": rel_paths})

                    scraping_status["progress"] = int(((script_idx) / len(scripts)) * 100 + ((bs + len(batch)) / total) * (100 / len(scripts)) * 0.8)

                if request.auto_video:
                    validate_scene_images(keyword_data, project_path)

                    scraping_status["message"] = f"🎙️ 正在生成中文旁白 {script_idx+1}/{len(scripts)}..."
                    engine = VideoEngine(output_dir=project_path.parent)
                    if api_keys.eleven_key:
                        engine.set_eleven_key(api_keys.eleven_key)
                    settings = request.video_settings or VideoSettings()
                    voice = settings.voice if settings.voice != "none" else None
                    if not voice:
                        raise RuntimeError("自动合成视频需要 TTS voice；当前 voice=none，无法生成与分镜数量一致的旁白文件。")

                    if voice:
                        sem = asyncio.Semaphore(3)
                        async def sem_voiceover(text, i):
                            async with sem:
                                return await engine.generate_voiceover(text, i, voice=voice, language=settings.language)
                        await asyncio.gather(*[sem_voiceover(item["sentence"], idx) for idx, item in enumerate(keyword_data)])
                    validate_tts_files(engine, len(keyword_data))

                    scraping_status["message"] = f"🎬 正在合成视频 {script_idx+1}/{len(scripts)}..."
                    bg_music = None
                    if settings.music != "none":
                        bg_music = str(BASE_DIR / "static" / "music" / settings.music)

                    # Ensure vibe is passed in settings
                    settings.vibe = request.vibe

                    video_file = await asyncio.to_thread(engine.create_video, keyword_data, project_path, media_type, bg_music=bg_music, settings=settings)
                    video_path = validate_final_video(video_file)

                    # Generate Thumbnail
                    thumb_file = engine.generate_thumbnail(video_file, project_name.replace("_", " ").title())
                    try:
                        video_rel = relative_download_path(video_path)
                        scraping_status["results"].append({"keyword": "合成视频", "files": [video_rel]})
                        set_status(final_video=video_rel)
                    except Exception:
                        pass
                    if thumb_file:
                        try:
                            thumb_rel = "/" + str(Path(thumb_file).relative_to(BASE_DIR)).replace("\\", "/")
                            scraping_status["results"].append({"keyword": "封面图", "files": [thumb_rel]})
                        except: pass

                    scraping_status["message"] = f"✅ 视频已生成：{project_name}/final_aesthetic_video.mp4"

                    if request.yt_upload and video_file and api_keys.yt_client_id and api_keys.yt_client_secret:
                        scraping_status["message"] = "📤 正在上传到 YouTube..."
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
                            scraping_status["message"] += "（已上传到 YouTube）"
                        except Exception as e:
                            scraping_status["message"] += f"（上传失败：{e}）"
                else:
                    scraping_status["message"] = f"✅ 素材已保存到 {project_name}/（视频合成已关闭）"
        else:
            query = request.query
            project_name = re.sub(r'[^\w\-]', '_', query).lower()
            project_path = DOWNLOAD_DIR / project_name / media_type
            project_path.mkdir(parents=True, exist_ok=True)

            scraping_status["message"] = f"🔍 正在处理“{query}”..."
            llm = None
            character_profile = ""
            character_seed = None
            character_reference_path = None
            image_prompt = None
            if source == "ai":
                api_keys = request.api_keys or ApiKeys()
                llm = LLMProcessor(api_key=api_keys.llm_key, api_url=api_keys.llm_url, model=api_keys.llm_model)
                character_profile = llm.generate_character_profile(query)
                if not character_profile:
                    raise RuntimeError(llm.last_error or "DeepSeek 没有生成可用主角设定。")
                image_prompt = llm.generate_image_description(query)
                if not image_prompt:
                    raise RuntimeError(llm.last_error or "DeepSeek 没有生成可用的画面提示词。")
                character_seed = random.randint(1, 999999)
            res_files = await universal_search(keyword=query, media_type=media_type, count=count, primary_source=source, project_path=project_path, api_keys=api_keys, llm=llm, sentence=query, character_profile=character_profile, character_seed=character_seed, character_reference=character_reference_path, image_prompt=image_prompt)
            rel_paths = []
            for f in res_files:
                try: rel_paths.append("/" + str(Path(f).relative_to(BASE_DIR)).replace("\\", "/"))
                except: rel_paths.append(str(f))
            scraping_status["results"] = [{"keyword": query, "files": rel_paths}]
            scraping_status["message"] = "✅ 已完成"

        set_status("success", progress=100)
    except Exception as e:
        set_status("error", message=f"❌ 出错：{str(e)}", progress=100, error=str(e))
        import traceback; traceback.print_exc()
    finally:
        scraping_status["is_running"] = False

@app.post("/api/scrape")
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    print(f"📥 VUZA Request: Mode={request.mode}, Source={request.source}, Vibe={request.vibe}")
    if scraping_status["is_running"]:
        return JSONResponse(status_code=400, content={"message": "正在处理上一个任务，请稍等"})
    background_tasks.add_task(run_scrape, request)
    return {"message": "已开始"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
