const form = document.getElementById('allocationForm');
const processList = document.getElementById('processList');
const allocationHistory = document.getElementById('allocationHistory');
const memoryBlocks = document.getElementById('memoryBlocks');
const utilization = document.getElementById('utilization');
const utilizationBar = document.getElementById('utilizationBar');
const allocatedDisplay = document.getElementById('allocated');
const fragmentationDisplay = document.getElementById('fragmentation');
const processCount = document.getElementById('processCount');
const notification = document.getElementById('notification');
const notificationMessage = document.getElementById('notificationMessage');

const TOTAL_MEMORY = 1024;

function showNotification(message, success = true) {
    notificationMessage.innerText = message;
    notification.className = 'notification' + (success ? '' : ' error');
    notification.classList.remove('hidden');
    setTimeout(() => notification.classList.add('hidden'), 2500);
}

async function fetchStatus() {
    const res = await fetch('/api/memory/status');
    const data = await res.json();
    updateUI(data);
}

form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const pid = document.getElementById('processId').value.trim();
    const pname = document.getElementById('processName').value.trim();
    const size = parseInt(document.getElementById('memorySize').value);
    const strategy = document.getElementById('strategy').value;
    if (!pid || !pname || !size || size < 1 || size > TOTAL_MEMORY) {
        showNotification('Invalid input', false);
        return;
    }
    const res = await fetch('/api/memory/allocate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ process_id: pid, process_name: pname, size, strategy })
    });
    const data = await res.json();
    showNotification(data.message, data.success);
    fetchStatus();
    form.reset();
});

async function deallocate(pid) {
    const res = await fetch('/api/memory/deallocate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ process_id: pid })
    });
    const data = await res.json();
    showNotification(data.message, data.success);
    fetchStatus();
}

document.getElementById('resetBtn').addEventListener('click', async () => {
    const res = await fetch('/api/memory/reset', { method: 'POST' });
    const data = await res.json();
    showNotification(data.message, data.success);
    fetchStatus();
});

function updateUI(data) {
    // Memory blocks visual
    memoryBlocks.innerHTML = '';
    let totalAllocated = 0;
    if (data.blocks && data.blocks.length) {
        data.blocks.forEach(block => {
            const div = document.createElement('div');
            div.className = 'memory-block' + (block.allocated ? ' allocated' : ' free');
            div.style.flex = block.size / TOTAL_MEMORY;
            div.innerText = block.allocated ? block.process_id : '';
            memoryBlocks.appendChild(div);
            if (block.allocated) totalAllocated += block.size;
        });
    }
    // Stats
    utilization.innerText = data.stats ? `${data.stats.utilization_percentage.toFixed(1)}%` : '0%';
    utilizationBar.style.width = data.stats ? `${data.stats.utilization_percentage.toFixed(1)}%` : '0%';
    allocatedDisplay.innerText = `${totalAllocated}B`;
    fragmentationDisplay.innerText = data.stats ? `${data.stats.fragmentation_percentage.toFixed(1)}%` : '0%';
    // Process list
    processList.innerHTML = '';
    if (data.processes && data.processes.length) {
        data.processes.forEach(proc => {
            const item = document.createElement('div');
            item.className = 'process-item';
            item.innerHTML = `
                <strong>${proc.id}</strong> - ${proc.name} | ${proc.size}B | ${proc.status}
                ${proc.status === 'allocated' ? `<button onclick="deallocate('${proc.id}')">❌ Deallocate</button>` : ''}
            `;
            processList.appendChild(item);
        });
        processCount.innerText = `${data.processes.length} processes`;
    } else {
        processList.innerHTML = '<div class="empty-state"><div class="empty-icon">🖥️</div><p>No processes created yet</p><small>Use the allocation form to create your first process</small></div>';
        processCount.innerText = '0 processes';
    }
    // History
    allocationHistory.innerHTML = '';
    if (data.history && data.history.length) {
        data.history.forEach(hist => {
            const item = document.createElement('div');
            item.className = 'history-item';
            item.innerText = `${hist.timestamp}: ${hist.action} ${hist.size || ''}B ${hist.process_id ? 'for ' + hist.process_id : ''} ${hist.strategy ? '(' + hist.strategy + ')' : ''}`;
            allocationHistory.appendChild(item);
        });
    } else {
        allocationHistory.innerHTML = '<div class="empty-state"><div class="empty-icon">🕒</div><p>No allocation history yet</p><small>Memory operations will appear here</small></div>';
    }
}

// Initial load
fetchStatus();
