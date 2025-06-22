from flask import Flask, render_template, request, jsonify
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)

# Database setup
def init_db():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # Create memory_blocks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memory_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            process_id TEXT,
            start_address INTEGER NOT NULL,
            size INTEGER NOT NULL,
            allocated BOOLEAN NOT NULL DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create processes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processes (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            size INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            allocated_at DATETIME,
            memory_block_id INTEGER,
            FOREIGN KEY (memory_block_id) REFERENCES memory_blocks (id)
        )
    ''')
    
    # Create allocation_history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS allocation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            process_id TEXT,
            size INTEGER,
            address INTEGER,
            strategy TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Initialize with one large free block if empty
    cursor.execute('SELECT COUNT(*) FROM memory_blocks')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO memory_blocks (start_address, size, allocated)
            VALUES (0, 1024, 0)
        ''')
    
    conn.commit()
    conn.close()

# Memory allocation strategies
def first_fit(size):
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, start_address, size FROM memory_blocks 
        WHERE allocated = 0 AND size >= ? 
        ORDER BY start_address ASC LIMIT 1
    ''', (size,))
    result = cursor.fetchone()
    conn.close()
    return result

def best_fit(size):
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, start_address, size FROM memory_blocks 
        WHERE allocated = 0 AND size >= ? 
        ORDER BY size ASC LIMIT 1
    ''', (size,))
    result = cursor.fetchone()
    conn.close()
    return result

