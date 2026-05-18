import base64
import asyncio
import contextlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi import BackgroundTasks, HTTPException
from PIL import Image

from app import (
    ApiKeys,
    ScrapeRequest,
    VideoSettings,
    generate_seedream_image,
    app as fastapi_app,
    local_script_segments,
    normalized_script_inputs,
    run_scrape,
    scraping_status,
    resolve_background_music,
    normalize_seedream_url,
    start_scrape,
    validate_ai_image_keys,
    validate_request_api_dependencies,
    validate_scrape_request_options,
    validate_script_keyword_key,
)


def tiny_png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), "black").save(buffer, format="PNG")
    return buffer.getvalue()


async def post_json(path, payload):
    body = json.dumps(payload).encode("utf-8")
    sent_body = False
    messages = []

    async def receive():
        nonlocal sent_body
        if sent_body:
            return {"type": "http.disconnect"}
        sent_body = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    await fastapi_app(scope, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, json.loads(response_body.decode("utf-8"))


class LocalScriptSegmentTests(unittest.TestCase):
    def test_chinese_script_splits_into_stable_scene_rows(self):
        script = "凌晨两点，我收到一条陌生短信。短信里只有五个字：别回头看。\n窗外的雨声突然停了。"

        segments = local_script_segments(script)

        self.assertEqual(
            segments,
            [
                {"sentence": "凌晨两点，我收到一条陌生短信。", "keyword": "scene_001"},
                {"sentence": "短信里只有五个字：别回头看。", "keyword": "scene_002"},
                {"sentence": "窗外的雨声突然停了。", "keyword": "scene_003"},
            ],
        )

    def test_empty_script_produces_no_segments(self):
        self.assertEqual(local_script_segments(" \n\t "), [])


class BackgroundMusicResolutionTests(unittest.TestCase):
    def test_none_disables_background_music(self):
        settings = VideoSettings(music="none")

        self.assertIsNone(resolve_background_music(settings))

    def test_blank_music_uses_default_no_music(self):
        settings = VideoSettings(music="")

        self.assertIsNone(resolve_background_music(settings))

    def test_none_music_is_case_insensitive(self):
        settings = VideoSettings(music=" NONE ")

        self.assertIsNone(resolve_background_music(settings))

    def test_existing_music_file_resolves_to_static_music_path(self):
        settings = VideoSettings(music="cinematic.mp3")

        music_path = resolve_background_music(settings)

        self.assertTrue(music_path.endswith("static\\music\\cinematic.mp3") or music_path.endswith("static/music/cinematic.mp3"))

    def test_missing_music_file_raises_clear_error(self):
        settings = VideoSettings(music="missing.mp3")

        with self.assertRaisesRegex(RuntimeError, "背景音乐文件不存在或为空"):
            resolve_background_music(settings)

    def test_nested_music_path_is_rejected(self):
        settings = VideoSettings(music="../cinematic.mp3")

        with self.assertRaisesRegex(RuntimeError, "背景音乐文件名无效"):
            resolve_background_music(settings)


class SeedreamGateTests(unittest.TestCase):
    def test_seedream_url_defaults_to_volcengine_generation_endpoint(self):
        self.assertEqual(
            normalize_seedream_url(""),
            "https://ark.cn-beijing.volces.com/api/v3/images/generations",
        )

    def test_seedream_url_accepts_api_v3_base_url(self):
        self.assertEqual(
            normalize_seedream_url("https://ark.cn-beijing.volces.com/api/v3"),
            "https://ark.cn-beijing.volces.com/api/v3/images/generations",
        )

    def test_seedream_url_keeps_full_generation_endpoint(self):
        self.assertEqual(
            normalize_seedream_url("https://ark.cn-beijing.volces.com/api/v3/images/generations/"),
            "https://ark.cn-beijing.volces.com/api/v3/images/generations",
        )

    def test_ai_source_requires_llm_and_seedream_keys(self):
        request = ScrapeRequest(
            source="ai",
            mode="single",
            query="雨夜小巷里的悬疑故事",
            api_keys=ApiKeys(llm_key="", seedream_key=""),
        )

        with contextlib.redirect_stderr(io.StringIO()):
            asyncio.run(run_scrape(request))

        self.assertEqual(scraping_status["status"], "error")
        self.assertIn("llm_key", scraping_status["error"])
        self.assertIn("seedream_key", scraping_status["error"])
        self.assertIn("不启用 Pollinations 兜底", scraping_status["error"])

    def test_ai_key_validation_reuses_same_error_message(self):
        request = ScrapeRequest(
            source="ai",
            mode="single",
            query="雨夜小巷里的悬疑故事",
            api_keys=ApiKeys(llm_key="", seedream_key=""),
        )

        with self.assertRaisesRegex(RuntimeError, "llm_key.*seedream_key"):
            validate_ai_image_keys(request)

    def test_ai_key_validation_treats_blank_strings_as_missing(self):
        request = ScrapeRequest(
            source="ai",
            mode="single",
            query="雨夜小巷里的悬疑故事",
            api_keys=ApiKeys(llm_key="   ", seedream_key="\t"),
        )

        with self.assertRaisesRegex(RuntimeError, "llm_key.*seedream_key"):
            validate_ai_image_keys(request)

    def test_seedream_generation_rejects_blank_key_before_network(self):
        with self.assertRaisesRegex(RuntimeError, "seedream_key"):
            asyncio.run(
                generate_seedream_image(
                    "雨夜小巷",
                    Path("unused_seedream_output.jpg"),
                    ApiKeys(seedream_key="   "),
                )
            )

    def test_seedream_url_image_download_must_be_valid_image(self):
        post_response = Mock(status_code=200)
        post_response.json.return_value = {"data": [{"url": "https://example.test/not-image"}]}
        get_response = Mock(content=b"", headers={})
        get_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=post_response), patch("requests.get", return_value=get_response):
            with self.assertRaisesRegex(RuntimeError, "Seedream 生图失败") as raised:
                asyncio.run(
                    generate_seedream_image(
                        "雨夜小巷",
                        Path("unused_seedream_output.jpg"),
                        ApiKeys(seedream_key="sk-test"),
                    )
                )
        self.assertIn("最后错误", str(raised.exception))
        self.assertIn("返回了空图片内容", str(raised.exception))

    def test_seedream_url_image_download_rejects_non_image_body(self):
        post_response = Mock(status_code=200)
        post_response.json.return_value = {"data": [{"url": "https://example.test/error-page"}]}
        get_response = Mock(content=b"<html>not an image</html>", headers={})
        get_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=post_response), patch("requests.get", return_value=get_response), patch.object(Path, "write_bytes", return_value=None) as write_bytes:
            with self.assertRaisesRegex(RuntimeError, "Seedream 生图失败") as raised:
                asyncio.run(
                    generate_seedream_image(
                        "雨夜小巷",
                        Path("unused_seedream_output.jpg"),
                        ApiKeys(seedream_key="sk-test"),
                    )
                )

        message = str(raised.exception)
        self.assertIn("最后错误", message)
        self.assertIn("Seedream 图片下载", message)
        self.assertIn("不是有效图片", message)
        write_bytes.assert_not_called()

    def test_seedream_http_error_keeps_response_detail(self):
        post_response = Mock(status_code=500, text="internal error")
        post_response.json.return_value = {"error": {"message": "quota exhausted"}}

        with patch("requests.post", return_value=post_response):
            with self.assertRaisesRegex(RuntimeError, "Seedream 生图失败") as raised:
                asyncio.run(
                    generate_seedream_image(
                        "雨夜小巷",
                        Path("unused_seedream_output.jpg"),
                        ApiKeys(seedream_key="sk-test"),
                    )
                )

        message = str(raised.exception)
        self.assertIn("Seedream HTTP 500", message)
        self.assertIn("quota exhausted", message)

    def test_seedream_b64_image_writes_valid_image(self):
        image_data = tiny_png_bytes()
        post_response = Mock(status_code=200)
        post_response.json.return_value = {
            "data": [{"b64_json": base64.b64encode(image_data).decode("ascii")}]
        }
        output_path = Path("codex_tmp_seedream_test_output.png")

        with patch("requests.post", return_value=post_response), patch.object(Path, "write_bytes", return_value=None) as write_bytes:
            result = asyncio.run(
                generate_seedream_image(
                    "雨夜小巷",
                    output_path,
                    ApiKeys(seedream_key=" sk-test "),
                )
            )

        self.assertEqual(result, str(output_path))
        write_bytes.assert_called_once_with(image_data)

    def test_seedream_b64_payload_must_be_valid_image(self):
        post_response = Mock(status_code=200)
        post_response.json.return_value = {
            "data": [{"b64_json": base64.b64encode(b"not an image").decode("ascii")}]
        }

        with patch("requests.post", return_value=post_response), patch.object(Path, "write_bytes", return_value=None) as write_bytes:
            with self.assertRaisesRegex(RuntimeError, "Seedream 生图失败") as raised:
                asyncio.run(
                    generate_seedream_image(
                        "雨夜小巷",
                        Path("unused_seedream_output.jpg"),
                        ApiKeys(seedream_key="sk-test"),
                    )
                )

        message = str(raised.exception)
        self.assertIn("Seedream b64_json", message)
        self.assertIn("不是有效图片", message)
        write_bytes.assert_not_called()


