/**
 * Star Command — Game frontend
 * AJAX game loop, DOM updates, LCARS map renderer.
 */

// ── State ──────────────────────────────────────
let isProcessing = false;
let currentMapData = null;  // ultimo galaxy_state ricevuto
let currentShipPos = null;  // [q_row, q_col, s_row, s_col]
let currentContext = 'NAVIGATION';

// ── Quick Action Buttons (per context) ─────────
// { label, cmd, cat, prompt? }
// cmd = comando da inviare direttamente, prompt = chiede input extra
const QUICK_ACTIONS = {
    COMBAT: [
        { label: 'Faser',          cmd: null,              cat: 'combat',  prompt: 'Energia faser:', prefix: 'spara faser ' },
        { label: 'Siluro',         cmd: 'spara siluro',    cat: 'combat' },
        { label: 'Scudi MAX',      cmd: 'scudi max',       cat: 'combat' },
        { label: 'Scudi %',        cmd: null,              cat: 'combat',  prompt: 'Livello scudi %:', prefix: 'scudi ' },
        { label: 'Rapp. Tattico',  cmd: 'rapporto tattico', cat: 'officer' },
        { label: 'Stato',          cmd: 'stato nave',      cat: 'info' },
        { label: 'Sistemi',        cmd: 'sistemi',         cat: 'info' },
    ],
    NAVIGATION: [
        { label: 'Warp',           cmd: null,              cat: 'nav',     prompt: 'Velocita warp (1-9):', prefix: 'warp ' },
        { label: 'Impulso',        cmd: null,              cat: 'nav',     prompt: 'Settore (riga col):', prefix: 'impulso ' },
        { label: 'Scan',           cmd: 'scan',            cat: 'nav' },
        { label: 'Mappa',          cmd: 'mappa',           cat: 'info' },
        { label: 'Stato',          cmd: 'stato nave',      cat: 'info' },
        { label: 'Rapp. Scientifico', cmd: 'rapporto scientifico', cat: 'officer' },
        { label: 'Rapp. Ingegnere', cmd: 'rapporto ingegnere', cat: 'officer' },
    ],
    DOCKED: [
        { label: 'Ripara',         cmd: null,              cat: 'system',  prompt: 'Sistema da riparare:', prefix: 'ripara ' },
        { label: 'Rapp. Ingegnere', cmd: 'rapporto ingegnere', cat: 'officer' },
        { label: 'Rapp. Medico',   cmd: 'rapporto medico', cat: 'officer' },
        { label: 'Stato',          cmd: 'stato nave',      cat: 'info' },
        { label: 'Sistemi',        cmd: 'sistemi',         cat: 'info' },
        { label: 'Warp',           cmd: null,              cat: 'nav',     prompt: 'Velocita warp (1-9):', prefix: 'warp ' },
        { label: 'Missione',       cmd: 'missione',        cat: 'info' },
    ],
    EXPLORATION: [
        { label: 'Scan',           cmd: 'scan',            cat: 'nav' },
        { label: 'Rapp. Scientifico', cmd: 'rapporto scientifico', cat: 'officer' },
        { label: 'Impulso',        cmd: null,              cat: 'nav',     prompt: 'Settore (riga col):', prefix: 'impulso ' },
        { label: 'Mappa',          cmd: 'mappa',           cat: 'info' },
        { label: 'Stato',          cmd: 'stato nave',      cat: 'info' },
    ],
    DIPLOMACY: [
        { label: 'Rapp. Tattico',  cmd: 'rapporto tattico', cat: 'officer' },
        { label: 'Rapp. Scientifico', cmd: 'rapporto scientifico', cat: 'officer' },
        { label: 'Riunione',       cmd: 'riunione equipaggio', cat: 'officer' },
        { label: 'Missione',       cmd: 'missione',        cat: 'info' },
    ],
};

// Pulsanti universali (sempre visibili)
const UNIVERSAL_ACTIONS = [
    { label: 'Diario',     cmd: 'diario',          cat: 'info' },
    { label: 'Missione',   cmd: 'missione',        cat: 'info' },
    { label: 'Mappa',      cmd: 'mappa',           cat: 'info' },
    { label: 'Salva+Esci', cmd: 'salva e esci',    cat: 'system' },
    { label: '? Help',     cmd: null,               cat: 'help',  action: 'help' },
];

