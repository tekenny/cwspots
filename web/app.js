'use strict';

const MAX_SPOTS = 200;
const AGE_TICK  = 10000;

function getWsUrl() {
    if (window.location.protocol === 'https:') {
        return `wss://${window.location.host}/ws`;
    }
    return `ws://${window.location.hostname}:8081`;
}

let ws      = null;
let spots   = new Map(); // key: `${dx}|${band_m}` — one row per DX station per band
let filters = loadFilters();
let kiwis = loadKiwis();              // [{name, url}, ...]
let activeKiwiUrl = localStorage.getItem('active_kiwi_url') || '';
let lastMsgTime   = Date.now();
let kiwiMode      = localStorage.getItem('kiwiMode') || 'static';
let skccShow      = localStorage.getItem('skccShow') === 'true';
let skccMembers   = null;

function connect() {
    ws = new WebSocket(getWsUrl());
    ws.onopen = () => {
        lastMsgTime = Date.now();
        setStatus('connected', '⬤ Connected');
        sendFilters();
    };
    ws.onmessage = (e) => {
        lastMsgTime = Date.now();
        try {
            const msg = JSON.parse(e.data);
            if (msg.type === 'spot') addSpot(msg.data);
        } catch (_) {}
    };
    ws.onclose = () => {
        setStatus('error', '⬤ Disconnected — retrying...');
        setTimeout(connect, 3000);
    };
    ws.onerror = () => { ws.close(); };
}

function sendFilters() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'filter', filters }));
    }
}

function addSpot(data) {
    const key  = `${data.dx}|${data.band_m}`;
    const list = document.getElementById('spot-list');

    if (list.firstChild && list.firstChild.classList &&
        list.firstChild.classList.contains('empty-state')) {
        list.innerHTML = '';
    }

    // If this DX+band is already displayed, remove the old row first
    const existing = spots.get(key);
    if (existing) existing.el.remove();

    const el = buildRow(data);
    el.dataset.spotKey = key;
    list.insertBefore(el, list.firstChild);
    spots.set(key, { data, el });

    // Trim oldest (last child) if over limit
    while (spots.size > MAX_SPOTS) {
        const lastEl = list.lastChild;
        if (!lastEl || !lastEl.dataset || !lastEl.dataset.spotKey) break;
        spots.delete(lastEl.dataset.spotKey);
        lastEl.remove();
    }

    updateCount();
    updateBandSummary();
}

function resolveKiwiUrl(d) {
    if (kiwiMode === 'dynamic' && kiwiDirectory) {
        const s = nearestKiwi(d.spotter_lat, d.spotter_lon);
        return s ? s.url : '';
    }
    return activeKiwiUrl || '';
}

function buildRow(d) {
    const cont  = d.dx_continent || '';
    const kiwi  = resolveKiwiUrl(d);
    const freq  = parseFloat(d.freq_khz).toFixed(1);
    const href  = kiwi ? `${kiwi}/?f=${freq}cw` : '#';
    const age   = formatAge(d.timestamp);

    const a = document.createElement('a');
    a.className          = 'spot-row spot-new';
    a.href               = href;
    a.target             = '_blank';
    a.rel                = 'noopener noreferrer';
    a.dataset.timestamp  = d.timestamp;
    a.dataset.freq       = freq;
    if (!kiwi) a.onclick = (e) => { e.preventDefault(); promptKiwi(); };

    const skccMember = skccShow ? skccLookup(d.dx) : null;
    const skccBadge  = skccMember ? `<span class="skcc-badge">${esc(skccMember.nr)}</span>` : '';
    a.innerHTML = `
        <span class="spot-dx">
            ${esc(d.dx)}
            ${cont ? `<span class="cont-badge cont-${cont}">${cont}</span>` : ''}${skccBadge}
        </span>
        <span class="spot-detail">
            <span class="spot-freq">${freq} kHz</span>
            <span class="spot-entity">${esc(d.dx_entity || '')} · via ${esc(d.spotter)}(${d.spotter_continent || '??'})</span>
        </span>
        <span class="spot-band">${d.band_m}m</span>
        <span class="spot-wpm">${d.wpm} wpm</span>
        <span class="spot-snr">${d.snr_db} dB</span>
        <span class="spot-age" data-ts="${d.timestamp}">${age}</span>
    `;
    return a;
}

