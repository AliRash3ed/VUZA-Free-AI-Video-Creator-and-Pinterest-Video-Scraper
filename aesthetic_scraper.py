import asyncio
import os
import re
import requests
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse, unquote
from playwright.async_api import async_playwright
import yt_dlp
from tqdm import tqdm
from PIL import Image

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

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
    OPENROUTER_MODEL_ALIASES = {
        "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
        "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
        "deepseek-v3.2": "deepseek/deepseek-v3.2",
        "deepseek-v3.2-exp": "deepseek/deepseek-v3.2-exp",
        "deepseek-chat-v3.1": "deepseek/deepseek-chat-v3.1",
        "deepseek-r1": "deepseek/deepseek-r1",
        "deepseek-chat": "deepseek/deepseek-chat",
    }
    DEEPSEEK_MODEL_ALIASES = {
        "deepseek/deepseek-v4-pro": "deepseek-v4-pro",
        "deepseek/deepseek-v4-flash": "deepseek-v4-flash",
        "deepseek/deepseek-chat": "deepseek-chat",
        "deepseek/deepseek-reasoner": "deepseek-reasoner",
    }

    def __init__(self, api_key=None, api_url=None, model=None):
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.api_url = self._normalize_api_url(api_url or os.environ.get("LLM_API_URL", ""))
        self.last_error = ""
        custom_model = self._normalize_model(model or os.environ.get("LLM_MODEL", ""))
        if custom_model:
            self.models = [custom_model]
        elif self._is_deepseek_api():
            self.models = ["deepseek-v4-pro", "deepseek-chat"]
        else:
            self.models = [
                "qwen/qwen3-coder:free",
                "openai/gpt-oss-20b:free",
                "z-ai/glm-4.5-air:free",
                "meta-llama/llama-3.3-70b-instruct:free"
            ]

    def _normalize_api_url(self, api_url):
        url = (api_url or "").strip().rstrip("/")
        default = "https://openrouter.ai/api/v1/chat/completions"
        if not url:
            return default

        if "openrouter.ai" in url and not url.endswith("/chat/completions"):
            return default

        if "api.deepseek.com" in url and not url.endswith("/chat/completions"):
            return f"{url}/chat/completions"

        if url.endswith("/v1"):
            return f"{url}/chat/completions"

        return url

    def _is_deepseek_api(self):
        return "api.deepseek.com" in self.api_url

    def _is_openrouter_api(self):
        return "openrouter.ai" in self.api_url

    def _normalize_model(self, model):
        model = (model or "").strip()
        if not model:
            return ""

        if self._is_deepseek_api():
            if model in self.DEEPSEEK_MODEL_ALIASES:
                return self.DEEPSEEK_MODEL_ALIASES[model]
            if model.startswith("deepseek/"):
                return model.split("/", 1)[1]
            return model

        if self._is_openrouter_api() and model in self.OPENROUTER_MODEL_ALIASES:
            return self.OPENROUTER_MODEL_ALIASES[model]
        if self._is_openrouter_api() and "/" not in model and model.startswith("deepseek-"):
            return f"deepseek/{model}"
        return model

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://vuza.local",
            "X-Title": "VUZA Chinese Suspense Video Generator"
        }

    def _format_api_error(self, response):
        try:
            data = response.json()
            if isinstance(data, dict):
                err = data.get("error") or data.get("detail") or data
                if isinstance(err, dict):
                    return err.get("message") or json.dumps(err, ensure_ascii=False)[:300]
                return str(err)[:300]
        except Exception:
            pass
        return response.text[:300] if response.text else response.reason

    def _request_timeout(self, timeout):
        read_timeout = timeout or 40
        if self._is_deepseek_api():
            read_timeout = max(read_timeout, 180)
        return (20, read_timeout)

    def _chat(self, model, messages, timeout=40, max_tokens=None):
        payload = {"model": model, "messages": messages}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        attempts = 3 if self._is_deepseek_api() else 2
        response = None
        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self._headers(),
                    json=payload,
                    timeout=self._request_timeout(timeout)
                )
            except requests.Timeout as exc:
                self.last_error = (
                    f"AI 接口响应超时（第 {attempt}/{attempts} 次）：{exc}。"
                    "如果一直超时，可以换 deepseek-chat、稍后重试，或改用 OpenRouter。"
                )
                print(f"❌ {self.last_error}")
                if attempt < attempts:
                    time.sleep(4 * attempt)
                    continue
                return None
            except requests.ConnectionError as exc:
                self.last_error = (
                    f"无法连接 AI 接口（第 {attempt}/{attempts} 次）：{exc}。"
                    "请检查网络、代理，或稍后重试。"
                )
                print(f"❌ {self.last_error}")
                if attempt < attempts:
                    time.sleep(4 * attempt)
                    continue
                return None
            except requests.RequestException as exc:
                self.last_error = f"无法连接 AI 接口：{exc}"
                print(f"❌ LLM request failed: {exc}")
                return None

            if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts:
                self.last_error = f"AI 接口繁忙（HTTP {response.status_code}），正在重试 {attempt}/{attempts}..."
                print(f"⚠️ {self.last_error}")
                time.sleep(4 * attempt)
                continue
            break

        if response.status_code != 200:
            if response.status_code == 404:
                if self._is_deepseek_api():
                    self.last_error = (
                        f"DeepSeek 官方接口地址或模型不存在（HTTP 404）。当前接口地址：{self.api_url}；"
                        f"当前模型：{model}。DeepSeek 官方地址可填 https://api.deepseek.com，"
                        "模型名示例：deepseek-v4-pro。"
                    )
                else:
                    self.last_error = (
                        f"AI 接口地址或模型不存在（HTTP 404）。当前接口地址：{self.api_url}；"
                        f"当前模型：{model}。OpenRouter 地址应为 https://openrouter.ai/api/v1/chat/completions，"
                        "模型名示例：deepseek/deepseek-v4-pro。"
                    )
            else:
                self.last_error = f"模型 {model} 调用失败（HTTP {response.status_code}）：{self._format_api_error(response)}"
            print(f"❌ {self.last_error}")
            return None

        try:
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            self.last_error = f"AI 返回格式异常：{exc}"
            print(f"❌ {self.last_error}")
            return None

    def extract_keywords(self, script, vibe="aesthetic"):
        if not self.api_key:
            self.last_error = "未收到 AI API 密钥，请先在 API 设置里填写。"
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
Return format: Sentence → keyword""",
            "suspense_cn": """把中文悬疑短视频旁白拆成适合配画面的短句。