const $ = id => document.getElementById(id);
const commandInput = $('command-input');
const sendBtn = $('send-btn');
const spinner = $('spinner');

// ── Init ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Carica stato iniziale dal setup
    const saved = sessionStorage.getItem('initialState');
    if (saved) {
        sessionStorage.removeItem('initialState');
        const data = JSON.parse(saved);
        processResponse(data);

        // Mostra briefing se presente
        const briefing = (data.output || []).find(m => m.type === 'mission_briefing');
        if (!briefing && data.mission) {
            showBriefing(data.mission);
        }
    }

    commandInput.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !isProcessing) sendCommand();
    });

    // Escape chiude overlay aperti
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') {
            closeHelp();
            closeMap();
            closeSystems();
        }
    });

    // Render pulsanti iniziali
    renderActionButtons('NAVIGATION');

    commandInput.focus();
});

// ── Command ────────────────────────────────────
async function sendCommand() {
    const cmd = commandInput.value.trim();
    if (!cmd || isProcessing) return;

    commandInput.value = '';
    appendNarrative(`> ${cmd}`, 'dim');
    setProcessing(true);

    try {
        const resp = await fetch('/api/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd }),
        });
        const data = await resp.json();
        processResponse(data);
    } catch (e) {
        appendNarrative(`Errore di comunicazione: ${e.message}`, 'red');
    } finally {
        setProcessing(false);
        commandInput.focus();
    }
}

async function sendConfirm(answer) {
    $('confirm-overlay').classList.remove('active');
    setProcessing(true);

    try {
        const resp = await fetch('/api/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirm: answer }),
        });
        const data = await resp.json();
        processResponse(data);
    } catch (e) {
        appendNarrative(`Errore: ${e.message}`, 'red');
    } finally {
        setProcessing(false);
        commandInput.focus();
    }
}

// ── Response processing ────────────────────────
function processResponse(data) {
    if (data.error && !data.bridge_state) {
        appendNarrative(data.error, 'red');
        return;
    }

    // Update HUD
    if (data.bridge_state) {
        updateBridge(data.bridge_state);
    }

    // Process output buffer
    const output = data.output || [];
    for (const msg of output) {
        switch (msg.type) {
            case 'officer_message':
                showOfficerMessage(msg);
                break;
            case 'narrative':
                appendNarrative(msg.text, msg.color);
                break;
            case 'narrative_long':
                appendNarrative(`── ${msg.title} ──`, 'cyan');
                appendNarrative(msg.text, 'white');
                break;
            case 'map_overlay':
                currentMapData = msg.galaxy;
                currentShipPos = msg.ship_position;
                showMap(msg.galaxy, msg.ship_position);
                break;
            case 'systems_overlay':
                showSystems(msg.systems, msg.repair_queue);
                break;
            case 'captain_log_overlay':
                showCaptainLog(msg.entries);
                break;
            case 'contextual_menu':
                showMenu(msg.context);
                break;
            case 'confirm_request':
                showConfirm(msg.message);
                return;  // Don't re-enable input
            case 'mission_briefing':
                showBriefing(msg.mission);
                break;
            case 'game_over':
                showGameOver(msg.reason, msg.victory);
                return;
            case 'resupply':
                appendNarrative('── RIFORNIMENTO ──', 'green');
                msg.messages.forEach(m => appendNarrative(m, 'green'));
                break;
        }
    }

    // Check end
    if (data.end_reason && data.end_reason !== 'QUIT') {
        showGameOver(data.end_reason, false);
    }
}