function updateAges() {
    document.querySelectorAll('.spot-age[data-ts]').forEach(el => {
        el.textContent = formatAge(parseFloat(el.dataset.ts));
    });
}

function formatAge(ts) {
    const s = Math.floor(Date.now() / 1000 - ts);
    if (s <  60)   return `${s}s`;
    if (s < 3600)  return `${Math.floor(s / 60)}m`;
    return `${Math.floor(s / 3600)}h`;
}

function updateCount() {
    document.getElementById('spot-count').textContent =
        `${spots.size} spot${spots.size !== 1 ? 's' : ''}`;
}

const BAND_ORDER = [160, 80, 60, 40, 30, 20, 17, 15, 12, 10, 6, 2];

function updateBandSummary() {
    const counts = {};
    spots.forEach(({ data }) => {
        if (data.band_m) counts[data.band_m] = (counts[data.band_m] || 0) + 1;
    });
    const el = document.getElementById('band-summary');
    const active = BAND_ORDER.filter(b => counts[b]);
    if (active.length === 0) { el.innerHTML = ''; return; }
    el.innerHTML = active.map(b =>
        `<span class="band-badge">${b}m <span class="band-count">${counts[b]}</span></span>`
    ).join('');
}

function cancelFilters() {
    loadFilterUI();
    document.getElementById('filter-panel').classList.add('hidden');
}

function toggleFilters() {
    const panel = document.getElementById('filter-panel');
    panel.classList.toggle('hidden');
    if (!panel.classList.contains('hidden')) loadFilterUI();
}

function loadFilterUI() {
    // Restore numeric inputs
    document.getElementById('wpm-min').value  = filters.wpm_min !== undefined ? filters.wpm_min : 0;
    document.getElementById('wpm-max').value  = filters.wpm_max !== undefined ? filters.wpm_max : 20;
    document.getElementById('snr-min').value  = filters.snr_min !== undefined ? filters.snr_min : 0;
    renderKiwis();

    // Chips: fall back to all active if filter not set
    // Band values stored as numbers in filters, chip data-values are strings — compare as strings
    const beaconVal = filters.beacon || 'both';
    document.querySelectorAll('.seg[data-group="beacon"]').forEach(b => {
        b.classList.toggle('active', b.dataset.value === beaconVal);
    });
    document.querySelectorAll('.seg[data-group="kiwimode"]').forEach(b => {
        b.classList.toggle('active', b.dataset.value === kiwiMode);
    });
    document.querySelectorAll('.seg[data-group="skcc"]').forEach(b => {
        b.classList.toggle('active', b.dataset.value === (skccShow ? 'show' : 'hide'));
    });

    const activeDx   = (filters.continents_dx   && filters.continents_dx.length)   ? filters.continents_dx                : allContinents();
    const activeSp   = (filters.continents_spotter && filters.continents_spotter.length) ? filters.continents_spotter     : allContinents();
    const activeBand = (filters.bands            && filters.bands.length)           ? filters.bands.map(String)           : allBands().map(String);
    const activeMode = (filters.modes            && filters.modes.length)           ? filters.modes                       : ['CW','RTTY','FT8'];

    setChips('dx',   activeDx);
    setChips('sp',   activeSp);
    setChips('band', activeBand);
    setChips('mode', activeMode);
}

function setChips(group, activeValues) {
    document.querySelectorAll(`.chip[data-group="${group}"]`).forEach(btn => {
        btn.classList.toggle('active', activeValues.includes(btn.dataset.value));
    });
}

function getChips(group) {
    return [...document.querySelectorAll(`.chip[data-group="${group}"].active`)]
        .map(b => b.dataset.value);
}

