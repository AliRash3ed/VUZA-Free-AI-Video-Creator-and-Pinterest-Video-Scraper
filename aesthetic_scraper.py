import asyncio
import os
import re
import requests
import json
from pathlib import Path
from urllib.parse import quote, urlparse, unquote
from playwright.async_api import async_playwright
import yt_dlp
from tqdm import tqdm
from PIL import Image

# ═══════════════════════════════════════════════════════════════
# VUZA — Video Utility for Zero-cost Automation
# Built by Ali R. | github.com/AliRash3ed
# ═══════════════════════════════════════════════════════════════

class PinterestScraper:
    def __init__(self, output_dir="downloads/pinterest"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.seen_ids = set()

    def _get_folder(self, query):
        safe_query = re.sub(r'[^\w\-]', '_', query)[:25]
        folder = self.output_dir / safe_query
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    async def get_pin_urls(self, query, media_type="videos", scroll_count=5):
        search_url = f"https://www.pinterest.com/search/{media_type}/?q={quote(query)}"
        print(f"🔍 Searching Pinterest {media_type}: {query}")
        pins = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=self.user_agent)
            try:
                await page.goto(search_url, wait_until="networkidle", timeout=60000)
                for _ in range(scroll_count):
                    await page.evaluate("window.scrollBy(0, 1500)")
                    await asyncio.sleep(1)
                hrefs = await page.evaluate('() => Array.from(document.querySelectorAll(\'a[href*="/pin/"]\')).map(a => a.href)')
                seen = set()
                for href in hrefs:
                    match = re.search(r'/pin/(\d+)/?', href)
                    if match and match.group(1) not in seen:
                        pins.append(f"https://www.pinterest.com/pin/{match.group(1)}/")
                        seen.add(match.group(1))
            except: pass
            finally: await browser.close()
        print(f"📌 Found {len(pins)} pins")
        return pins

    async def search_images(self, query, num_images=5):
        urls = await self.get_pin_urls(query, media_type="pins", scroll_count=3)
        folder = self._get_folder(query)
        results = []
        for i, pin_url in enumerate(urls[:num_images*2]):
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page(user_agent=self.user_agent)
                    await page.goto(pin_url, wait_until="networkidle", timeout=30000)
                    img_url = await page.evaluate('() => { const img = document.querySelector(\'img[srcset]\'); return img ? img.src : null; }')
                    await browser.close()
                    if img_url:
                        path = folder / f"pin_{i}.jpg"
                        if not path.exists():
                            r = requests.get(img_url, timeout=15)
                            if r.status_code == 200: path.write_bytes(r.content); results.append(str(path))
                        else: results.append(str(path))
            except: continue
            if len(results) >= num_images: break
        return results[:num_images]

    async def search_videos(self, query, num_videos=3):
        urls = await self.get_pin_urls(query, media_type="videos", scroll_count=3)
        if not urls: return []
        folder = self._get_folder(query)
        print(f"📌 Found {len(urls)} pins, downloading via yt-dlp...")
        downloader = VideoDownloader(output_dir=folder)
        return await downloader.download_parallel(urls, max_count=num_videos)

    def download_file(self, url, path):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                path.write_bytes(r.content); return True
        except: pass
        return False

# ═══════════════════════════════════════════════════════════════
# PEXELS SCRAPER (PARALLEL)
# ═══════════════════════════════════════════════════════════════

class PexelsScraper:
    def __init__(self, output_dir="downloads/pexels", api_key=None):
        self.output_dir = Path(output_dir)
        self.api_key = api_key or os.environ.get("PEXELS_API_KEY", "")
        self.headers = {"Authorization": self.api_key}
        self.seen_ids = set()

    def _get_folder(self, query):
        folder = self.output_dir / re.sub(r'[^\w\-]', '_', query)[:25]
        folder.mkdir(parents=True, exist_ok=True); return folder

    async def search_images(self, query, num_images=5):
        if not self.api_key: print("⚠️ Pexels API key not set"); return []
        folder = self._get_folder(query)
        try:
            url = f"https://api.pexels.com/v1/search?query={quote(query)}&per_page={num_images}"
            data = requests.get(url, headers=self.headers, timeout=15).json()
            tasks = [asyncio.to_thread(self.download_file, p["src"]["large2x"], folder / f"p_{i}.jpg") for i, p in enumerate(data.get("photos", []))]
            await asyncio.gather(*tasks)
            return [str(f) for f in folder.glob("*.jpg")][:num_images]
        except: return []

    async def search_videos(self, query, num_videos=3):
        if not self.api_key: print("⚠️ Pexels API key not set"); return []
        print(f"🎬 Searching Pexels: {query}")
        folder = self._get_folder(query)
        try:
            url = f"https://api.pexels.com/videos/search?query={quote(query)}&per_page={num_videos*5}"
            data = requests.get(url, headers=self.headers, timeout=15).json()
            valid_vids = []
            for v in data.get("videos", []):
                vid_id = v.get("id")
                if vid_id in self.seen_ids: continue
                if 3 <= v.get("duration", 0) <= 15:
                    best = next((vf for vf in v["video_files"] if vf.get("width") and vf["width"] <= 1920 and vf.get("link")), None)
                    if best:
                        valid_vids.append((best["link"], vid_id))
                        self.seen_ids.add(vid_id)
                if len(valid_vids) >= num_videos: break
            
            tasks = [asyncio.to_thread(self.download_file, link, folder / f"vid_{i}.mp4") for i, (link, _) in enumerate(valid_vids)]
            await asyncio.gather(*tasks)
            return [str(f) for f in folder.glob("*.mp4")]
        except: return []

    def download_file(self, url, path):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200: path.write_bytes(r.content); return True
        except: pass
        return False