// ── Bridge HUD update ──────────────────────────
function updateBridge(state) {
    const ship = state.ship;
    if (!ship) return;

    $('ship-name').textContent = `${ship.name} (${ship.ship_class})`;
    $('stardate').textContent = `SD ${state.stardate.toFixed(2)}`;
    $('turn-display').textContent = `T${state.turn_number || 0}`;

    // Context badge
    const ctx = state.context || 'NAVIGATION';
    const badge = $('context-badge');
    badge.textContent = ctx;
    badge.className = `context-badge ${ctx}`;

    // Update action buttons if context changed
    if (ctx !== currentContext) {
        currentContext = ctx;
        renderActionButtons(ctx);
    }

    // Bars
    updateBar('hull', ship.hull_pct, 100);
    updateBar('shields', ship.shields_pct, 150);
    updateBar('energy', ship.energy, ship.energy_max);
    updateBar('morale', ship.morale_pct, 100);

    $('energy-val').textContent = `${Math.round(ship.energy)}/${Math.round(ship.energy_max)}`;
    $('torpedoes-val').textContent = `${ship.torpedoes}/${ship.torpedoes_max}`;
    $('dilithium-val').textContent = `${ship.dilithium}/${ship.dilithium_max}`;
    $('crew-val').textContent = `${ship.crew}/${ship.crew_max}`;
    $('position-val').textContent = `Q(${ship.position[0]},${ship.position[1]}) S(${ship.position[2]},${ship.position[3]})`;

    // Mission
    if (state.mission_nome) {
        $('mission-val').textContent = `${state.mission_nome} — ${state.mission_obiettivo || ''} (deadline SD ${state.deadline_stardate || '?'})`;
    }

    // Enemies
    const enemies = state.enemies || [];
    const enemyRow = $('enemies-row');
    if (enemies.length > 0) {
        enemyRow.style.display = 'flex';
        const types = enemies.map(e => e.enemy_type || '?').join(', ');
        $('enemies-val').textContent = `${types} (${enemies.length})`;
    } else {
        enemyRow.style.display = 'none';
    }

    // Store position for map
    currentShipPos = ship.position;
}

function updateBar(name, value, max) {
    const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
    const bar = $(`${name}-bar`);
    const label = $(`${name}-pct`);
    if (bar) {
        bar.style.width = pct + '%';
        if (pct > 50) bar.style.background = name === 'shields' ? 'var(--bar-cyan)' : name === 'energy' ? 'var(--bar-blue)' : 'var(--bar-green)';
        else if (pct > 20) bar.style.background = 'var(--bar-yellow)';
        else bar.style.background = 'var(--bar-red)';
    }
    if (label) label.textContent = Math.round(pct) + '%';
}

// ── Officer messages ───────────────────────────
function showOfficerMessage(msg) {
    const panel = $('officers-panel');
    const div = document.createElement('div');
    div.className = `officer-msg ${msg.role}`;
    div.innerHTML = `
        <div class="officer-name ${msg.role}">${msg.officer_name} [${msg.role.toUpperCase()}]</div>
        <div>${msg.message}</div>
        <div class="officer-trust">Trust: ${Math.round(msg.trust)}%</div>
    `;
    panel.appendChild(div);
    panel.scrollTop = panel.scrollHeight;

    // Keep max 10 messages
    while (panel.children.length > 11) panel.removeChild(panel.children[1]);
}

// ── Narrative log ──────────────────────────────
function appendNarrative(text, color) {
    const log = $('narrative-log');
    const div = document.createElement('div');
    div.className = `narr-entry ${color || 'white'}`;
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;

    // Keep max 100 entries
    while (log.children.length > 100) log.removeChild(log.firstChild);
}

// ── Galaxy Map ─────────────────────────────────
function showMap(galaxyState, shipPos) {
    $('hud-view').style.display = 'none';
    $('systems-view').classList.remove('active');
    $('map-view').classList.add('active');

    const qRow = shipPos[0], qCol = shipPos[1];
    const sRow = shipPos[2], sCol = shipPos[3];
    const quadrants = galaxyState.quadrants;

    // ── Quadrant overview ──
    const galGrid = $('galaxy-grid');
    galGrid.innerHTML = '';
    galGrid.appendChild(makeGridHeader(''));
    for (let c = 1; c <= 8; c++) galGrid.appendChild(makeGridHeader(c));

    for (let r = 0; r < 8; r++) {
        galGrid.appendChild(makeGridHeader(r + 1));
        for (let c = 0; c < 8; c++) {
            const qData = quadrants[r][c];
            const vis = qData.visibility || 'UNKNOWN';
            const isCurrent = (r + 1 === qRow && c + 1 === qCol);

            const cell = document.createElement('div');
            cell.className = 'galaxy-cell';
            if (isCurrent) cell.classList.add('current');
            if (vis === 'UNKNOWN') cell.classList.add('unknown');
            else cell.classList.add('scanned');

            if (vis === 'UNKNOWN') {
                cell.textContent = '???';
            } else {
                cell.innerHTML = quadrantSummary(qData);
            }

            cell.onclick = () => renderSectors(quadrants[r][c], r + 1, c + 1, shipPos);
            galGrid.appendChild(cell);
        }
    }

    // ── Sector detail (current quadrant) ──
    renderSectors(quadrants[qRow - 1][qCol - 1], qRow, qCol, shipPos);
}