class LlmEndpointValidationTests(unittest.TestCase):
    def test_api_analyze_rejects_missing_llm_key_before_processor(self):
        with patch("app.LLMProcessor") as processor:
            status, data = asyncio.run(post_json(
                "/api/analyze",
                {
                    "script": "凌晨两点，我收到一条陌生短信。",
                    "api_keys": {"llm_key": ""},
                },
            ))

        self.assertEqual(status, 400)
        self.assertIn("AI 文本密钥", data["detail"])
        processor.assert_not_called()

    def test_api_generate_script_rejects_missing_llm_key_before_processor(self):
        with patch("app.LLMProcessor") as processor:
            status, data = asyncio.run(post_json(
                "/api/generate_script",
                {
                    "topic": "雨夜收到陌生短信",
                    "vibe": "suspense_cn",
                    "api_keys": {"llm_key": " "},
                },
            ))

        self.assertEqual(status, 400)
        self.assertIn("AI 文本密钥", data["detail"])
        processor.assert_not_called()

    def test_api_scrape_url_rejects_missing_llm_key_before_scraping(self):
        with patch("app.WebScraper") as web_scraper, patch("app.LLMProcessor") as processor:
            status, data = asyncio.run(post_json(
                "/api/scrape_url",
                {
                    "url": "https://example.com/story",
                    "api_keys": {"llm_key": ""},
                },
            ))

        self.assertEqual(status, 400)
        self.assertIn("AI 文本密钥", data["detail"])
        web_scraper.assert_not_called()
        processor.assert_not_called()


