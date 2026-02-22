const POLL_INTERVAL = 15000;

function barColor(pct) {
    if (pct >= 90) return 'var(--red)';
    if (pct >= 70) return 'var(--orange)';
    if (pct >= 40) return 'var(--yellow)';
    return 'var(--green)';
}

function renderGpuBars(gpus) {
    if (!gpus || gpus.length === 0) return '<p class="muted">No GPU data</p>';
    return gpus.map(g => `
        <div style="margin-bottom:6px">
            <small>GPU ${g.index} (${g.name}): ${g.utilization_pct}% | ${g.memory_used_mb}/${g.memory_total_mb}MB | ${g.temperature_c}°C</small>
            <div class="bar-container">
                <div class="bar" style="width:${g.utilization_pct}%;background:${barColor(g.utilization_pct)}">${g.utilization_pct}%</div>
            </div>
        </div>
    `).join('');
}

function renderJobs(jobs) {
    if (!jobs || jobs.length === 0) return '<p class="muted">No running jobs</p>';
    return `<p>${jobs.length} job(s) running</p>` +
        jobs.map(j => `<div class="cmd" style="font-size:0.7rem;margin-top:2px">${j.command.substring(0, 80)}...</div>`).join('');
}

function renderSys(s) {
    const parts = [];
    if (s.cpu_percent != null) parts.push(`CPU: ${s.cpu_percent}%`);
    if (s.memory_used_mb != null) parts.push(`RAM: ${s.memory_used_mb}/${s.memory_total_mb}MB`);
    if (s.uptime) parts.push(s.uptime);
    return parts.length ? `<small class="muted">${parts.join(' | ')}</small>` : '';
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
            if (jobEl) jobEl.innerHTML = renderJobs(s.running_jobs);

            const sysEl = document.getElementById(`sys-${name}`);
            if (sysEl) sysEl.innerHTML = renderSys(s);
        }

        const onlineEl = document.getElementById('online-count');
        if (onlineEl) onlineEl.textContent = `Online: ${onlineCount}`;
        const gpuEl = document.getElementById('total-gpus');
        if (gpuEl) gpuEl.textContent = `GPUs: ${totalGpus}`;
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
    pollStatuses();
    setInterval(pollStatuses, POLL_INTERVAL);
}
