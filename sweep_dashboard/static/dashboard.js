const POLL_INTERVAL = 15000;

function barColor(pct) {
    if (pct >= 90) return 'var(--red)';
    if (pct >= 70) return 'var(--orange)';
    if (pct >= 40) return 'var(--yellow)';
    return 'var(--green)';
}

function formatIdleTime(seconds) {
    if (seconds == null) return '';
    if (seconds < 60) return 'idle <1m';
    if (seconds < 3600) return `idle ${Math.floor(seconds/60)}m`;
    if (seconds < 86400) return `idle ${Math.floor(seconds/3600)}h ${Math.floor((seconds%3600)/60)}m`;
    return `idle ${Math.floor(seconds/86400)}d ${Math.floor((seconds%86400)/3600)}h`;
}

function renderGpuBars(gpus) {
    if (!gpus || gpus.length === 0) return '<p class="muted">No GPU data</p>';
    return gpus.map(g => `
        <div style="margin-bottom:6px">
            <small>GPU ${g.index} (${g.name}): ${g.utilization_pct}% | ${g.memory_used_mb}/${g.memory_total_mb}MB | ${g.temperature_c}°C${g.idle_seconds != null && g.utilization_pct <= 5 ? ' | ' + formatIdleTime(g.idle_seconds) : ''}</small>
            <div class="bar-container">
                <div class="bar" style="width:${g.utilization_pct}%;background:${barColor(g.utilization_pct)}">${g.utilization_pct}%</div>
            </div>
        </div>
    `).join('');
}

function renderJobs(jobs, wandb_url) {
    let html = '';
    if (!jobs || jobs.length === 0) {
        html = '<p class="muted">No running jobs</p>';
    } else {
        html = `<p>${jobs.length} job(s) running</p>` +
            jobs.map(j => `<div class="cmd" style="font-size:0.7rem;margin-top:2px">${j.command.substring(0, 80)}...</div>`).join('');
    }
    if (wandb_url) {
        html += `<a href="${wandb_url}" target="_blank" rel="noopener" style="font-size:0.75rem;color:var(--accent);display:inline-block;margin-top:4px">&#x1f517; WandB Run</a>`;
    }
    return html;
}

function renderSys(s) {
    const parts = [];
    if (s.cpu_percent != null) parts.push(`CPU: ${s.cpu_percent}%`);
    if (s.memory_used_mb != null) parts.push(`RAM: ${s.memory_used_mb}/${s.memory_total_mb}MB`);
    if (s.uptime) parts.push(s.uptime);
    return parts.length ? `<small class="muted">${parts.join(' | ')}</small>` : '';
}

// --- View Toggle (Grid vs List) ---
function setView(mode) {
    const grid = document.getElementById('node-grid');
    const list = document.getElementById('node-list');
    const gridBtn = document.getElementById('grid-view-btn');
    const listBtn = document.getElementById('list-view-btn');
    if (!grid || !list) return;

    if (mode === 'list') {
        grid.style.display = 'none';
        list.style.display = 'block';
        if (gridBtn) gridBtn.classList.remove('active');
        if (listBtn) listBtn.classList.add('active');
    } else {
        grid.style.display = '';
        list.style.display = 'none';
        if (gridBtn) gridBtn.classList.add('active');
        if (listBtn) listBtn.classList.remove('active');
    }
    localStorage.setItem('dashboard-view', mode);
}

function renderListView(statuses) {
    const tbody = document.getElementById('node-list-body');
    if (!tbody) return;

    const rows = [];
    for (const [name, s] of Object.entries(statuses)) {
        const online = s.online ? '<span class="badge badge-online">Online</span>' : '<span class="badge badge-offline">Offline</span>';
        const gpuCount = (s.gpus || []).length;

        // Average GPU utilization
        let avgUtil = '-';
        if (gpuCount > 0) {
            const avg = s.gpus.reduce((sum, g) => sum + g.utilization_pct, 0) / gpuCount;
            avgUtil = `${Math.round(avg)}%`;
        }

        // Total VRAM used/total
        let vram = '-';
        if (gpuCount > 0) {
            const usedMB = s.gpus.reduce((sum, g) => sum + g.memory_used_mb, 0);
            const totalMB = s.gpus.reduce((sum, g) => sum + g.memory_total_mb, 0);
            vram = `${usedMB}/${totalMB}MB`;
        }

        const jobCount = (s.running_jobs || []).length;
        const cpu = s.cpu_percent != null ? `${s.cpu_percent}%` : '-';
        const ram = s.memory_used_mb != null ? `${s.memory_used_mb}/${s.memory_total_mb}MB` : '-';

        let wandb = '-';
        if (s.wandb_url) {
            wandb = `<a href="${s.wandb_url}" target="_blank" rel="noopener" style="color:var(--accent);font-size:0.8rem">&#x1f517; Link</a>`;
        }

        const actions = `
            <a href="/node/${name}" class="btn btn-sm">Details</a>
            <a href="/terminal/${name}" class="btn btn-sm">Terminal</a>
        `;

        rows.push(`<tr>
            <td><strong>${name}</strong></td>
            <td>${online}</td>
            <td>${gpuCount}</td>
            <td>${avgUtil}</td>
            <td>${vram}</td>
            <td>${jobCount > 0 ? jobCount + ' running' : '-'}</td>
            <td>${cpu}</td>
            <td>${ram}</td>
            <td>${wandb}</td>
            <td>${actions}</td>
        </tr>`);
    }
    tbody.innerHTML = rows.join('');
}