function applyFilters() {
    const wpmMin  = parseInt(document.getElementById('wpm-min').value, 10) || 0;
    const wpmMaxR = parseInt(document.getElementById('wpm-max').value, 10);
    const wpmMax  = Number.isFinite(wpmMaxR) ? wpmMaxR : 20;
    const snrMin  = parseInt(document.getElementById('snr-min').value, 10) || 0;

    const beacon   = document.querySelector('.seg[data-group="beacon"].active')?.dataset.value || 'both';
    const newKiwiMode = document.querySelector('.seg[data-group="kiwimode"].active')?.dataset.value || 'static';
    kiwiMode = newKiwiMode;
    localStorage.setItem('kiwiMode', kiwiMode);
    if (kiwiMode === 'dynamic' && kiwiDirectory === null) loadKiwiDirectory();
    skccShow = document.querySelector('.seg[data-group="skcc"].active')?.dataset.value === 'show';
    localStorage.setItem('skccShow', skccShow);
    if (skccShow && skccMembers === null) loadSkccMembers();
    const dxConts = getChips('dx');
    const spConts = getChips('sp');
    const bands   = getChips('band').map(Number);
    const modes   = getChips('mode');

    filters = {
        wpm_min:            wpmMin,
        wpm_max:            wpmMax,
        snr_min:            snrMin,
        continents_dx:      dxConts.length < 7  ? dxConts : [],
        continents_spotter: spConts.length < 7  ? spConts : [],
        bands:              bands.length   < 11 ? bands   : [],
        modes:              modes.length   < 3  ? modes   : [],
        beacon,
    };

    localStorage.setItem('cwspots_filters', JSON.stringify(filters));

    clearSpots();
    sendFilters();
    toggleFilters();
}

function clearSpots() {
    spots = new Map();
    document.getElementById('spot-list').innerHTML =
        '<div class="empty-state">Waiting for spots...<br>Filters applied.</div>';
    updateCount();
    updateBandSummary();
}

function loadFilters() {
    try {
        const saved = localStorage.getItem('cwspots_filters');
        return saved ? JSON.parse(saved) : {};
    } catch (e) { return {}; }
}

function loadKiwis() {
    try {
        const saved = localStorage.getItem('kiwis');
        return saved ? JSON.parse(saved) : [];
    } catch (e) { return []; }
}

function saveKiwis() {
    localStorage.setItem('kiwis', JSON.stringify(kiwis));
}

function addKiwi() {
    const nameEl = document.getElementById('kiwi-name');
    const urlEl  = document.getElementById('kiwi-url-input');
    const name = nameEl.value.trim();
    let url    = urlEl.value.trim().replace(/\/$/, '');
    if (!name || !url) { alert('Enter both name and URL'); return; }
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'http://' + url;
    }
    kiwis.push({ name, url });
    saveKiwis();
    if (!activeKiwiUrl) {
        activeKiwiUrl = url;
        localStorage.setItem('active_kiwi_url', activeKiwiUrl);
    }
    nameEl.value = '';
    urlEl.value = '';
    renderKiwis();
    rebuildRows();
}

function removeKiwi(url) {
    if (!confirm('Remove this Kiwi?')) return;
    kiwis = kiwis.filter(k => k.url !== url);
    saveKiwis();
    if (activeKiwiUrl === url) {
        activeKiwiUrl = kiwis.length ? kiwis[0].url : '';
        localStorage.setItem('active_kiwi_url', activeKiwiUrl);
    }
    renderKiwis();
    rebuildRows();
}

function selectKiwi(url) {
    activeKiwiUrl = url;
    localStorage.setItem('active_kiwi_url', activeKiwiUrl);
    renderKiwis();
    rebuildRows();
}