function renderSectors(qData, qr, qc, shipPos) {
    $('sector-title').textContent = `QUADRANTE (${qr},${qc}) — SETTORI`;
    const secGrid = $('sector-grid');
    secGrid.innerHTML = '';

    secGrid.appendChild(makeGridHeader(''));
    for (let c = 1; c <= 8; c++) secGrid.appendChild(makeGridHeader(c));

    const sectors = qData.sectors || [];
    for (let r = 0; r < 8; r++) {
        secGrid.appendChild(makeGridHeader(r + 1));
        for (let c = 0; c < 8; c++) {
            const val = sectors[r] ? sectors[r][c] : '\u00b7';
            const isShip = (qr === shipPos[0] && qc === shipPos[1] && r + 1 === shipPos[2] && c + 1 === shipPos[3]);

            const cell = document.createElement('div');
            cell.className = 'sector-cell ' + sectorClass(val, isShip);
            cell.textContent = isShip ? 'E' : (val === '\u00b7' ? '\u00b7' : val);
            secGrid.appendChild(cell);
        }
    }
}

function quadrantSummary(qData) {
    const sectors = qData.sectors || [];
    const counts = {};
    for (const row of sectors) {
        for (const cell of row) {
            if (cell !== '\u00b7') counts[cell] = (counts[cell] || 0) + 1;
        }
    }
    const important = ['K', 'R', '!', 'X', 'B', '?'];
    const parts = [];
    for (const sym of important) {
        if (counts[sym]) {
            const cls = sectorClass(sym, false);
            parts.push(`<span class="sector-cell ${cls}" style="display:inline;background:none;min-height:auto;font-size:0.6rem">${sym}${counts[sym]}</span>`);
        }
    }
    return parts.length ? parts.join(' ') : '<span style="color:#333">\u00b7</span>';
}

function sectorClass(val, isShip) {
    if (isShip) return 'ship';
    switch (val) {
        case 'K': case 'R': case '!': case 'X': return 'enemy';
        case '*': return 'star';
        case 'B': return 'base';
        case '?': return 'anomaly';
        case '~': return 'nebula';
        case 'P': return 'planet';
        case 'E': return 'ship';
        default: return 'empty';
    }
}

function makeGridHeader(text) {
    const div = document.createElement('div');
    div.className = 'grid-header';
    div.textContent = text;
    return div;
}

function closeMap() {
    $('map-view').classList.remove('active');
    $('hud-view').style.display = 'flex';
}

// ── Systems overlay ────────────────────────────
function showSystems(systems, repairQueue) {
    $('hud-view').style.display = 'none';
    $('map-view').classList.remove('active');
    const view = $('systems-view');
    view.classList.add('active');

    const list = $('systems-list');
    list.innerHTML = '';

    for (const [name, data] of Object.entries(systems)) {
        const integrity = data.integrity || 0;
        let status, statusColor;
        if (integrity > 50) { status = 'OK'; statusColor = 'var(--bar-green)'; }
        else if (integrity > 19) { status = '!!'; statusColor = 'var(--bar-yellow)'; }
        else if (integrity > 0) { status = 'XX'; statusColor = 'var(--lcars-red)'; }
        else { status = '--'; statusColor = 'var(--lcars-red)'; }

        const penalty = integrity >= 50 ? 0 : Math.pow((50 - integrity) / 50, 1.5);

        const row = document.createElement('div');
        row.className = 'system-row';
        row.innerHTML = `
            <div class="sys-name">${name}</div>
            <div class="bar-gauge"><div class="fill" style="width:${integrity}%;background:${statusColor}"></div><span class="pct">${Math.round(integrity)}%</span></div>
            <div class="sys-status" style="color:${statusColor}">${status}</div>
            <div class="sys-penalty">${penalty > 0 ? penalty.toFixed(2) : '0.00'}</div>
        `;
        list.appendChild(row);
    }
}

function closeSystems() {
    $('systems-view').classList.remove('active');
    $('hud-view').style.display = 'flex';
}

