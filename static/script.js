console.log("🚀 VUZA v4 — Video Utility for Zero-cost Automation");

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
            pexels_key: document.getElementById('pexels-key').value.trim(),
            pixabay_key: document.getElementById('pixabay-key').value.trim(),
            yt_client_id: document.getElementById('yt-client-id').value.trim(),
            yt_client_secret: document.getElementById('yt-client-secret').value.trim(),
            eleven_key: document.getElementById('eleven-key').value.trim()
        };
        localStorage.setItem('vuza_api_keys', JSON.stringify(keys));
        showToast('✅ Settings saved!', 'success');
    }

    function getKeys() {
        return JSON.parse(localStorage.getItem('vuza_api_keys') || '{}');
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
            scrapeBtn.querySelector('.btn-text').textContent = 'Start Scraping';
        } else {
            tabSingle.classList.remove('active');
            tabScript.classList.add('active');
            singleArea.classList.add('hidden');
            scriptArea.classList.remove('hidden');
            scrapeBtn.querySelector('.btn-text').textContent = 'Analyze & Extract';
        }
    }

    tabSingle.addEventListener('click', () => switchMode('single'));
    tabScript.addEventListener('click', () => switchMode('script'));

    // ═══ BATCH SCRIPTS ═══
    if (addScriptBtn) {
        addScriptBtn.addEventListener('click', () => {
            const div = document.createElement('div');
            div.className = 'script-item';
            div.innerHTML = `<textarea class="script-input" placeholder="Paste another script here..."></textarea><button type="button" class="remove-script-btn">×</button>`;
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

            if (template === 'motivational') {
                firstScript.value = "Success is not final, failure is not fatal: it is the courage to continue that counts.\nBelieve in yourself and all that you are.\nYour only limit is your mind.";
                document.getElementById('vibe-aesthetic').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'educational') {
                firstScript.value = "Did you know that honey never spoils? Archaeologists have found pots of honey in ancient Egyptian tombs that are over three thousand years old and still perfectly edible.\nThis is because honey is naturally acidic and low in moisture, making it an inhospitable environment for bacteria.";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-16-9').checked = true;
            } else if (template === 'storytelling') {
                firstScript.value = "Once upon a time in a forgotten library, books whispered secrets to those who listened closely.\nOne day, a young girl found a golden key hidden between the pages of an ancient atlas.\nLittle did she know, this key opened a door to another world.";
                document.getElementById('vibe-aesthetic').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'lofi_vibes') {
                firstScript.value = "Late night rain against the window.\nA warm cup of coffee and a good book.\nThe city lights blur in the distance.\nPeace and quiet finally found.";
                document.getElementById('vibe-lofi').checked = true;
                document.getElementById('ratio-9-16').checked = true;
            } else if (template === 'news') {
                firstScript.value = "BREAKING NEWS: Scientists have discovered a new planet that could potentially support life.\nLocated just 20 light-years away, this Earth-like planet orbits a red dwarf star.\nFurther investigations are underway to detect signs of water and atmosphere.";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-16-9').checked = true;
                document.getElementById('subtitle-style').value = 'yellow_box';
            } else if (template === 'tutorial') {
                firstScript.value = "How to make the perfect cup of coffee in 3 simple steps.\nStep 1: Grind your fresh beans to a medium-fine consistency.\nStep 2: Heat your water to exactly 95 degrees Celsius.\nStep 3: Pour slowly in a circular motion and enjoy the aroma.";
                document.getElementById('vibe-general').checked = true;
                document.getElementById('ratio-9-16').checked = true;
                document.getElementById('subtitle-style').value = 'bold_outline';
            }
            if (template) showToast(`✅ ${template} template loaded!`, 'success');
        });
    }

    // ═══ DYNAMIC VOICES ═══
    const languageSelect = document.getElementById('language-select');
    const voiceSelect = document.getElementById('voice-select');

    const voiceMap = {
        'en-US': [
            { name: '🎙️ Christopher (Free)', value: 'en-US-ChristopherNeural' },
            { name: '🎤 Jenny (Free)', value: 'en-US-JennyNeural' },
            { name: '🌟 Adam (ElevenLabs)', value: 'eleven_pNInz6obpg8ndclQU7Nc' },
            { name: '🌟 Antoni (ElevenLabs)', value: 'eleven_ErXwBPLxhSj618Y4yxKI' },
            { name: '🌟 Bella (ElevenLabs)', value: 'eleven_EXAVITQu4vr4xnSDxMaL' }
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
            { name: '🇨🇳 Yunyang', value: 'zh-CN-YunyangNeural' },
            { name: '🇨🇳 Xiaoxiao', value: 'zh-CN-XiaoxiaoNeural' }
        ],
        'ja-JP': [
            { name: '🇯🇵 Keita', value: 'ja-JP-KeitaNeural' },
            { name: '🇯🇵 Nanami', value: 'ja-JP-NanamiNeural' }
        ]
    };

    function updateVoices() {
        const lang = languageSelect.value;
        const voices = voiceMap[lang] || [];
        voiceSelect.innerHTML = voices.map(v => `<option value="${v.value}">${v.name}</option>`).join('') + '<option value="none">🔇 No Voice</option>';
    }

    if (languageSelect) {
        languageSelect.addEventListener('change', updateVoices);
        updateVoices(); // Initial load
    }

    // ═══ URL SCRAPER ACTION ═══
    if (scrapeUrlBtn) {
        scrapeUrlBtn.addEventListener('click', async () => {
            const url = urlInput.value.trim();
            if (!url) { showToast('Paste a URL first!', 'error'); return; }

            const keys = getKeys();
            scrapeUrlBtn.disabled = true;
            scrapeUrlBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scraping...';

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
                        showToast('✅ URL scraped & summarized!', 'success');
                    }
                } else {
                    const err = await response.json();
                    showToast(err.detail || 'Scrape failed', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                scrapeUrlBtn.disabled = false;
                scrapeUrlBtn.innerHTML = '<i class="fas fa-file-download"></i> Extract Script';
            }
        });
    }

    // ═══ AI SCRIPT GENERATOR ACTION ═══
    if (generateScriptBtn) {
        generateScriptBtn.addEventListener('click', async () => {
            const topic = topicInput.value.trim();
            if (!topic) { showToast('Enter a topic first!', 'error'); return; }

            const keys = getKeys();
            const vibe = document.querySelector('input[name="vibe"]:checked').value;

            generateScriptBtn.disabled = true;
            generateScriptBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';

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
                        showToast('✅ Script generated successfully!', 'success');
                    }
                } else {
                    const err = await response.json();
                    showToast(err.detail || 'Generation failed', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                generateScriptBtn.disabled = false;
                generateScriptBtn.innerHTML = '<i class="fas fa-magic"></i> Generate Script';
            }
        });
    }

    // ═══ AI ANALYSIS ACTION ═══
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async () => {
            const scripts = Array.from(document.querySelectorAll('.script-input'))
                                .map(s => s.value.trim())
                                .filter(s => s !== "");

            if (scripts.length === 0) { showToast('Paste a script first!', 'error'); return; }

            const keys = getKeys();
            analyzeBtn.disabled = true;
            analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

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
                    showToast('✅ Analysis complete!', 'success');
                } else {
                    const err = await response.json();
                    showToast(err.detail || 'Analysis failed', 'error');
                }
            } catch (error) {
                showToast('Network error', 'error');
            } finally {
                analyzeBtn.disabled = false;
                analyzeBtn.innerHTML = '<i class="fas fa-brain"></i> AI YouTube Analyzer';
            }
        });
    }

    // ═══ MAIN ACTION ═══
    scrapeBtn.addEventListener('click', async () => {
        const query = queryInput ? queryInput.value.trim() : "";

        const scripts = Array.from(document.querySelectorAll('.script-input'))
                            .map(s => s.value.trim())
                            .filter(s => s !== "");

        if (currentMode === 'single' && !query) { showToast('Enter a search query!', 'error'); return; }
        if (currentMode === 'script' && scripts.length === 0) { showToast('Paste at least one script!', 'error'); return; }

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

        setLoading(true);
        galleryContainer.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>VUZA is processing your request...</p></div>';

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
                        pexels_key: keys.pexels_key || '',
                        pixabay_key: keys.pixabay_key || '',
                        yt_client_id: keys.yt_client_id || '',
                yt_client_secret: keys.yt_client_secret || '',
                eleven_key: keys.eleven_key || ''
                    }
                })
            });

            if (response.ok) {
                showToast('🚀 VUZA started!', 'success');
                startPollingStatus();
            } else {
                const err = await response.json();
                showToast(err.message || 'Failed', 'error');
                setLoading(false);
            }
        } catch (error) {
            showToast('Network error', 'error');
            setLoading(false);
        }
    });

    function startPollingStatus() {
        statusCard.classList.remove('hidden');
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/status');
                const status = await response.json();
                statusMsg.textContent = status.message;
                statusPercent.textContent = status.progress + '%';
                progressFill.style.width = status.progress + '%';
                if (status.results && status.results.length > 0) updateGallery(status.results);
                if (!status.is_running) {
                    clearInterval(statusInterval);
                    setLoading(false);
                    showToast('✅ Done!', 'success');
                }
            } catch (err) { }
        }, 2000);
    }

    function updateGallery(results) {
        galleryContainer.innerHTML = '';
        results.forEach(res => {
            const block = document.createElement('div');
            block.className = 'keyword-block';
            let html = `<h3>🔑 ${res.keyword}</h3>`;
            if (res.sentence) html += `<span class="sentence-text">"${res.sentence}"</span>`;
            html += `<div class="gallery-grid">`;
            (res.files || []).forEach(file => {
                const isVideo = /\.(mp4|mov|webm)$/i.test(file);
                if (isVideo) {
                    html += `<div class="media-card"><video src="${file}" preload="metadata" loop muted onmouseover="this.play()" onmouseout="this.pause()"></video><div class="media-actions"><a href="${file}" download class="icon-btn"><i class="fas fa-download"></i></a><span class="badge">VIDEO</span></div></div>`;
                } else {
                    html += `<div class="media-card"><img src="${file}" loading="lazy"><div class="media-actions"><a href="${file}" download class="icon-btn"><i class="fas fa-download"></i></a><span class="badge">HD</span></div></div>`;
                }
            });
            html += `</div>`;
            block.innerHTML = html;
            galleryContainer.appendChild(block);
        });
    }

    clearBtn.addEventListener('click', () => {
        galleryContainer.innerHTML = '<div class="empty-state"><i class="fas fa-cloud-download-alt"></i><p>Gallery cleared.</p></div>';
        statusCard.classList.add('hidden');
    });

    function setLoading(loading) {
        scrapeBtn.disabled = loading;
        const btnText = scrapeBtn.querySelector('.btn-text');
        const btnLoader = scrapeBtn.querySelector('.btn-loader');
        const btnIcon = scrapeBtn.querySelector('.fa-rocket');
        if (loading) {
            btnText.textContent = 'Processing...';
            if (btnLoader) btnLoader.classList.remove('hidden');
            if (btnIcon) btnIcon.classList.add('hidden');
        } else {
            btnText.textContent = currentMode === 'single' ? 'Start Scraping' : 'Analyze & Extract';
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