function renderKiwis() {
    const list = document.getElementById('kiwi-list');
    if (!list) return;
    if (kiwis.length === 0) {
        list.innerHTML = '<div class="kiwi-empty">No KiwiSDRs added yet</div>';
        return;
    }
    list.innerHTML = kiwis.map((k, i) => `
        <div class="kiwi-item ${k.url === activeKiwiUrl ? 'active-kiwi' : ''}"
             data-idx="${i}">
            <div class="kiwi-info">
                <span class="kiwi-name">${esc(k.name)}</span>
                <span class="kiwi-url">${esc(k.url)}</span>
            </div>
            <span class="kiwi-active-badge">ACTIVE</span>
            <button class="kiwi-remove" data-idx="${i}">×</button>
        </div>
    `).join('');
    list.querySelectorAll('.kiwi-item').forEach(el => {
        const idx = parseInt(el.dataset.idx, 10);
        el.addEventListener('click', () => selectKiwi(kiwis[idx].url));
        el.querySelector('.kiwi-remove').addEventListener('click', e => {
            e.stopPropagation();
            removeKiwi(kiwis[idx].url);
        });
    });
}

let kiwiDirectory = null;

function haversine(lat1, lon1, lat2, lon2) {
    const R    = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a    = Math.sin(dLat / 2) ** 2 +
                 Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                 Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function nearestKiwi(spotterLat, spotterLon) {
    if (!kiwiDirectory || !kiwiDirectory.length) return null;
    if (spotterLat == null || spotterLon == null) return null;
    let best = null, bestDist = Infinity;
    // Prefer stations that aren't full
    for (const s of kiwiDirectory) {
        if (s.lat == null || s.lon == null) continue;
        if (s.users >= s.users_max) continue;
        const d = haversine(spotterLat, spotterLon, s.lat, s.lon);
        if (d < bestDist) { bestDist = d; best = s; }
    }
    if (best) return best;
    // Fallback: allow full stations
    bestDist = Infinity;
    for (const s of kiwiDirectory) {
        if (s.lat == null || s.lon == null) continue;
        const d = haversine(spotterLat, spotterLon, s.lat, s.lon);
        if (d < bestDist) { bestDist = d; best = s; }
    }
    return best;
}

function toggleKiwiBrowse() {
    const panel = document.getElementById('kiwi-browse-panel');
    const opening = panel.classList.contains('hidden');
    panel.classList.toggle('hidden');
    if (opening) {
        document.getElementById('kiwi-search').value = '';
        if (kiwiDirectory === null) {
            loadKiwiDirectory();
        } else {
            filterKiwiBrowse();
        }
        document.getElementById('kiwi-search').focus();
    }
}

async function loadKiwiDirectory() {
    const list = document.getElementById('kiwi-browse-list');
    list.innerHTML = '<div class="kiwi-empty">Loading...</div>';
    try {
        const resp = await fetch('kiwi_stations.json');
        if (!resp.ok) throw new Error(resp.status);
        kiwiDirectory = await resp.json();
        filterKiwiBrowse();
    } catch (e) {
        list.innerHTML = '<div class="kiwi-empty">Failed to load station list.</div>';
    }
}

async function loadSkccMembers() {
    try {
        const resp = await fetch('skcc_members.json');
        if (!resp.ok) throw new Error(resp.status);
        skccMembers = await resp.json();
        rebuildRows();
    } catch (e) {
        console.warn('Failed to load SKCC members:', e);
    }
}

function skccLookup(dx) {
    if (!skccMembers) return null;
    const parts = dx.toUpperCase().split('/');
    return skccMembers[parts[0]] || (parts[1] ? skccMembers[parts[1]] : null) || null;
}

function filterKiwiBrowse() {
    const query = (document.getElementById('kiwi-search').value || '').trim().toLowerCase();
    const list  = document.getElementById('kiwi-browse-list');
    if (!kiwiDirectory) return;

    if (!query) {
        list.innerHTML = `<div class="kiwi-empty">Type to search ${kiwiDirectory.length} stations.</div>`;
        return;
    }

    const filtered = kiwiDirectory.filter(s => s.name.toLowerCase().includes(query));
    if (filtered.length === 0) {
        list.innerHTML = '<div class="kiwi-empty">No stations match.</div>';
        return;
    }

    const shown = filtered.slice(0, 50);
    list.innerHTML = shown.map((s, i) => `
        <div class="kiwi-dir-item" data-i="${i}">
            <span class="kiwi-dir-name">${esc(s.name)}</span>
            <span class="kiwi-dir-users${s.users >= s.users_max ? ' kiwi-full' : ''}">${s.users}/${s.users_max}</span>
        </div>
    `).join('');
    if (filtered.length > 50) {
        list.insertAdjacentHTML('beforeend',
            `<div class="kiwi-empty">+${filtered.length - 50} more — refine search.</div>`);
    }
    list.querySelectorAll('.kiwi-dir-item').forEach(el => {
        const s = shown[parseInt(el.dataset.i, 10)];
        el.addEventListener('click', () => selectKiwiFromDirectory(s));
    });
}

function selectKiwiFromDirectory(s) {
    if (!kiwis.find(k => k.url === s.url)) {
        kiwis.push({ name: s.name, url: s.url });
        saveKiwis();
    }
    activeKiwiUrl = s.url;
    localStorage.setItem('active_kiwi_url', activeKiwiUrl);
    renderKiwis();
    rebuildRows();
    document.getElementById('kiwi-browse-panel').classList.add('hidden');
}

function promptKiwi() {
    alert('Add a KiwiSDR in the filter panel under "KiwiSDR Receivers"');
}

function rebuildRows() {
    spots.forEach(({ data, el }) => {
        const freq  = parseFloat(data.freq_khz).toFixed(1);
        const kiwi  = resolveKiwiUrl(data);
        el.href     = kiwi ? `${kiwi}/?f=${freq}cw` : '#';
        if (!kiwi) el.onclick = (e) => { e.preventDefault(); promptKiwi(); };
        else el.onclick = null;
        const dxSpan = el.querySelector('.spot-dx');
        if (dxSpan) {
            const cont       = data.dx_continent || '';
            const member     = skccShow ? skccLookup(data.dx) : null;
            const skccBadge  = member ? `<span class="skcc-badge">${esc(member.nr)}</span>` : '';
            dxSpan.innerHTML = `${esc(data.dx)}${cont ? `<span class="cont-badge cont-${cont}">${cont}</span>` : ''}${skccBadge}`;
        }
    });
}

function setStatus(state, text) {
    const el = document.getElementById('status');
    el.textContent = text;
    el.className   = `status-${state}`;
}

function toggleTheme() {
    const light = document.body.classList.toggle('light');
    localStorage.setItem('theme', light ? 'light' : 'dark');
    document.getElementById('theme-btn').textContent = light ? '☾' : '☀';
}

function allContinents() { return ['NA','SA','EU','AF','AS','OC','AN']; }
function allBands()      { return [160,80,60,40,30,20,17,15,12,10,6]; }

function esc(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// Chip toggle (multi-select)
document.querySelectorAll('.chip').forEach(btn => {
    btn.addEventListener('click', () => btn.classList.toggle('active'));
});

// Seg toggle (single-select per group)
document.querySelectorAll('.seg').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll(`.seg[data-group="${btn.dataset.group}"]`)
            .forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

// Init
document.getElementById('spot-list').innerHTML =
    '<div class="empty-state">Connecting to CW Spotter...<br>Spots will appear here.</div>';

// Keepalive: ping every 45s; reconnect if silent for 3 minutes (handles iOS sleep)
setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (Date.now() - lastMsgTime > 180000) {
        ws.close();
    } else {
        try { ws.send(JSON.stringify({ type: 'ping' })); } catch (_) {}
    }
}, 45000);

if (localStorage.getItem('theme') === 'light') {
    document.body.classList.add('light');
    document.getElementById('theme-btn').textContent = '☾';
}

renderKiwis();
if (kiwiMode === 'dynamic') loadKiwiDirectory();
if (skccShow) loadSkccMembers();
setInterval(updateAges, AGE_TICK);
connect();