对每一句生成 1 个英文素材搜索关键词，必须是 Pexels/Pixabay 容易搜到的具体画面。
规则:
- 左边保留原中文旁白句子。
- 右边只写英文关键词，1-4 个词，不要中文，不要抽象词。
- 关键词要偏悬疑、夜晚、空房间、走廊、手机、门、窗、影子、雨、监控、脚步、老照片等可视化元素。
- 不要输出解释、编号、场景描述或角色名。
返回格式严格为: 中文句子 → english keyword""",
            "futuristic": "Break script into sentences. For each, give 1 futuristic/cyberpunk keyword (2-4 words, end with 'futuristic'). Return: Sentence → keyword",
            "black_and_white": "Break script into sentences. For each, give 1 noir/vintage keyword (2-4 words, end with 'black and white'). Return: Sentence → keyword"
        }
        prompt = prompts.get(vibe, prompts["aesthetic"])
        for m in self.models:
            print(f"🤖 LLM ({m}) | Vibe: {vibe}")
            content = self._chat(
                m,
                [{"role": "system", "content": prompt}, {"role": "user", "content": script}],
                timeout=120 if len(script) >= 1000 else 40,
                max_tokens=6000 if len(script) >= 1000 else 1500
            )
            if content:
                parsed = self._parse(content)
                if parsed:
                    return parsed
                self.last_error = f"AI 已返回内容，但没有按“句子 → keyword”格式输出：{content[:200]}"
        return []

    def generate_viral_metadata(self, script):
        if not self.api_key:
            self.last_error = "未收到 AI API 密钥，请先在 API 设置里填写。"
            return None
        prompt = """Analyze the following video script and act as a viral YouTube expert.