class ScrapeRequestValidationTests(unittest.TestCase):
    def test_request_options_are_normalized_before_validation(self):
        request = ScrapeRequest(
            source=" AI ",
            media_type=" PHOTO ",
            mode=" SCRIPT ",
            script="凌晨两点，我听见门外有人低声喊我的名字。",
            api_keys=ApiKeys(llm_key="sk-test", seedream_key="sk-test"),
        )

        validate_scrape_request_options(request)
        validate_request_api_dependencies(request)

        self.assertEqual(request.source, "ai")
        self.assertEqual(request.media_type, "photo")
        self.assertEqual(request.mode, "script")

    def test_invalid_source_is_rejected_before_background_work(self):
        request = ScrapeRequest(source="unknown", query="雨夜小巷")

        with self.assertRaisesRegex(RuntimeError, "素材来源无效"):
            validate_scrape_request_options(request)

    def test_invalid_media_type_is_rejected(self):
        request = ScrapeRequest(media_type="gif", query="雨夜小巷")

        with self.assertRaisesRegex(RuntimeError, "素材类型无效"):
            validate_scrape_request_options(request)

    def test_ai_source_rejects_video_media_type(self):
        request = ScrapeRequest(source="ai", media_type="video", query="雨夜小巷")

        with self.assertRaisesRegex(RuntimeError, "只支持图片素材"):
            validate_scrape_request_options(request)

    def test_single_mode_requires_query(self):
        request = ScrapeRequest(source="pexels", query="  ")

        with self.assertRaisesRegex(RuntimeError, "需要先输入主题 query"):
            validate_scrape_request_options(request)

    def test_count_must_stay_inside_ui_range(self):
        request = ScrapeRequest(source="pexels", query="雨夜小巷", count=16)

        with self.assertRaisesRegex(RuntimeError, "1 到 15"):
            validate_scrape_request_options(request)

    def test_single_stock_search_rejects_auto_video(self):
        request = ScrapeRequest(source="pexels", query="雨夜小巷", auto_video=True)

        with self.assertRaisesRegex(RuntimeError, "单条素材搜索不会自动合成视频"):
            validate_scrape_request_options(request)

    def test_auto_video_rejects_disabled_voice(self):
        request = ScrapeRequest(
            source="pexels",
            query="雨夜小巷",
            auto_video=True,
            video_settings=VideoSettings(voice=" NONE "),
        )

        with self.assertRaisesRegex(RuntimeError, "自动合成视频需要选择一个 AI 配音"):
            validate_scrape_request_options(request)

    def test_asset_only_mode_allows_disabled_voice(self):
        request = ScrapeRequest(
            source="pexels",
            query="雨夜小巷",
            auto_video=False,
            video_settings=VideoSettings(voice="none"),
        )

        validate_scrape_request_options(request)

    def test_start_scrape_rejects_invalid_request_before_queuing_task(self):
        request = ScrapeRequest(source="pexels", query="  ")
        background_tasks = BackgroundTasks()
        scraping_status["is_running"] = False
        scraping_status["status"] = "success"
        scraping_status["message"] = "old success"
        scraping_status["error"] = None
        scraping_status["final_video"] = "/downloads/old/final.mp4"
        scraping_status["results"] = [{"keyword": "old", "files": ["/downloads/old/final.mp4"]}]

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(start_scrape(request, background_tasks))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("需要先输入主题 query", raised.exception.detail)
        self.assertEqual(background_tasks.tasks, [])
        self.assertEqual(scraping_status["status"], "error")
        self.assertEqual(scraping_status["error"], raised.exception.detail)
        self.assertIn("需要先输入主题 query", scraping_status["message"])
        self.assertEqual(scraping_status["progress"], 100)
        self.assertIsNone(scraping_status["final_video"])
        self.assertEqual(scraping_status["results"], [])

    def test_start_scrape_rejects_empty_script_mode_before_queuing_task(self):
        request = ScrapeRequest(mode="script", script=" ", scripts=["", "  "])
        background_tasks = BackgroundTasks()
        scraping_status["is_running"] = False

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(start_scrape(request, background_tasks))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("至少一段旁白脚本", raised.exception.detail)
        self.assertEqual(background_tasks.tasks, [])

    def test_script_mode_ignores_blank_batch_entries(self):
        request = ScrapeRequest(
            mode="script",
            script="   备用脚本不会重复使用   ",
            scripts=["", "  第一段旁白  ", "\t", "第二段旁白\n"],
        )

        self.assertEqual(normalized_script_inputs(request), ["第一段旁白", "第二段旁白"])
        validate_scrape_request_options(request)

    def test_script_mode_uses_single_script_when_batch_is_empty(self):
        request = ScrapeRequest(mode="script", script="   只有一段旁白   ", scripts=[" ", ""])

        self.assertEqual(normalized_script_inputs(request), ["只有一段旁白"])
        validate_scrape_request_options(request)

    def test_stock_script_mode_requires_llm_key_for_keyword_analysis(self):
        request = ScrapeRequest(
            source="pexels",
            mode="script",
            script="凌晨两点，我听见门外有人低声喊我的名字。",
            auto_video=False,
            api_keys=ApiKeys(llm_key=" "),
        )

        with self.assertRaisesRegex(RuntimeError, "AI 文本密钥"):
            validate_script_keyword_key(request)

    def test_stock_script_mode_api_dependency_rejects_missing_llm_key(self):
        request = ScrapeRequest(
            source="pixabay",
            mode="script",
            script="凌晨两点，我听见门外有人低声喊我的名字。",
            auto_video=False,
            api_keys=ApiKeys(llm_key=""),
        )

        with self.assertRaisesRegex(RuntimeError, "搜索关键词"):
            validate_request_api_dependencies(request)

    def test_stock_script_mode_accepts_llm_key_without_seedream_key(self):
        request = ScrapeRequest(
            source="pexels",
            mode="script",
            script="凌晨两点，我听见门外有人低声喊我的名字。",
            auto_video=False,
            api_keys=ApiKeys(llm_key="sk-test", seedream_key=""),
        )

        validate_request_api_dependencies(request)

    def test_start_scrape_rejects_single_stock_auto_video_before_queuing_task(self):
        request = ScrapeRequest(source="pexels", query="雨夜小巷", auto_video=True)
        background_tasks = BackgroundTasks()
        scraping_status["is_running"] = False

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(start_scrape(request, background_tasks))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("单条素材搜索不会自动合成视频", raised.exception.detail)
        self.assertEqual(background_tasks.tasks, [])

    def test_start_scrape_rejects_missing_seedream_keys_before_queuing_task(self):
        request = ScrapeRequest(
            source="ai",
            mode="single",
            query="雨夜小巷里的悬疑故事",
            api_keys=ApiKeys(llm_key="", seedream_key=""),
        )
        background_tasks = BackgroundTasks()
        scraping_status["is_running"] = False

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(start_scrape(request, background_tasks))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("llm_key", raised.exception.detail)
        self.assertIn("seedream_key", raised.exception.detail)
        self.assertEqual(background_tasks.tasks, [])

    def test_start_scrape_rejects_stock_script_without_llm_key_before_queuing_task(self):
        request = ScrapeRequest(
            source="pexels",
            mode="script",
            script="凌晨两点，我听见门外有人低声喊我的名字。",
            auto_video=False,
            api_keys=ApiKeys(llm_key=""),
        )
        background_tasks = BackgroundTasks()
        scraping_status["is_running"] = False

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(start_scrape(request, background_tasks))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("AI 文本密钥", raised.exception.detail)
        self.assertEqual(background_tasks.tasks, [])

    def test_start_scrape_rejects_missing_music_before_queuing_task(self):
        request = ScrapeRequest(
            source="pexels",
            query="雨夜小巷",
            auto_video=True,
            video_settings=VideoSettings(music="missing.mp3"),
        )
        background_tasks = BackgroundTasks()
        scraping_status["is_running"] = False

        with self.assertRaises(HTTPException) as raised:
            asyncio.run(start_scrape(request, background_tasks))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("背景音乐文件不存在或为空", raised.exception.detail)
        self.assertEqual(background_tasks.tasks, [])

    def test_api_scrape_rejects_missing_seedream_keys_with_detail(self):
        scraping_status["is_running"] = False

        status, data = asyncio.run(post_json(
            "/api/scrape",
            {
                "source": "ai",
                "mode": "single",
                "query": "雨夜小巷里的悬疑故事",
                "api_keys": {"llm_key": "", "seedream_key": ""},
            },
        ))

        self.assertEqual(status, 400)
        detail = data["detail"]
        self.assertIn("llm_key", detail)
        self.assertIn("seedream_key", detail)
        self.assertIn("不启用 Pollinations 兜底", detail)
        self.assertFalse(scraping_status["is_running"])

    def test_api_scrape_rejects_ai_video_media_type_with_detail(self):
        scraping_status["is_running"] = False

        status, data = asyncio.run(post_json(
            "/api/scrape",
            {
                "source": "ai",
                "media_type": "video",
                "mode": "single",
                "query": "雨夜小巷里的悬疑故事",
                "api_keys": {"llm_key": "sk-test", "seedream_key": "sk-test"},
            },
        ))

        self.assertEqual(status, 400)
        self.assertIn("只支持图片素材", data["detail"])
        self.assertFalse(scraping_status["is_running"])

    def test_api_scrape_rejects_disabled_voice_auto_video_with_detail(self):
        scraping_status["is_running"] = False

        status, data = asyncio.run(post_json(
            "/api/scrape",
            {
                "source": "ai",
                "mode": "script",
                "script": "凌晨两点，我听见门外有人低声喊我的名字。",
                "auto_video": True,
                "video_settings": {"voice": "none"},
                "api_keys": {"llm_key": "sk-test", "seedream_key": "sk-test"},
            },
        ))

        self.assertEqual(status, 400)
        self.assertIn("自动合成视频需要选择一个 AI 配音", data["detail"])
        self.assertFalse(scraping_status["is_running"])

    def test_api_scrape_rejects_stock_script_without_llm_key_with_detail(self):
        scraping_status["is_running"] = False

        status, data = asyncio.run(post_json(
            "/api/scrape",
            {
                "source": "pexels",
                "mode": "script",
                "script": "凌晨两点，我听见门外有人低声喊我的名字。",
                "auto_video": False,
                "api_keys": {"llm_key": ""},
            },
        ))

        self.assertEqual(status, 400)
        self.assertIn("AI 文本密钥", data["detail"])
        self.assertFalse(scraping_status["is_running"])

    def test_single_search_reports_error_when_no_media_is_found(self):
        request = ScrapeRequest(
            source="pexels",
            mode="single",
            query="codex missing media case",
            auto_video=False,
        )
        scraping_status["is_running"] = False
        scraping_status["error"] = None

        with patch("app.universal_search", new=AsyncMock(return_value=[])):
            with contextlib.redirect_stderr(io.StringIO()):
                asyncio.run(run_scrape(request))

        self.assertEqual(scraping_status["status"], "error")
        self.assertIn("没有找到可用素材", scraping_status["error"])
        self.assertFalse(scraping_status["is_running"])

    def test_asset_only_script_reports_error_when_a_scene_has_no_media(self):
        request = ScrapeRequest(
            source="pexels",
            mode="script",
            script="第一句。第二句。",
            auto_video=False,
            api_keys=ApiKeys(llm_key="sk-test"),
        )
        processor = Mock()
        processor.extract_keywords.return_value = [
            {"sentence": "第一句。", "keyword": "scene_001"},
            {"sentence": "第二句。", "keyword": "scene_002"},
        ]

        async def fake_universal_search(keyword, **kwargs):
            return [Path("README.md")] if keyword == "scene_001" else []

        scraping_status["is_running"] = False
        scraping_status["error"] = None

        with patch.object(Path, "mkdir", return_value=None), \
             patch("app.LLMProcessor", return_value=processor), \
             patch("app.universal_search", new=AsyncMock(side_effect=fake_universal_search)):
            with contextlib.redirect_stderr(io.StringIO()):
                asyncio.run(run_scrape(request))

        self.assertEqual(scraping_status["status"], "error")
        self.assertIn("分镜素材不完整", scraping_status["error"])
        self.assertIn("scene_002", scraping_status["error"])
        self.assertIn("pexels 未找到可用图片素材", scraping_status["error"])
        self.assertFalse(scraping_status["is_running"])

    def test_script_batch_search_exception_keeps_scene_context(self):
        request = ScrapeRequest(
            source="pexels",
            mode="script",
            script="第一句。第二句。",
            auto_video=False,
            api_keys=ApiKeys(llm_key="sk-test"),
        )
        processor = Mock()
        processor.extract_keywords.return_value = [
            {"sentence": "第一句。", "keyword": "scene_001"},
            {"sentence": "第二句。", "keyword": "scene_002"},
        ]

        async def fake_universal_search(keyword, **kwargs):
            if keyword == "scene_002":
                raise RuntimeError("Seedream HTTP 500: quota exhausted")
            return [Path("README.md")]

        scraping_status["is_running"] = False
        scraping_status["error"] = None

        with patch.object(Path, "mkdir", return_value=None), \
             patch("app.LLMProcessor", return_value=processor), \
             patch("app.universal_search", new=AsyncMock(side_effect=fake_universal_search)):
            with contextlib.redirect_stderr(io.StringIO()):
                asyncio.run(run_scrape(request))

        self.assertEqual(scraping_status["status"], "error")
        self.assertIn("分镜素材不完整", scraping_status["error"])
        self.assertIn("scene_002", scraping_status["error"])
        self.assertIn("Seedream HTTP 500: quota exhausted", scraping_status["error"])
        self.assertFalse(scraping_status["is_running"])

    def test_asset_only_single_search_does_not_load_video_engine(self):
        request = ScrapeRequest(
            source="pexels",
            mode="single",
            query="雨夜小巷",
            auto_video=False,
        )
        scraping_status["is_running"] = False
        scraping_status["error"] = None

        with patch("app.universal_search", new=AsyncMock(return_value=["unused"])), \
             patch("app.require_media_files", return_value=[Path("downloads/fake.jpg")]), \
             patch("app.load_video_engine", side_effect=AssertionError("video deps loaded")):
            asyncio.run(run_scrape(request))

        self.assertEqual(scraping_status["status"], "success")
        self.assertIsNone(scraping_status["error"])
        self.assertFalse(scraping_status["is_running"])


if __name__ == "__main__":
    unittest.main()
