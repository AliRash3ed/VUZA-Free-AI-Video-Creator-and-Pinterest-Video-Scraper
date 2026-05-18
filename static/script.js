console.log("🚀 VUZA v5 — 中文悬疑短视频自动生成工具");

document.addEventListener('DOMContentLoaded', () => {
    // ── Elements ──
    const scrapeBtn = document.getElementById('scrape-btn');
    const queryInput = document.getElementById('query');
    const scriptInput = document.getElementById('script');
    const countInput = document.getElementById('count');
    const statusCard = document.getElementById('status-card');
    const statusMsg = document.getElementById('status-msg');
    const statusPercent = document.getElementById('status-percent');
    const progressFill = document.getElementById('progress-fill');
    const galleryContainer = document.getElementById('gallery-container');
    const clearBtn = document.getElementById('clear-gallery');
    const analyzeBtn = document.getElementById('analyze-btn');
    const generateScriptBtn = document.getElementById('generate-script-btn');
    const topicInput = document.getElementById('topic-input');
    const analysisPanel = document.getElementById('analysis-panel');
    const aiTitle = document.getElementById('ai-title');
    const aiDesc = document.getElementById('ai-desc');
    const aiHashtags = document.getElementById('ai-hashtags');
    const aiThumbPrompt = document.getElementById('ai-thumb-prompt');

    const tabSingle = document.getElementById('tab-single');
    const tabScript = document.getElementById('tab-script');
    const singleArea = document.getElementById('single-input-area');
    const scriptArea = document.getElementById('script-input-area');
    const scriptsContainer = document.getElementById('scripts-container');
    const addScriptBtn = document.getElementById('add-script-btn');
    const templateSelect = document.getElementById('template-select');
    const scrapeUrlBtn = document.getElementById('scrape-url-btn');
    const urlInput = document.getElementById('url-input');

    let currentMode = 'single';
    let statusInterval = null;
    let finalVideoUrl = '';
    let pollConnectionErrorShown = false;

    // ═══ SETTINGS PANEL TOGGLE ═══
    const settingsToggle = document.getElementById('settings-toggle');
    const settingsBody = document.getElementById('settings-body');
    const settingsPanel = document.getElementById('settings-panel');

    if (settingsToggle) {
        settingsToggle.addEventListener('click', () => {
            settingsBody.classList.toggle('hidden');
            settingsPanel.classList.toggle('open');
        });
    }

    // ═══ LOAD SAVED KEYS FROM localStorage ═══
    function loadKeys() {
        const keys = JSON.parse(localStorage.getItem('vuza_api_keys') || '{}');
        if (keys.llm_key) document.getElementById('llm-key').value = keys.llm_key;
        if (keys.llm_url) document.getElementById('llm-url').value = keys.llm_url;
        if (keys.llm_model) document.getElementById('llm-model').value = keys.llm_model;
        if (keys.seedream_key) document.getElementById('seedream-key').value = keys.seedream_key;
        if (keys.seedream_url) document.getElementById('seedream-url').value = keys.seedream_url;
        if (keys.seedream_model) document.getElementById('seedream-model').value = keys.seedream_model;
        if (keys.pexels_key) document.getElementById('pexels-key').value = keys.pexels_key;
        if (keys.pixabay_key) document.getElementById('pixabay-key').value = keys.pixabay_key;
        if (keys.yt_client_id) document.getElementById('yt-client-id').value = keys.yt_client_id;
        if (keys.yt_client_secret) document.getElementById('yt-client-secret').value = keys.yt_client_secret;
        if (keys.eleven_key) document.getElementById('eleven-key').value = keys.eleven_key;
    }

    function saveKeys() {
        const keys = {
            llm_key: document.getElementById('llm-key').value.trim(),
            llm_url: document.getElementById('llm-url').value.trim(),
            llm_model: document.getElementById('llm-model').value.trim(),
            seedream_key: document.getElementById('seedream-key').value.trim(),
            seedream_url: document.getElementById('seedream-url').value.trim(),
            seedream_model: document.getElementById('seedream-model').value.trim(),
            pexels_key: document.getElementById('pexels-key').value.trim(),
            pixabay_key: document.getElementById('pixabay-key').value.trim(),
            yt_client_id: document.getElementById('yt-client-id').value.trim(),
            yt_client_secret: document.getElementById('yt-client-secret').value.trim(),
            eleven_key: document.getElementById('eleven-key').value.trim()
        };
        localStorage.setItem('vuza_api_keys', JSON.stringify(keys));
        showToast('✅ 设置已保存', 'success');
    }

    function getKeys() {
        const saved = JSON.parse(localStorage.getItem('vuza_api_keys') || '{}');
        const valueOf = (id) => {
            const el = document.getElementById(id);
            return el ? el.value.trim() : '';
        };
        const current = {
            llm_key: valueOf('llm-key'),
            llm_url: valueOf('llm-url'),
            llm_model: valueOf('llm-model'),
            seedream_key: valueOf('seedream-key'),
            seedream_url: valueOf('seedream-url'),
            seedream_model: valueOf('seedream-model'),
            pexels_key: valueOf('pexels-key'),
            pixabay_key: valueOf('pixabay-key'),
            yt_client_id: valueOf('yt-client-id'),
            yt_client_secret: valueOf('yt-client-secret'),
            eleven_key: valueOf('eleven-key')
        };
        const merged = { ...saved };
        Object.entries(current).forEach(([key, value]) => {
            if (value) merged[key] = value;
        });
        return merged;
    }

    function persistKeys(keys) {
        localStorage.setItem('vuza_api_keys', JSON.stringify(keys));
    }

    async function readErrorMessage(response, fallback) {
        try {
            const err = await response.json();
            const message = err.detail || err.message;
            if (typeof message === 'string') return message;
            if (message) return JSON.stringify(message);
            return fallback;
        } catch (error) {
            return fallback;
        }
    }

    function showApiSettings() {
        if (settingsBody && settingsBody.classList.contains('hidden')) {
            settingsBody.classList.remove('hidden');
            settingsPanel.classList.add('open');
        }
    }

    // Load on start
    loadKeys();

    // Save button
    const saveBtn = document.getElementById('save-keys-btn');
    if (saveBtn) saveBtn.addEventListener('click', saveKeys);

    // ═══ MODE TABS ═══
    if (!tabSingle || !tabScript) return;

    function switchMode(mode) {
        currentMode = mode;
        if (mode === 'single') {
            tabSingle.classList.add('active');
            tabScript.classList.remove('active');
            singleArea.classList.remove('hidden');
            scriptArea.classList.add('hidden');
        } else {
            tabSingle.classList.remove('active');
            tabScript.classList.add('active');
            singleArea.classList.add('hidden');
            scriptArea.classList.remove('hidden');
        }
        updatePrimaryButtonText();
    }

    tabSingle.addEventListener('click', () => switchMode('single'));
    tabScript.addEventListener('click', () => switchMode('script'));

    // ═══ BATCH SCRIPTS ═══
    if (addScriptBtn) {
        addScriptBtn.addEventListener('click', () => {
            const div = document.createElement('div');
            div.className = 'script-item';
            div.innerHTML = `<textarea class="script-input" placeholder="粘贴另一个脚本，用于批量生成"></textarea><button type="button" class="remove-script-btn">×</button>`;
            scriptsContainer.appendChild(div);
            div.querySelector('.remove-script-btn').addEventListener('click', () => div.remove());
        });
    }

    // ═══ TEMPLATES ═══
    if (templateSelect) {
        templateSelect.addEventListener('change', () => {
            const template = templateSelect.value;
            const firstScript = scriptsContainer.querySelector('.script-input');
            if (!firstScript) return;

            if (template === 'suspense_cn') {
                firstScript.value = "凌晨两点，我收到一条陌生短信。\n短信里只有五个字：别回头看。\n可我明明一个人住在这间屋子。\n窗外的雨声突然停了。\n门缝下面，慢慢塞进来一张旧照片。\n照片上站着的，竟然是十年前的我。\n更奇怪的是，我身后还有一个模糊的人影。\n下一秒，手机又响了：他已经进来了。";
                document.getElementById('vibe-suspense').checked = true;
                applySuspenseDefaults();
            } else if (template === 'motivational') {
                firstScript.value = "真正拉开差距的，从来不是某一次爆发。\n而是你在没人看见的时候，依然愿意往前走。\n今天慢一点没关系，只要别停下来。\n你以为自己只是撑过了一天，其实你正在变强。";
                document.getElementById('vibe-aesthetic').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'educational') {
                firstScript.value = "你知道吗，蜂蜜几乎不会自然变质。\n考古学家曾在古埃及墓葬里发现三千多年前的蜂蜜。\n它依然可以食用。\n原因是蜂蜜含水量低、酸性强，细菌很难在里面生长。";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-16-9').checked = true;
            } else if (template === 'storytelling') {
                firstScript.value = "那家旧书店只在雨夜开门。\n小女孩在最里面的书架上，发现了一本没有书名的地图册。\n她刚翻开第一页，柜台上的钟就停了。\n地图中央，慢慢浮现出她家的地址。";
                document.getElementById('vibe-aesthetic').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'lofi_vibes') {
                firstScript.value = "深夜的雨敲在窗户上。\n桌上还有一杯温热的咖啡。\n远处的城市灯光慢慢散开。\n这一刻，世界终于安静下来。";
                document.getElementById('vibe-lofi').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'news') {
                firstScript.value = "最新消息，科学家发现了一颗可能适合生命存在的类地行星。\n它距离地球约二十光年，围绕一颗红矮星运行。\n研究团队正在进一步确认那里是否存在水和大气。\n这项发现可能会改写我们对宜居星球的认识。";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-16-9').checked = true;
                document.getElementById('subtitle-style').value = 'yellow_box';
            } else if (template === 'tutorial') {
                firstScript.value = "三步做出一杯更稳定的手冲咖啡。\n第一步，把咖啡豆磨到中细研磨。\n第二步，把水温控制在九十二到九十五度。\n第三步，绕圈慢慢注水，让香气充分释放。";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-9-16').checked = true;
                document.getElementById('subtitle-style').value = 'bold_outline';
            }
            if (template) showToast('✅ 模板已载入', 'success');
        });
    }

    // ═══ DYNAMIC VOICES ═══
    const languageSelect = document.getElementById('language-select');
    const voiceSelect = document.getElementById('voice-select');

    const voiceMap = {
        'en-US': [
            { name: '🎙️ Christopher（免费）', value: 'en-US-ChristopherNeural' },
            { name: '🎤 Jenny（免费）', value: 'en-US-JennyNeural' },
            { name: '🌟 Adam（ElevenLabs）', value: 'eleven_pNInz6obpg8ndclQU7Nc' },
            { name: '🌟 Antoni（ElevenLabs）', value: 'eleven_ErXwBPLxhSj618Y4yxKI' },
            { name: '🌟 Bella（ElevenLabs）', value: 'eleven_EXAVITQu4vr4xnSDxMaL' }
        ],
        'en-GB': [
            { name: '🇬🇧 Ryan', value: 'en-GB-RyanNeural' },
            { name: '🇬🇧 Sonia', value: 'en-GB-SoniaNeural' },
            { name: '🇬🇧 Libby', value: 'en-GB-LibbyNeural' },
            { name: '🇬🇧 Thomas', value: 'en-GB-ThomasNeural' }
        ],
        'es-ES': [
            { name: '🇪🇸 Alvaro', value: 'es-ES-AlvaroNeural' },
            { name: '🇪🇸 Elvira', value: 'es-ES-ElviraNeural' }
        ],
        'fr-FR': [
            { name: '🇫🇷 Henri', value: 'fr-FR-HenriNeural' },
            { name: '🇫🇷 Denise', value: 'fr-FR-DeniseNeural' }
        ],
        'de-DE': [
            { name: '🇩🇪 Conrad', value: 'de-DE-ConradNeural' },
            { name: '🇩🇪 Katja', value: 'de-DE-KatjaNeural' }
        ],
        'it-IT': [
            { name: '🇮🇹 Diego', value: 'it-IT-DiegoNeural' },
            { name: '🇮🇹 Elsa', value: 'it-IT-ElsaNeural' }
        ],
        'hi-IN': [
            { name: '🇮🇳 Madhur', value: 'hi-IN-MadhurNeural' },
            { name: '🇮🇳 Swara', value: 'hi-IN-SwaraNeural' }
        ],
        'ur-PK': [
            { name: '🇵🇰 Asad', value: 'ur-PK-AsadNeural' },
            { name: '🇵🇰 Uzma', value: 'ur-PK-UzmaNeural' }
        ],
        'zh-CN': [
            { name: '🇨🇳 云扬（男声）', value: 'zh-CN-YunyangNeural' },
            { name: '🇨🇳 晓晓（女声）', value: 'zh-CN-XiaoxiaoNeural' }
        ],
        'ja-JP': [
            { name: '🇯🇵 Keita', value: 'ja-JP-KeitaNeural' },
            { name: '🇯🇵 Nanami', value: 'ja-JP-NanamiNeural' }
        ]
    };

    function updateVoices() {
        const lang = languageSelect.value;
        const voices = voiceMap[lang] || [];
        voiceSelect.innerHTML = voices.map(v => `<option value="${v.value}">${v.name}</option>`).join('') + '<option value="none">🔇 不配音（仅素材模式）</option>';
    }

    function applySuspenseDefaults() {
        const setChecked = (id) => {
            const el = document.getElementById(id);
            if (el) el.checked = true;
        };

        setChecked('src-ai');
        setChecked('type-photo');
        setChecked('ratio-9-16');
        setChecked('emoji-subs-off');

        const suspenseVibe = document.getElementById('vibe-suspense');
        if (suspenseVibe) suspenseVibe.checked = true;

        if (languageSelect) {
            languageSelect.value = 'zh-CN';
            updateVoices();
        }
        if (voiceSelect) voiceSelect.value = 'zh-CN-YunyangNeural';

        const musicSelect = document.getElementById('music-select');
        if (musicSelect) musicSelect.value = 'none';

        const subtitleStyle = document.getElementById('subtitle-style');
        if (subtitleStyle) subtitleStyle.value = 'high_retention';

        if (topicInput) topicInput.placeholder = '短主题：半夜收到已故室友的短信。也可以直接粘贴长篇故事，系统会自动改写成长版解说脚本。';
    }

    if (languageSelect) {
        languageSelect.addEventListener('change', updateVoices);
        updateVoices(); // Initial load
    }

    const suspenseVibe = document.getElementById('vibe-suspense');
    if (suspenseVibe) {
        suspenseVibe.addEventListener('change', () => {
            if (suspenseVibe.checked) applySuspenseDefaults();
        });
    }

    applySuspenseDefaults();
    switchMode('script');
    resumeCurrentJob();

    document.querySelectorAll('input[name="source"], input[name="auto_video"]').forEach(input => {
        input.addEventListener('change', updatePrimaryButtonText);
    });

    // ═══ URL SCRAPER ACTION ═══
    if (scrapeUrlBtn) {
        scrapeUrlBtn.addEventListener('click', async () => {
            const url = urlInput.value.trim();
            if (!url) { showToast('请先粘贴文章链接', 'error'); return; }

            const keys = getKeys();
            scrapeUrlBtn.disabled = true;
            scrapeUrlBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在提取...';

            try {
                const response = await fetch('/api/scrape_url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: url,
                        api_keys: keys
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    const firstScript = scriptsContainer.querySelector('.script-input');
                    if (firstScript) {
                        firstScript.value = data.script;
                        showToast('✅ 已提取并总结成脚本', 'success');
                    }
                } else {
                    showToast(await readErrorMessage(response, '提取失败'), 'error');
                }
            } catch (error) {
                showToast('网络错误', 'error');
            } finally {
                scrapeUrlBtn.disabled = false;
                scrapeUrlBtn.innerHTML = '<i class="fas fa-file-download"></i> 提取脚本';
            }
        });
    }

    // ═══ AI SCRIPT GENERATOR ACTION ═══
    if (generateScriptBtn) {
        generateScriptBtn.addEventListener('click', async () => {
            const topic = topicInput.value.trim();
            if (!topic) { showToast('请先输入悬疑主题或粘贴长篇原文', 'error'); return; }

            const keys = getKeys();
            const vibe = document.querySelector('input[name="vibe"]:checked').value;

            if (!keys.llm_key) {
                showApiSettings();
                showToast('请先在 API 设置里填写 AI API 密钥', 'error');
                return;
            }
            persistKeys(keys);

            generateScriptBtn.disabled = true;
            generateScriptBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在生成...';

            try {
                const response = await fetch('/api/generate_script', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        topic: topic,
                        vibe: vibe,
                        api_keys: {
                            llm_key: keys.llm_key || '',
                            llm_url: keys.llm_url || 'https://openrouter.ai/api/v1/chat/completions',
                            llm_model: keys.llm_model || ''
                        }
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    const firstScript = scriptsContainer.querySelector('.script-input');
                    if (firstScript) {
                        firstScript.value = data.script;
                        showToast('✅ 脚本生成成功', 'success');
                    }
                } else {
                    showToast(await readErrorMessage(response, '脚本生成失败'), 'error');
                }
            } catch (error) {
                showToast('网络错误', 'error');
            } finally {
                generateScriptBtn.disabled = false;
                generateScriptBtn.innerHTML = '<i class="fas fa-magic"></i> 生成脚本';
            }
        });
    }

    // ═══ AI ANALYSIS ACTION ═══
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async () => {
            const scripts = Array.from(document.querySelectorAll('.script-input'))
                                .map(s => s.value.trim())
                                .filter(s => s !== "");

            if (scripts.length === 0) { showToast('请先输入或生成脚本', 'error'); return; }

            const keys = getKeys();
            if (!keys.llm_key) {
                showApiSettings();
                showToast('请先在 API 设置里填写 AI API 密钥', 'error');
                return;
            }
            persistKeys(keys);
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在分析...';

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        script: scripts[0],
                        api_keys: {
                            llm_key: keys.llm_key || '',
                            llm_url: keys.llm_url || 'https://openrouter.ai/api/v1/chat/completions',
                            llm_model: keys.llm_model || ''
                        }
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    aiTitle.value = data.title;
                    aiDesc.value = data.description;
                    aiHashtags.value = data.hashtags;
                    if (aiThumbPrompt) aiThumbPrompt.value = data.thumbnail_prompt || "";
                    analysisPanel.classList.remove('hidden');
                    showToast('✅ 分析完成', 'success');
                } else {
                    showToast(await readErrorMessage(response, '分析失败'), 'error');
                }
            } catch (error) {
                showToast('网络错误', 'error');
            } finally {
                analyzeBtn.disabled = false;
                analyzeBtn.innerHTML = '<i class="fas fa-brain"></i> AI 标题分析';
            }
        });
    }

    // ═══ MAIN ACTION ═══
    scrapeBtn.addEventListener('click', async () => {
        const query = queryInput ? queryInput.value.trim() : "";

        const scripts = Array.from(document.querySelectorAll('.script-input'))
                            .map(s => s.value.trim())
                            .filter(s => s !== "");

        if (currentMode === 'single' && !query) { showToast('请输入素材搜索词', 'error'); return; }
        if (currentMode === 'script' && scripts.length === 0) { showToast('请至少输入一个脚本', 'error'); return; }

        const source = document.querySelector('input[name="source"]:checked').value;
        const mediaType = document.querySelector('input[name="media_type"]:checked').value;
        const vibe = document.querySelector('input[name="vibe"]:checked').value;
        const count = parseInt(countInput.value);

        const ratio = document.querySelector('input[name="ratio"]:checked').value;
        const language = document.getElementById('language-select').value;
        const voice = document.getElementById('voice-select').value;
        const music = document.getElementById('music-select').value;
        const filter = document.getElementById('filter-select').value;
        const subtitleStyle = document.getElementById('subtitle-style').value;
        const subtitles = document.querySelector('input[name="subtitles"]:checked').value === 'true';
        const autoVideo = document.querySelector('input[name="auto_video"]:checked').value === 'true';
        const ytUpload = document.querySelector('input[name="yt_upload"]:checked').value === 'true';
        const emojiSubtitles = document.querySelector('input[name="emoji_subtitles"]:checked').value === 'true';
        const watermark = document.querySelector('input[name="watermark"]:checked').value === 'true';

        // Get saved API keys
        const keys = getKeys();

        const allowedMusic = new Set(['none', 'cinematic.mp3']);
        if (!allowedMusic.has(music)) {
            showToast('背景音乐选项无效，请重新选择', 'error');
            return;
        }

        if (source === 'ai' && mediaType !== 'photo') {
            showToast('AI 生图模式当前只支持图片素材；如需视频素材，请切换到素材来源', 'error');
            return;
        }

        if (autoVideo && voice === 'none') {
            showToast('自动合成视频需要选择一个 AI 配音；如需不配音，请先关闭自动合成视频', 'error');
            return;
        }

        if (autoVideo && currentMode === 'single' && source !== 'ai') {
            showToast('单条素材搜索不会自动合成视频；请切换到脚本模式，或关闭自动合成视频', 'error');
            return;
        }

        if (source === 'ai' && (!keys.llm_key || !keys.seedream_key)) {
            showApiSettings();
            const missing = [];
            if (!keys.llm_key) missing.push('AI 文本密钥');
            if (!keys.seedream_key) missing.push('Seedream 生图密钥');
            showToast(`请先填写 ${missing.join(' 和 ')}，才能使用 Seedream AI 生图`, 'error');
            return;
        }

        if (currentMode === 'script' && source !== 'ai' && !keys.llm_key) {
            showApiSettings();
            showToast('脚本模式使用素材来源需要先填写 AI 文本密钥，用于分镜关键词分析', 'error');
            return;
        }

        setLoading(true);
        finalVideoUrl = '';
        pollConnectionErrorShown = false;
        galleryContainer.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>VUZA 正在处理，请稍等...</p></div>';

        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query,
                    script: scripts[0],
                    scripts: scripts, // Send all for batch mode
                    source,
                    media_type: mediaType, count,
                    mode: currentMode, vibe,
                    video_settings: {
                        ratio, voice, subtitles, language,
                        subtitle_style: subtitleStyle, music, filter,
                        emoji_subtitles: emojiSubtitles,
                        watermark: watermark
                    },
                    auto_video: autoVideo,
                    yt_upload: ytUpload,
                    api_keys: {
                        llm_key: keys.llm_key || '',
                        llm_url: keys.llm_url || 'https://openrouter.ai/api/v1/chat/completions',
                        llm_model: keys.llm_model || '',
                        seedream_key: keys.seedream_key || '',
                        seedream_url: keys.seedream_url || 'https://ark.cn-beijing.volces.com/api/v3/images/generations',
                        seedream_model: keys.seedream_model || 'doubao-seedream-4-5-251128',
                        pexels_key: keys.pexels_key || '',
                        pixabay_key: keys.pixabay_key || '',
                        yt_client_id: keys.yt_client_id || '',
                yt_client_secret: keys.yt_client_secret || '',
                eleven_key: keys.eleven_key || ''
                    }
                })
            });

            if (response.ok) {
                showToast('🚀 已开始生成', 'success');
                startPollingStatus();
            } else {
                showToast(await readErrorMessage(response, '启动失败'), 'error');
                setLoading(false);
            }
        } catch (error) {
            showToast('网络错误', 'error');
            setLoading(false);
        }
    });

    function startPollingStatus() {
        statusCard.classList.remove('hidden');
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/status');
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const status = await response.json();
                renderStatus(status);
                if (status.final_video) {
                    finalVideoUrl = status.final_video;
                }
                if ((status.results && status.results.length > 0) || finalVideoUrl) updateGallery(status.results || []);
                if (!status.is_running) {
                    clearInterval(statusInterval);
                    statusInterval = null;
                    setLoading(false);
                    if (isFailureStatus(status)) {
                        showToast(status.error || status.message || '生成失败', 'error');
                    } else {
                        showToast('✅ 已完成', 'success');
                    }
                }
            } catch (err) {
                clearInterval(statusInterval);
                statusInterval = null;
                setLoading(false);
                showServiceConnectionError();
            }
        }, 2000);
    }

    async function resumeCurrentJob() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const status = await response.json();

            if (status.final_video) {
                finalVideoUrl = status.final_video;
            }

            if (status.results && status.results.length > 0) {
                updateGallery(status.results);
            } else if (finalVideoUrl) {
                updateGallery([]);
            }

            if (status.is_running || normalizeProgress(status.progress) > 0 || (status.results && status.results.length > 0)) {
                statusCard.classList.remove('hidden');
                renderStatus(status);
            }

            if (status.is_running) {
                setLoading(true);
                startPollingStatus();
            } else {
                setLoading(false);
            }
        } catch (err) {
            showServiceConnectionError();
        }
    }

    function updateGallery(results) {
        galleryContainer.innerHTML = '';
        renderFinalVideoCard();
        results.forEach(res => {
            const block = document.createElement('div');
            block.className = 'keyword-block';
            let html = `<h3>🔑 ${res.keyword}</h3>`;
            if (res.sentence) html += `<span class="sentence-text">"${res.sentence}"</span>`;
            html += `<div class="gallery-grid">`;
            (res.files || []).forEach(file => {
                const isVideo = /\.(mp4|mov|webm)$/i.test(file);
                if (isVideo) {
                    html += `<div class="media-card"><video src="${file}" preload="metadata" loop muted onmouseover="this.play()" onmouseout="this.pause()"></video><div class="media-actions"><a href="${file}" download class="icon-btn"><i class="fas fa-download"></i></a><span class="badge">视频</span></div></div>`;
                } else {
                    html += `<div class="media-card"><img src="${file}" loading="lazy"><div class="media-actions"><a href="${file}" download class="icon-btn"><i class="fas fa-download"></i></a><span class="badge">高清</span></div></div>`;
                }
            });
            html += `</div>`;
            block.innerHTML = html;
            galleryContainer.appendChild(block);
        });
    }

    function renderFinalVideoCard() {
        if (!finalVideoUrl) return;
        const card = document.createElement('div');
        card.className = 'final-video-card';
        card.innerHTML = `
            <div class="final-video-copy">
                <span class="final-video-kicker"><i class="fas fa-check-circle"></i> 成片已生成</span>
                <strong>下载最终视频</strong>
            </div>
            <a class="final-video-btn" href="${finalVideoUrl}" download>
                <i class="fas fa-download"></i> 下载最终视频
            </a>
        `;
        galleryContainer.appendChild(card);
    }

    clearBtn.addEventListener('click', () => {
        finalVideoUrl = '';
        galleryContainer.innerHTML = '<div class="empty-state"><i class="fas fa-cloud-download-alt"></i><p>已清空。</p></div>';
        statusCard.classList.add('hidden');
    });

    function updatePrimaryButtonText() {
        const btnText = scrapeBtn.querySelector('.btn-text');
        if (!btnText) return;

        const source = document.querySelector('input[name="source"]:checked')?.value;
        const autoVideo = document.querySelector('input[name="auto_video"]:checked')?.value === 'true';

        if (currentMode === 'script') {
            btnText.textContent = autoVideo ? '脚本到视频' : '按脚本生成素材';
        } else if (source === 'ai' && autoVideo) {
            btnText.textContent = '主题到视频';
        } else if (source === 'ai') {
            btnText.textContent = 'AI 生成素材';
        } else {
            btnText.textContent = '开始搜素材';
        }
    }

    function isFailureStatus(status) {
        const message = status?.message || '';
        return status?.status === 'error' || Boolean(status?.error) || message.trim().startsWith('❌');
    }

    function normalizeProgress(value) {
        const progress = Number(value);
        if (!Number.isFinite(progress)) return 0;
        return Math.min(100, Math.max(0, Math.round(progress)));
    }

    function renderStatus(status) {
        const progress = normalizeProgress(status.progress);
        const failed = isFailureStatus(status);
        statusMsg.textContent = status.error || status.message || (failed ? '生成失败' : '处理中...');
        statusCard.classList.toggle('status-error', failed);
        statusPercent.textContent = `${progress}%`;
        progressFill.style.width = `${progress}%`;
    }

    function showServiceConnectionError() {
        statusCard.classList.remove('hidden');
        statusCard.classList.add('status-error');
        statusMsg.textContent = '服务连接错误，请确认后端服务仍在运行';
        statusPercent.textContent = '0%';
        progressFill.style.width = '0%';
        if (!pollConnectionErrorShown) {
            showToast('服务连接错误，请稍后重试', 'error');
            pollConnectionErrorShown = true;
        }
    }

    function setLoading(loading) {
        scrapeBtn.disabled = loading;
        const btnText = scrapeBtn.querySelector('.btn-text');
        const btnLoader = scrapeBtn.querySelector('.btn-loader');
        const btnIcon = scrapeBtn.querySelector('.fa-rocket');
        if (loading) {
            btnText.textContent = '处理中...';
            if (btnLoader) btnLoader.classList.remove('hidden');
            if (btnIcon) btnIcon.classList.add('hidden');
        } else {
            updatePrimaryButtonText();
            if (btnLoader) btnLoader.classList.add('hidden');
            if (btnIcon) btnIcon.classList.remove('hidden');
        }
    }

    function showToast(message, type = 'success') {
        const toast = document.getElementById('toast');
        if (!toast) return;
        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3500);
    }
});