Generate:
1. A viral, high-click-through-rate Title.
2. An engaging Description including a summary and relevant keywords.
3. 5-10 trending Hashtags.
4. A detailed AI Image Generation Prompt for a high-CTR thumbnail (for Midjourney/DALL-E).

Format your response exactly like this:
TITLE: [Your Title]
DESCRIPTION: [Your Description]
HASHTAGS: [Your Hashtags]
THUMBNAIL_PROMPT: [Your AI Image Prompt]"""
        for m in self.models:
            try:
                r = requests.post(self.api_url,
                                  headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                                  data=json.dumps({"model": m, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": script}]}), timeout=30)
                if r.status_code == 200:
                    content = r.json()["choices"][0]["message"]["content"]
                    return self._parse_youtube(content)
            except: continue
        return None

    def generate_full_script(self, topic, vibe="general"):
        if not self.api_key:
            self.last_error = "未收到 AI API 密钥，请先在 API 设置里填写。"
            return None
        if vibe == "suspense_cn":
            is_long_source = len(topic) >= 600
            if is_long_source:
                prompt = """你是抖音中文悬疑剧情解说编剧，擅长把长篇故事改写成高留存旁白。
用户会给你一篇完整故事。请把它改写成适合自动配画面的中文旁白脚本。
目标:
- 保留原文主线，不要压缩成简介或梗概。
- 必须覆盖关键剧情节点、转折、危机场景、解法和结尾反转。
- 适合 3-6 分钟竖屏悬疑解说视频。
结构:
- 开头 1-2 句必须是强钩子。
- 中段按原文事件顺序推进，保持紧张感。
- 每个重要危机场景至少写 4-8 句，不要一句带过。
- 结尾保留原故事的余味或悬念。
格式规则:
- 输出 45-80 句中文旁白，每句独立一行。
- 每句 10-26 个汉字左右，方便一句配一个画面。
- 只输出可以直接念出来的旁白。
- 不要标题、分集标题、镜头说明、编号、项目符号、角色名标签。
- 不要写“第一章”“下一幕”“画面出现”等说明。
- 不要添加原文没有的关键设定。"""
                max_tokens = 5000
            else:
                prompt = """你是抖音中文原创悬疑剧情解说编剧。
用户会给你一个主题或悬疑点子。请写一段 30-60 秒的原创悬疑短视频旁白。
结构必须是: 3 秒钩子 -> 异常细节 -> 反转或疑点 -> 悬念结尾。
规则:
- 输出 8-12 句中文旁白，每句独立一行。
- 每句 10-24 个汉字左右，适合一句话配一个画面。
- 只写可以直接念出来的旁白，不要标题、镜头说明、角色名标签、编号。
- 氛围要克制、紧张、有画面感，避免血腥暴力和真实案件指认。
- 最后一行留下悬念，适合引导观众看下一集。"""
                max_tokens = 1200

            for m in self.models:
                content = self._chat(
                    m,
                    [{"role": "system", "content": prompt}, {"role": "user", "content": topic}],
                    timeout=90 if is_long_source else 40,
                    max_tokens=max_tokens
                )
                if content:
                    return content
            return None

        vibe_instr = "educational and informative" if vibe == "educational" else "inspiring and fast-paced" if vibe == "motivational" else "poetic and slow" if vibe == "lofi" else "engaging and viral"
        prompt = f"""Act as a professional viral script writer for TikTok/Reels/Shorts.