async function pollStatuses() {
    try {
        const resp = await fetch('/api/statuses');
        if (!resp.ok) return;
        const statuses = await resp.json();

        let onlineCount = 0;
        let totalGpus = 0;

        for (const [name, s] of Object.entries(statuses)) {
            const badge = document.getElementById(`badge-${name}`);
            if (badge) {
                badge.textContent = s.online ? 'Online' : 'Offline';
                badge.className = `badge ${s.online ? 'badge-online' : 'badge-offline'}`;
            }
            if (s.online) onlineCount++;
            totalGpus += (s.gpus || []).length;

            const gpuEl = document.getElementById(`gpus-${name}`);
            if (gpuEl) gpuEl.innerHTML = renderGpuBars(s.gpus);

            const jobEl = document.getElementById(`jobs-${name}`);
            if (jobEl) jobEl.innerHTML = renderJobs(s.running_jobs, s.wandb_url);

            const sysEl = document.getElementById(`sys-${name}`);
            if (sysEl) sysEl.innerHTML = renderSys(s);
        }

        const onlineEl = document.getElementById('online-count');
        if (onlineEl) onlineEl.textContent = `Online: ${onlineCount}`;
        const gpuEl = document.getElementById('total-gpus');
        if (gpuEl) gpuEl.textContent = `GPUs: ${totalGpus}`;

        renderListView(statuses);
    } catch (e) {
        console.error('Poll error:', e);
    }
}

async function refreshAll() {
    const btn = document.getElementById('refresh-all-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Refreshing...'; }
    try {
        await fetch('/api/poll-all', { method: 'POST' });
        await pollStatuses();
    } catch (e) {
        console.error('Refresh all error:', e);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Refresh All'; }
    }
}

async function forcePoll(nodeName) {
    try {
        await fetch(`/api/poll/${nodeName}`, { method: 'POST' });
        await pollStatuses();
    } catch (e) {
        console.error('Force poll error:', e);
    }
}

if (document.getElementById('node-grid')) {
    // Restore view preference
    const savedView = localStorage.getItem('dashboard-view');
    if (savedView === 'list') setView('list');

    pollStatuses();
    setInterval(pollStatuses, POLL_INTERVAL);
}

// --- Drag and Drop for Node Cards ---
function initDragAndDrop() {
    const grid = document.getElementById('node-grid');
    if (!grid) return;

    // Restore saved order
    const savedOrder = localStorage.getItem('node-card-order');
    if (savedOrder) {
        try {
            const order = JSON.parse(savedOrder);
            order.forEach(name => {
                const card = document.getElementById(`card-${name}`);
                if (card) grid.appendChild(card);
            });
        } catch (e) { /* ignore bad data */ }
    }

    let draggedCard = null;

    grid.addEventListener('dragstart', (e) => {
        const card = e.target.closest('.node-card');
        if (!card) return;
        draggedCard = card;
        card.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', card.dataset.node);
    });

    grid.addEventListener('dragend', (e) => {
        if (draggedCard) {
            draggedCard.classList.remove('dragging');
            draggedCard = null;
        }
        grid.querySelectorAll('.node-card').forEach(c => c.classList.remove('drag-over'));
    });

    grid.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const target = e.target.closest('.node-card');
        if (!target || target === draggedCard) return;

        // Clear all drag-over highlights
        grid.querySelectorAll('.node-card').forEach(c => c.classList.remove('drag-over'));
        target.classList.add('drag-over');
    });

    grid.addEventListener('dragleave', (e) => {
        const target = e.target.closest('.node-card');
        if (target) target.classList.remove('drag-over');
    });

    grid.addEventListener('drop', (e) => {
        e.preventDefault();
        const target = e.target.closest('.node-card');
        if (!target || !draggedCard || target === draggedCard) return;

        // Determine if we should insert before or after
        const targetRect = target.getBoundingClientRect();
        const midY = targetRect.top + targetRect.height / 2;
        if (e.clientY < midY) {
            grid.insertBefore(draggedCard, target);
        } else {
            grid.insertBefore(draggedCard, target.nextSibling);
        }

        // Save order
        const cards = grid.querySelectorAll('.node-card');
        const order = Array.from(cards).map(c => c.dataset.node);
        localStorage.setItem('node-card-order', JSON.stringify(order));

        grid.querySelectorAll('.node-card').forEach(c => c.classList.remove('drag-over'));
    });
}

// Initialize drag and drop
initDragAndDrop();
