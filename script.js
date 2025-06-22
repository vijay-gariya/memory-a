const form = document.getElementById('allocationForm');
const processList = document.getElementById('processList');
const allocationHistory = document.getElementById('allocationHistory');
const memoryBlocks = document.getElementById('memoryBlocks');
const utilization = document.getElementById('utilization');
const utilizationBar = document.getElementById('utilizationBar');
const allocatedDisplay = document.getElementById('allocated');
const fragmentationDisplay = document.getElementById('fragmentation');
const processCount = document.getElementById('processCount');

const TOTAL_MEMORY = 1024;
let usedMemory = 0;
let processCounter = 0;
let processes = [];

form.addEventListener('submit', function (e) {
    e.preventDefault();

    const pid = document.getElementById('processId').value;
    const pname = document.getElementById('processName').value;
    const size = parseInt(document.getElementById('memorySize').value);
    const strategy = document.getElementById('strategy').value;

    if (usedMemory + size > TOTAL_MEMORY) {
        alert('Not enough memory!');
        return;
    }

    usedMemory += size;
    processCounter++;

    const process = {
        id: pid,
        name: pname,
        size: size,
        strategy: strategy
    };

    processes.push(process);
    updateUI();
    form.reset();
});

function updateUI() {
    // Update memory blocks visually
    memoryBlocks.innerHTML = '';
    processes.forEach(proc => {
        const block = document.createElement('div');
        block.className = 'memory-block allocated';
        block.style.flex = proc.size / TOTAL_MEMORY;
        block.innerText = proc.id;
        memoryBlocks.appendChild(block);
    });

    // Update stats
    const utilizationPercent = ((usedMemory / TOTAL_MEMORY) * 100).toFixed(1);
    utilization.innerText = `${utilizationPercent}%`;
    utilizationBar.style.width = `${utilizationPercent}%`;
    allocatedDisplay.innerText = `${usedMemory}B`;
    fragmentationDisplay.innerText = `${(Math.random() * 5).toFixed(1)}%`; // Example
    processCount.innerText = `${processCounter} processes`;

    // Update process list
    processList.innerHTML = '';
    processes.forEach(proc => {
        const item = document.createElement('div');
        item.className = 'process-item';
        item.innerHTML = `
            <strong>${proc.id}</strong> - ${proc.name} | ${proc.size}B
            <button onclick="deallocate('${proc.id}')">❌ Deallocate</button>
        `;
        processList.appendChild(item);
    });

    // Update history
    const historyItem = document.createElement('div');
    historyItem.className = 'history-item';
    const lastProc = processes[processes.length - 1];
    historyItem.innerText = `Allocated ${lastProc.size}B to ${lastProc.id} (${lastProc.name}) with ${lastProc.strategy}`;
    allocationHistory.prepend(historyItem);
}

function deallocate(pid) {
    const index = processes.findIndex(p => p.id === pid);
    if (index !== -1) {
        usedMemory -= processes[index].size;
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        historyItem.innerText = `Deallocated ${processes[index].size}B from ${processes[index].id}`;
        allocationHistory.prepend(historyItem);

        processes.splice(index, 1);
        processCounter--;
        updateUI();
    }
}

// Reset functionality
document.getElementById('resetBtn').addEventListener('click', () => {
    processes = [];
    usedMemory = 0;
    processCounter = 0;
    updateUI();
    allocationHistory.innerHTML = '<div class="empty-state"><div class="empty-icon">🕒</div><p>No allocation history yet</p><small>Memory operations will appear here</small></div>';
    processList.innerHTML = '<div class="empty-state"><div class="empty-icon">🖥️</div><p>No processes created yet</p><small>Use the allocation form to create your first process</small></div>';
});