# ═══════════════════════════════════════════════════════════════
# PIXABAY SCRAPER (PARALLEL)
# ═══════════════════════════════════════════════════════════════

class PixabayScraper:
    def __init__(self, output_dir="downloads/pixabay", api_key=None):
        self.output_dir = Path(output_dir)
        self.api_key = api_key or os.environ.get("PIXABAY_API_KEY", "")
        self.seen_ids = set()

    def _get_folder(self, query):
        folder = self.output_dir / re.sub(r'[^\w\-]', '_', query)[:25]
        folder.mkdir(parents=True, exist_ok=True); return folder

    async def search_images(self, query, num_images=5):
        if not self.api_key: print("⚠️ Pixabay API key not set"); return []
        folder = self._get_folder(query)
        try:
            url = f"https://pixabay.com/api/?key={self.api_key}&q={quote(query)}&per_page={num_images}"
            data = requests.get(url, timeout=15).json()
            tasks = [asyncio.to_thread(self.download_file, h["largeImageURL"], folder / f"pix_{i}.jpg") for i, h in enumerate(data.get("hits", []))]
            await asyncio.gather(*tasks)
            return [str(f) for f in folder.glob("*.jpg")][:num_images]
        except: return []

    async def search_videos(self, query, num_videos=3):
        if not self.api_key: print("⚠️ Pixabay API key not set"); return []
        folder = self._get_folder(query)
        try:
            url = f"https://pixabay.com/api/videos/?key={self.api_key}&q={quote(query)}&per_page={num_videos*5}"
            data = requests.get(url, timeout=15).json()
            valid = []
            for h in data.get("hits", []):
                vid_id = h.get("id")
                if vid_id in self.seen_ids: continue
                if 3 <= h.get("duration", 0) <= 15:
                    v = h["videos"].get("medium") or h["videos"].get("small")
                    if v: 
                        valid.append(v["url"])
                        self.seen_ids.add(vid_id)
                if len(valid) >= num_videos: break
            tasks = [asyncio.to_thread(self.download_file, u, folder / f"v_{i}.mp4") for i, u in enumerate(valid)]
            await asyncio.gather(*tasks)
            return [str(f) for f in folder.glob("*.mp4")]
        except: return []

    def download_file(self, url, path):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200: path.write_bytes(r.content); return True
        except: pass
        return False

# ═══════════════════════════════════════════════════════════════
# VIDEO DOWNLOADER (yt-dlp PARALLEL)
# ═══════════════════════════════════════════════════════════════

class VideoDownloader:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def download_parallel(self, urls, max_count=3):
        print(f"🚀 Downloading {max_count} videos in parallel...")
        tasks = [self._dl_one(url, i) for i, url in enumerate(urls[:max_count*2])]
        res = await asyncio.gather(*tasks)
        return [r for r in res if r][:max_count]

    async def _dl_one(self, url, idx):
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
            'outtmpl': str(self.output_dir / f'vid_{idx}_%(id)s.%(ext)s'),
            'match_filter': yt_dlp.utils.match_filter_func('duration >= 3 & duration <= 15'),
            'quiet': True, 'ignoreerrors': True
        }
        try:
            return await asyncio.to_thread(self._run_ydl, url, ydl_opts)
        except: return None

    def _run_ydl(self, url, opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info) if info else None

# ═══════════════════════════════════════════════════════════════
# LLM PROCESSOR (Custom AI Brain Support)
# ═══════════════════════════════════════════════════════════════

class LLMProcessor:
    def __init__(self, api_key=None, api_url=None, model=None):
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.api_url = api_url or os.environ.get("LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
        custom_model = model or os.environ.get("LLM_MODEL", "")
        self.models = [custom_model] if custom_model else [
            "stepfun/step-3.5-flash:free",
            "arcee-ai/trinity-large-preview:free",
            "qwen/qwen3-coder:free"
        ]

    def extract_keywords(self, script, vibe="aesthetic"):
        if not self.api_key:
            print("⚠️ LLM API key not set! Please add your AI API key in settings.")
            return []
        
        prompts = {
            "aesthetic": "Break script into sentences. For each, give 1 aesthetic keyword (2-4 words, end with 'aesthetic'). Return: Sentence → keyword",
            "lofi": """Break script into sentences. For each, give 1 keyword (2-4 words before adding 'lofi art', end with 'lofi art'). 
Match lofi-style visuals (rain, solitude, late night, healing, reflection). Return: Sentence → keyword""",
            "general": """Break this script into sentences. For each sentence, give 1 simple and general keyword (1-3 words) that visually represents the meaning of that sentence.
Rules:
- Use the MOST COMMON and EASIEST words possible (e.g. 'sunset', 'walking alone', 'ocean waves', 'city lights', 'happy people', 'rain falling').
- Do NOT add 'aesthetic', 'lofi', 'art', or any style suffix.
- Keywords must be generic enough to easily find stock photos/videos on Pexels or Pixabay.
- Think like a stock video searcher: what simple word would find a matching clip?
- Avoid abstract or poetic words. Use concrete, visual, real-world words.
Return format: Sentence → keyword"""
        }
        prompt = prompts.get(vibe, prompts["aesthetic"])
        for m in self.models:
            print(f"🤖 LLM ({m}) | Vibe: {vibe}")
            try:
                r = requests.post(self.api_url, 
                                  headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "HTTP-Referer": "https://vuza.app"},
                                  data=json.dumps({"model": m, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": script}]}), timeout=30)
                if r.status_code == 200: return self._parse(r.json()["choices"][0]["message"]["content"])
            except: continue
        return []

    def _parse(self, text):
        res = []
        for line in text.split('\n'):
            if '→' in line:
                p = line.split('→'); res.append({"sentence": p[0].strip(), "keyword": p[1].strip()})
        return res
