document.addEventListener('DOMContentLoaded', () => {
    const scanBtn = document.getElementById('scanBtn');
    const dirInput = document.getElementById('dirInput');
    const scanStatus = document.getElementById('scanStatus');
    const trackList = document.getElementById('trackList');
    const trackCount = document.getElementById('trackCount');
    const automixBtn = document.getElementById('automixBtn');
    const crossfadeBtn = document.getElementById('crossfadeBtn');
    const stopBtn = document.getElementById('stopBtn');
    const selectAll = document.getElementById('selectAll');
    const queuePanel = document.getElementById('queuePanel');
    const queueList = document.getElementById('queueList');
    
    // Player Bar
    const playPauseBtn = document.getElementById('playPauseBtn');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const rewindBtn = document.getElementById('rewindBtn');
    const forwardBtn = document.getElementById('forwardBtn');
    const seekSlider = document.getElementById('seekSlider');
    const currentTimeEl = document.getElementById('currentTime');
    const totalTimeEl = document.getElementById('totalTime');
    const npTitle = document.getElementById('npTitle');
    const npArtist = document.getElementById('npArtist');

    let allTracks = [];
    let isDragging = false;

    // Fetch tracks on load
    fetchTracks();

    async function fetchTracks() {
        try {
            const res = await fetch('/api/tracks');
            allTracks = await res.json();
            renderTracks(allTracks);
            trackCount.textContent = allTracks.length;
        } catch (e) {
            console.error(e);
        }
    }

    function formatTime(ms) {
        if (!ms) return "0:00";
        const totalSeconds = Math.floor(ms / 1000);
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    function renderTracks(tracks) {
        trackList.innerHTML = '';
        tracks.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><input type="checkbox" class="track-select" value="${t.id}"></td>
                <td style="font-weight: 600;">${t.title || 'Unknown'}</td>
                <td style="color: var(--text-muted);">${t.artist || 'Unknown'}</td>
                <td><span class="badge">${formatTime(t.duration_ms)}</span></td>
            `;
            trackList.appendChild(tr);
        });

        // Add listeners to checkboxes
        document.querySelectorAll('.track-select').forEach(cb => {
            cb.addEventListener('change', updateAutomixBtn);
        });
    }

    function updateAutomixBtn() {
        const checked = document.querySelectorAll('.track-select:checked');
        automixBtn.disabled = checked.length === 0;
        automixBtn.textContent = checked.length > 0 ? `Generate Automix (${checked.length} tracks)` : 'Generate Automix';
    }

    selectAll.addEventListener('change', (e) => {
        document.querySelectorAll('.track-select').forEach(cb => {
            cb.checked = e.target.checked;
        });
        updateAutomixBtn();
    });

    scanBtn.addEventListener('click', async () => {
        const dir = dirInput.value.trim();
        if(!dir) return;
        
        scanBtn.disabled = true;
        scanBtn.textContent = "Scanning...";
        scanStatus.textContent = "Extracting ID3 and querying Spotify API... This may take a moment.";
        
        try {
            const res = await fetch('/api/scan_directory', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({directory: dir})
            });
            const data = await res.json();
            scanStatus.textContent = data.message || data.error;
            fetchTracks();
        } catch(e) {
            scanStatus.textContent = "Error scanning directory.";
        }
        
        scanBtn.disabled = false;
        scanBtn.textContent = "Scan Directory";
    });

    automixBtn.addEventListener('click', async () => {
        const checked = Array.from(document.querySelectorAll('.track-select:checked')).map(cb => parseInt(cb.value));
        if (checked.length === 0) return;

        automixBtn.disabled = true;
        automixBtn.textContent = "Mixing...";

        try {
            const res = await fetch('/api/automix', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({track_ids: checked})
            });
            const data = await res.json();
            
            if (data.playlist) {
                renderQueue(data.playlist);
            }
        } catch (e) {
            console.error(e);
        }

        automixBtn.textContent = "Playing Automix";
    });

    function renderQueue(playlist) {
        queuePanel.style.display = 'block';
        queueList.innerHTML = '';
        playlist.forEach((t, i) => {
            const div = document.createElement('div');
            div.className = 'queue-item';
            div.innerHTML = `
                <div><strong>${i+1}. ${t.title}</strong> - <span style="color: var(--text-muted);">${t.artist}</span></div>
                <div style="display:flex; gap: 8px;">
                    <span class="badge">${t.bpm.toFixed(1)} BPM</span>
                    <span class="badge key">${t.camelot}</span>
                </div>
            `;
            queueList.appendChild(div);
        });
    }

    crossfadeBtn.addEventListener('click', async () => {
        await fetch('/api/crossfade', {method: 'POST'});
    });

    stopBtn.addEventListener('click', async () => {
        await fetch('/api/stop', {method: 'POST'});
        automixBtn.disabled = false;
        automixBtn.textContent = "Generate Automix";
        queuePanel.style.display = 'none';
        document.querySelectorAll('.track-select:checked').forEach(cb => cb.checked = false);
        selectAll.checked = false;
        updateAutomixBtn();
    });

    // -----------------------------------------
    // Player Bar Logic
    // -----------------------------------------
    
    // Poll state every 500ms
    setInterval(async () => {
        try {
            const res = await fetch('/api/state');
            const state = await res.json();
            
            // Update Text
            npTitle.textContent = state.title || "--";
            npArtist.textContent = state.artist || "--";
            playPauseBtn.textContent = state.is_paused ? "▶" : "⏸";
            
            if (state.duration > 0) {
                totalTimeEl.textContent = formatTime(state.duration * 1000);
                if (!isDragging) {
                    currentTimeEl.textContent = formatTime(state.position * 1000);
                    seekSlider.max = state.duration;
                    seekSlider.value = state.position;
                }
            } else {
                seekSlider.value = 0;
                currentTimeEl.textContent = "0:00";
                totalTimeEl.textContent = "0:00";
            }
        } catch (e) {
            // console.error("Error polling state", e);
        }
    }, 500);

    // Play/Pause Button
    playPauseBtn.addEventListener('click', async () => {
        await fetch('/api/pause', {method: 'POST'});
    });

    // Spacebar Play/Pause
    document.addEventListener('keydown', async (e) => {
        // Prevent spacebar from scrolling or triggering inputs if we aren't in an input
        if (e.code === 'Space' && document.activeElement.tagName !== 'INPUT') {
            e.preventDefault();
            await fetch('/api/pause', {method: 'POST'});
        }
    });

    // Transport Buttons
    nextBtn.addEventListener('click', async () => {
        await fetch('/api/next', {method: 'POST'});
    });
    
    prevBtn.addEventListener('click', async () => {
        await fetch('/api/prev', {method: 'POST'});
    });

    forwardBtn.addEventListener('click', async () => {
        const currentPos = parseFloat(seekSlider.value);
        const maxPos = parseFloat(seekSlider.max);
        const newPos = Math.min(currentPos + 5, maxPos);
        await fetch('/api/seek', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({position_sec: newPos})
        });
    });

    rewindBtn.addEventListener('click', async () => {
        const currentPos = parseFloat(seekSlider.value);
        const newPos = Math.max(currentPos - 5, 0);
        await fetch('/api/seek', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({position_sec: newPos})
        });
    });

    // Seek Slider
    seekSlider.addEventListener('mousedown', () => { isDragging = true; });
    seekSlider.addEventListener('input', () => {
        currentTimeEl.textContent = formatTime(seekSlider.value * 1000);
    });
    seekSlider.addEventListener('change', async () => {
        const val = parseFloat(seekSlider.value);
        await fetch('/api/seek', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({position_sec: val})
        });
        isDragging = false;
    });
});