def worst_fit(size):
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, start_address, size FROM memory_blocks 
        WHERE allocated = 0 AND size >= ? 
        ORDER BY size DESC LIMIT 1
    ''', (size,))
    result = cursor.fetchone()
    conn.close()
    return result

def merge_adjacent_blocks():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # Get all free blocks sorted by start address
    cursor.execute('''
        SELECT id, start_address, size FROM memory_blocks 
        WHERE allocated = 0 ORDER BY start_address
    ''')
    blocks = cursor.fetchall()
    
    merged = []
    for block in blocks:
        if merged and merged[-1][1] + merged[-1][2] == block[1]:
            # Merge with previous block
            merged[-1] = (merged[-1][0], merged[-1][1], merged[-1][2] + block[2])
            # Delete the current block
            cursor.execute('DELETE FROM memory_blocks WHERE id = ?', (block[0],))
        else:
            merged.append(block)
    
    # Update merged blocks
    for block in merged[:-len(blocks)]:
        cursor.execute('''
            UPDATE memory_blocks SET size = ? WHERE id = ?
        ''', (block[2], block[0]))
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/memory/allocate', methods=['POST'])
def allocate_memory():
    data = request.get_json()
    process_id = data.get('process_id')
    process_name = data.get('process_name', process_id)
    size = data.get('size')
    strategy = data.get('strategy', 'first-fit')
    
    if not process_id or not size or size <= 0:
        return jsonify({'success': False, 'message': 'Invalid input parameters'})
    
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # Check if process already exists and is allocated
    cursor.execute('SELECT status FROM processes WHERE id = ?', (process_id,))
    existing = cursor.fetchone()
    if existing and existing[0] == 'allocated':
        conn.close()
        return jsonify({'success': False, 'message': 'Process already allocated'})
    
    # Find suitable block based on strategy
    strategies = {
        'first-fit': first_fit,
        'best-fit': best_fit,
        'worst-fit': worst_fit
    }
    
    block = strategies.get(strategy, first_fit)(size)
    
    if not block:
        # Add to waiting processes
        cursor.execute('''
            INSERT OR REPLACE INTO processes (id, name, size, status)
            VALUES (?, ?, ?, 'waiting')
        ''', (process_id, process_name, size))
        
        cursor.execute('''
            INSERT INTO allocation_history (action, process_id, size, strategy)
            VALUES ('allocation_failed', ?, ?, ?)
        ''', (process_id, size, strategy))
        
        conn.commit()
        conn.close()
        return jsonify({'success': False, 'message': 'No suitable free block found'})
    
    block_id, start_address, block_size = block
    
    # Allocate the block
    cursor.execute('''
        UPDATE memory_blocks SET process_id = ?, allocated = 1, size = ?
        WHERE id = ?
    ''', (process_id, size, block_id))
    
    # Create remaining free block if necessary
    if block_size > size:
        cursor.execute('''
            INSERT INTO memory_blocks (start_address, size, allocated)
            VALUES (?, ?, 0)
        ''', (start_address + size, block_size - size))
    
    # Update or create process
    cursor.execute('''
        INSERT OR REPLACE INTO processes (id, name, size, status, allocated_at, memory_block_id)
        VALUES (?, ?, ?, 'allocated', ?, ?)
    ''', (process_id, process_name, size, datetime.now(), block_id))
    
    # Add to history
    cursor.execute('''
        INSERT INTO allocation_history (action, process_id, size, address, strategy)
        VALUES ('allocated', ?, ?, ?, ?)
    ''', (process_id, size, start_address, strategy))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'message': 'Memory allocated successfully',
        'address': start_address,
        'size': size
    })

@app.route('/api/memory/deallocate', methods=['POST'])
def deallocate_memory():
    data = request.get_json()
    process_id = data.get('process_id')
    
    if not process_id:
        return jsonify({'success': False, 'message': 'Process ID required'})
    
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # Find the process and its memory block
    cursor.execute('''
        SELECT p.memory_block_id, p.size, mb.start_address 
        FROM processes p
        JOIN memory_blocks mb ON p.memory_block_id = mb.id
        WHERE p.id = ? AND p.status = 'allocated'
    ''', (process_id,))
    
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({'success': False, 'message': 'Process not found or not allocated'})
    
    block_id, size, start_address = result
    
    # Free the memory block
    cursor.execute('''
        UPDATE memory_blocks SET process_id = NULL, allocated = 0
        WHERE id = ?
    ''', (block_id,))
    
    # Update process status
    cursor.execute('''
        UPDATE processes SET status = 'deallocated', memory_block_id = NULL
        WHERE id = ?
    ''', (process_id,))
    
    # Add to history
    cursor.execute('''
        INSERT INTO allocation_history (action, process_id, size, address)
        VALUES ('deallocated', ?, ?, ?)
    ''', (process_id, size, start_address))
    
    conn.commit()
    conn.close()
    
    # Merge adjacent free blocks
    merge_adjacent_blocks()
    
    return jsonify({
        'success': True,
        'message': 'Memory deallocated successfully'
    })

@app.route('/api/memory/status')
def memory_status():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # Get memory blocks
    cursor.execute('''
        SELECT start_address, size, allocated, process_id
        FROM memory_blocks ORDER BY start_address
    ''')
    blocks = cursor.fetchall()
    
    # Get processes
    cursor.execute('''
        SELECT id, name, size, status, allocated_at, memory_block_id
        FROM processes ORDER BY allocated_at DESC
    ''')
    processes = cursor.fetchall()
    
    # Get allocation history
    cursor.execute('''
        SELECT action, process_id, size, address, strategy, timestamp
        FROM allocation_history ORDER BY timestamp DESC LIMIT 20
    ''')
    history = cursor.fetchall()
    
    conn.close()
    
    # Calculate statistics
    total_memory = 1024
    allocated_memory = sum(block[1] for block in blocks if block[2])
    free_memory = total_memory - allocated_memory
    
    # Calculate fragmentation
    free_blocks = [block for block in blocks if not block[2]]
    fragmented_memory = sum(block[1] for block in free_blocks if block[1] < 16)
    fragmentation_percentage = (fragmented_memory / free_memory * 100) if free_memory > 0 else 0
    
    return jsonify({
        'blocks': [
            {
                'start_address': block[0],
                'size': block[1],
                'allocated': bool(block[2]),
                'process_id': block[3]
            } for block in blocks
        ],
        'processes': [
            {
                'id': proc[0],
                'name': proc[1],
                'size': proc[2],
                'status': proc[3],
                'allocated_at': proc[4],
                'memory_block_id': proc[5]
            } for proc in processes
        ],
        'history': [
            {
                'action': hist[0],
                'process_id': hist[1],
                'size': hist[2],
                'address': hist[3],
                'strategy': hist[4],
                'timestamp': hist[5]
            } for hist in history
        ],
        'stats': {
            'total_memory': total_memory,
            'allocated_memory': allocated_memory,
            'free_memory': free_memory,
            'utilization_percentage': (allocated_memory / total_memory) * 100,
            'fragmentation_percentage': fragmentation_percentage
        }
    })

@app.route('/api/memory/reset', methods=['POST'])
def reset_memory():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # Clear all tables
    cursor.execute('DELETE FROM memory_blocks')
    cursor.execute('DELETE FROM processes')
    cursor.execute('DELETE FROM allocation_history')
    
    # Initialize with one large free block
    cursor.execute('''
        INSERT INTO memory_blocks (start_address, size, allocated)
        VALUES (0, 1024, 0)
    ''')
    
    cursor.execute('''
        INSERT INTO allocation_history (action, process_id, size)
        VALUES ('system_reset', NULL, NULL)
    ''')
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Memory system reset successfully'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)