Write a complete, high-retention video script about the following topic: '{topic}'.
The vibe should be {vibe_instr}.
Rules:
- Length: 5-10 punchy sentences.
- Each sentence should be on a NEW line.
- Do NOT include scene descriptions or speaker names. ONLY the text to be spoken.
- Make it highly engaging with a strong hook at the beginning."""
        for m in self.models:
            content = self._chat(m, [{"role": "system", "content": prompt}, {"role": "user", "content": topic}], timeout=40)
            if content:
                return content
        return None

    def _parse_youtube(self, text):
        data = {"title": "", "description": "", "hashtags": "", "thumbnail_prompt": ""}
        title_match = re.search(r'TITLE:\s*(.*)', text, re.IGNORECASE)
        desc_match = re.search(r'DESCRIPTION:\s*([\s\S]*?)(?=HASHTAGS:|$)', text, re.IGNORECASE)
        hash_match = re.search(r'HASHTAGS:\s*([\s\S]*?)(?=THUMBNAIL_PROMPT:|$)', text, re.IGNORECASE)
        thumb_match = re.search(r'THUMBNAIL_PROMPT:\s*(.*)', text, re.IGNORECASE)

        if title_match: data["title"] = title_match.group(1).strip()
        if desc_match: data["description"] = desc_match.group(1).strip()
        if hash_match: data["hashtags"] = hash_match.group(1).strip()
        if thumb_match: data["thumbnail_prompt"] = thumb_match.group(1).strip()
        return data

    def _parse(self, text):
        res = []
        for line in text.split('\n'):
            if '→' in line or '->' in line:
                arrow = '→' if '→' in line else '->'
                p = line.split(arrow, 1)
                sentence = re.sub(r'^\s*[\-\*\d\.\)\uff08\uff09、]+\s*', '', p[0]).strip()
                keyword = p[1].strip().strip('"').strip("'")
                if sentence and keyword:
                    res.append({"sentence": sentence, "keyword": keyword})
        return res

    def summarize_url(self, content):
        """Summarizes scraped web content into a video script."""
        if not self.api_key: return None
        prompt = "Act as a viral script writer. Summarize the following web content into a 5-10 sentence punchy video script for TikTok/Shorts. Return ONLY the script sentences, one per line. No scene descriptions."
        for m in self.models:
            try:
                r = requests.post(self.api_url,
                                  headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                                  data=json.dumps({"model": m, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": content[:10000]}]}), timeout=30)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            except: continue
        return None

    def generate_image_description(self, sentence):
        """Generates a detailed visual description for AI image generation fallback."""
        if not self.api_key:
            self.last_error = "未收到 AI API 密钥，无法生成画面提示词。"
            return None
        prompt = "Describe a high-quality, cinematic suspense illustration representing this sentence. If the sentence is Chinese, return the description in English. Return ONLY the description (max 28 words)."
        for m in self.models:
            content = self._chat(m, [{"role": "system", "content": prompt}, {"role": "user", "content": sentence}], timeout=30, max_tokens=120)
            if content:
                return content
        if not self.last_error:
            self.last_error = "AI 没有生成可用的画面提示词。"
        return None

    def generate_character_profile(self, script):
        """Builds a reusable English protagonist profile for consistent AI scenes."""
        if not self.api_key:
            self.last_error = "未收到 AI API 密钥，无法生成主角设定。"
            return None

        prompt = """Read the Chinese suspense story and infer the main on-screen protagonist/narrator.