// ── Captain's Log ──────────────────────────────
function showCaptainLog(entries) {
    if (!entries || entries.length === 0) {
        appendNarrative('Nessuna voce nel diario del Capitano.', 'dim');
        return;
    }
    appendNarrative('── DIARIO DEL CAPITANO ──', 'cyan');
    const recent = entries.slice(-10);
    for (const e of recent) {
        const sd = (e.stardate || 0).toFixed(2);
        const tipo = e.tipo || e.type || '?';
        const text = e.testo || e.text || '';
        appendNarrative(`  SD ${sd} [${tipo}] ${text}`, 'cyan');
    }
}

// ── Contextual Menu ────────────────────────────
function showMenu(context) {
    // Menu commands are shown in the narrative area
    appendNarrative(`── COMANDI [${context}] ──`, 'amber');
    // The actual menu items come from the engine via narrative messages
}

// ── Modals ─────────────────────────────────────
function showConfirm(message) {
    $('confirm-msg').textContent = message;
    $('confirm-overlay').classList.add('active');
}

function showBriefing(mission) {
    $('briefing-title').textContent = `BRIEFING: ${mission.nome || 'Missione'}`;
    $('briefing-desc').textContent = mission.descrizione_narrativa || '';
    $('briefing-obj').textContent = `Obiettivo: ${mission.obiettivo_testo || ''}`;
    $('briefing-deadline').textContent = `Deadline: SD ${mission.deadline_stardate || '?'}`;
    $('briefing-overlay').classList.add('active');
}

function closeBriefing() {
    $('briefing-overlay').classList.remove('active');
    commandInput.focus();
}

function showGameOver(reason, victory) {
    const box = $('gameover-box');
    box.className = `gameover-box ${victory ? 'victory' : 'defeat'}`;
    $('gameover-title').textContent = victory ? 'MISSIONE COMPLETATA' : 'MISSIONE FALLITA';
    $('gameover-reason').textContent = reason;
    $('gameover-overlay').classList.add('active');
}

// ── Quick Action Buttons ───────────────────────
function renderActionButtons(context) {
    const bar = $('actions-bar');
    // Mantieni il label
    bar.innerHTML = '<span class="actions-label">Azioni:</span>';

    // Pulsanti specifici per contesto
    const contextActions = QUICK_ACTIONS[context] || QUICK_ACTIONS['NAVIGATION'];
    for (const act of contextActions) {
        bar.appendChild(makeActionBtn(act));
    }

    // Separatore
    const sep = document.createElement('span');
    sep.className = 'actions-sep';
    bar.appendChild(sep);

    // Pulsanti universali (deduplica se gia presenti nel contesto)
    const contextCmds = new Set(contextActions.filter(a => a.cmd).map(a => a.cmd));
    for (const act of UNIVERSAL_ACTIONS) {
        if (act.cmd && contextCmds.has(act.cmd)) continue;
        bar.appendChild(makeActionBtn(act));
    }
}

function makeActionBtn(act) {
    const btn = document.createElement('button');
    btn.className = `action-btn cat-${act.cat}`;
    btn.textContent = act.label;
    btn.disabled = isProcessing;

    btn.onclick = () => {
        if (isProcessing) return;

        // Azione speciale (help)
        if (act.action === 'help') {
            openHelp();
            return;
        }

        // Comando diretto
        if (act.cmd) {
            commandInput.value = act.cmd;
            sendCommand();
            return;
        }

        // Comando con prompt (richiede input)
        if (act.prompt) {
            commandInput.value = act.prefix || '';
            commandInput.focus();
            commandInput.placeholder = act.prompt;
            // Ripristina placeholder dopo blur
            const restore = () => {
                commandInput.placeholder = 'Inserisci comando...';
                commandInput.removeEventListener('blur', restore);
            };
            commandInput.addEventListener('blur', restore);
        }
    };

    // Tooltip
    if (act.prompt) {
        btn.title = act.prompt;
    } else if (act.cmd) {
        btn.title = act.cmd;
    }

    return btn;
}

// ── Help ───────────────────────────────────────
function openHelp() {
    $('help-overlay').classList.add('active');
}

function closeHelp() {
    $('help-overlay').classList.remove('active');
    commandInput.focus();
}

// ── Helpers ────────────────────────────────────
function setProcessing(state) {
    isProcessing = state;
    commandInput.disabled = state;
    sendBtn.disabled = state;
    spinner.classList.toggle('active', state);

    // Disabilita/abilita pulsanti azione
    document.querySelectorAll('.action-btn').forEach(btn => btn.disabled = state);
}
