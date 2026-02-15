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
    const tabSingle = document.getElementById('tab-single');
    const tabScript = document.getElementById('tab-script');
    const singleArea = document.getElementById('single-input-area');
    const scriptArea = document.getElementById('script-input-area');

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
    }

    function saveKeys() {
        const keys = {
            llm_key: document.getElementById('llm-key').value.trim(),
            llm_url: document.getElementById('llm-url').value.trim(),
            llm_model: document.getElementById('llm-model').value.trim(),
            pexels_key: document.getElementById('pexels-key').value.trim(),
            pixabay_key: document.getElementById('pixabay-key').value.trim()
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

    // ═══ MAIN ACTION ═══
    scrapeBtn.addEventListener('click', async () => {
        const query = queryInput ? queryInput.value.trim() : "";
        const script = scriptInput ? scriptInput.value.trim() : "";

        if (currentMode === 'single' && !query) { showToast('Enter a search query!', 'error'); return; }
        if (currentMode === 'script' && !script) { showToast('Paste a script first!', 'error'); return; }

        const source = document.querySelector('input[name="source"]:checked').value;
        const mediaType = document.querySelector('input[name="media_type"]:checked').value;
        const vibe = document.querySelector('input[name="vibe"]:checked').value;
        const count = parseInt(countInput.value);

        const ratio = document.querySelector('input[name="ratio"]:checked').value;
        const voice = document.getElementById('voice-select').value;
        const subtitles = document.querySelector('input[name="subtitles"]:checked').value === 'true';
        const autoVideo = document.querySelector('input[name="auto_video"]:checked').value === 'true';

        // Get saved API keys
        const keys = getKeys();

        setLoading(true);
        galleryContainer.innerHTML = '<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><p>VUZA is processing your request...</p></div>';

        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query, script, source,
                    media_type: mediaType, count,
                    mode: currentMode, vibe,
                    video_settings: { ratio, voice, subtitles },
                    auto_video: autoVideo,
                    api_keys: {
                        llm_key: keys.llm_key || '',
                        llm_url: keys.llm_url || 'https://openrouter.ai/api/v1/chat/completions',
                        llm_model: keys.llm_model || '',
                        pexels_key: keys.pexels_key || '',
                        pixabay_key: keys.pixabay_key || ''
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