Return one concise English visual character profile for consistent image generation.
Include: gender, age range, ethnicity, face, hair, clothes, mood, and 2-3 signature visual details.
Do not mention names. Do not include explanations. Max 45 words."""
        for m in self.models:
            content = self._chat(m, [{"role": "system", "content": prompt}, {"role": "user", "content": script[:12000]}], timeout=40, max_tokens=180)
            if content:
                return content.strip()
        if not self.last_error:
            self.last_error = "AI 没有生成可用的主角设定。"
        return None

    def _parse_json_array(self, text):
        cleaned = (text or "").strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start >= 0 and end > start:
            cleaned = cleaned[start:end + 1]
        return json.loads(cleaned)

    def generate_scene_prompts(self, scene_items, character_profile="", vibe="suspense_cn"):
        """Generate high-quality Seedream image prompts for already-split narration rows."""
        if not self.api_key:
            self.last_error = "AI 生图模式需要 DeepSeek/兼容 LLM API Key 来生成画面提示词。"
            return None

        prompted_items = []
        batch_size = 10
        system_prompt = f"""你是豆包 Seedream 4.5 的悬疑短视频分镜提示词导演。
任务：根据每句中文旁白，生成高质量竖屏画面提示词，用于 AI 生图。
全片主角设定：{character_profile or "保持同一个中国悬疑故事主角，真实影视感。"}
要求：
- 每个提示词必须具体描述画面主体、场景、光线、镜头、情绪和悬疑细节。
- 适合 9:16 竖屏短视频，真实中国网剧质感，电影感，暗调但画面清楚。
- 如果旁白提到同一个“我/主角”，保持主角外貌、服装和气质一致。
- 不要生成字幕、文字、水印、Logo、界面乱码。
- 避免血腥、过度恐怖、真实人物指认。
- image_prompt 写中文即可，可夹少量英文摄影术语。
- keyword 写一个短英文文件夹名，2-5 个词，用下划线连接。
只输出 JSON 数组，不要解释。格式：
[{{"id":1,"keyword":"dark_room_phone","image_prompt":"..."}}]"""

        for start in range(0, len(scene_items), batch_size):
            batch = scene_items[start:start + batch_size]
            payload = [
                {"id": idx + 1, "sentence": item["sentence"]}
                for idx, item in enumerate(batch)
            ]
            content = None
            for m in self.models:
                content = self._chat(
                    m,
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
                    ],
                    timeout=180,
                    max_tokens=3500
                )
                if content:
                    break
            if not content:
                return None

            try:
                parsed = self._parse_json_array(content)
            except Exception as exc:
                self.last_error = f"DeepSeek 画面提示词返回格式异常：{exc}；返回片段：{content[:200]}"
                return None

            by_id = {}
            for row in parsed:
                try:
                    by_id[int(row.get("id"))] = row
                except Exception:
                    continue

            for idx, item in enumerate(batch):
                row = by_id.get(idx + 1, {})
                keyword = (row.get("keyword") or item.get("keyword") or f"scene_{start + idx + 1:03d}").strip()
                keyword = re.sub(r"[^\w\-]+", "_", keyword)[:40] or f"scene_{start + idx + 1:03d}"
                prompt = (row.get("image_prompt") or "").strip()
                if not prompt:
                    self.last_error = f"DeepSeek 没有为第 {start + idx + 1} 句生成画面提示词。"
                    return None
                prompted_items.append({
                    "sentence": item["sentence"],
                    "keyword": keyword,
                    "image_prompt": prompt
                })

        return prompted_items

# ═══════════════════════════════════════════════════════════════
# WEB SCRAPER (FOR URL TO VIDEO)
# ═══════════════════════════════════════════════════════════════

class WebScraper:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    async def scrape_url(self, url):
        """Extracts text content from a URL using Playwright."""
        print(f"🌐 Scraping URL: {url}")
        content = ""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(user_agent=self.user_agent)
            try:
                await page.goto(url, wait_until="networkidle", timeout=60000)
                # Remove script/style tags
                await page.evaluate('''() => {
                    const elements = document.querySelectorAll("script, style, nav, footer, header");
                    for (const el of elements) el.remove();
                }''')
                content = await page.evaluate('() => document.body.innerText')
                # Clean up whitespace
                content = re.sub(r'\s+', ' ', content).strip()
            except Exception as e:
                print(f"❌ Scrape Error: {e}")
            finally:
                await browser.close()
        return content
