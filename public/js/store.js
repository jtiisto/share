/**
 * Share Store — Signals, LocalForage, API helpers, WebSocket client
 */
import { signal, batch } from '@preact/signals';
import localforage from 'localforage';

localforage.config({ name: 'ShareApp', storeName: 'share_data' });

const KEYS = { ITEMS: 'items', DIRTY: 'dirty_items', LAST_SYNC: 'last_sync_time' };

// ==================== Signals ====================

export const items = signal([]);
export const categories = signal([]);
export const isLoading = signal(true);
export const isSyncing = signal(false);
export const syncStatus = signal('gray');
export const selectedCategory = signal(null);

// ==================== API Helpers ====================

const API = '/api';

async function apiFetch(path, opts = {}) {
    const res = await fetch(`${API}${path}`, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return res.json();
}

// ==================== CRUD ====================

export async function loadItems(type, category) {
    let url = '/items?';
    if (type) url += `type=${type}&`;
    if (category !== null && category !== undefined) url += `category=${category}`;
    const data = await apiFetch(url);
    items.value = data;
    await localforage.setItem(KEYS.ITEMS, data);
    return data;
}

export async function loadCategories() {
    const data = await apiFetch('/categories');
    categories.value = data;
    return data;
}

export async function createNote(title, content, category = '', pinned = false) {
    const item = await apiFetch('/items', {
        method: 'POST',
        body: JSON.stringify({ title, content, category, pinned }),
    });
    items.value = [item, ...items.value];
    await localforage.setItem(KEYS.ITEMS, items.value);
    return item;
}

export async function updateItem(id, updates) {
    const item = await apiFetch(`/items/${id}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
    });
    items.value = items.value.map(i => i.id === id ? item : i);
    await localforage.setItem(KEYS.ITEMS, items.value);
    return item;
}

export async function deleteItem(id) {
    await apiFetch(`/items/${id}`, { method: 'DELETE' });
    items.value = items.value.filter(i => i.id !== id);
    await localforage.setItem(KEYS.ITEMS, items.value);
}

export async function togglePin(id) {
    const item = await apiFetch(`/items/${id}/pin`, { method: 'PATCH' });
    items.value = items.value.map(i => i.id === id ? item : i);
    await localforage.setItem(KEYS.ITEMS, items.value);
    return item;
}

export async function uploadFile(file, category = '', title = '', pinned = false) {
    const form = new FormData();
    form.append('file', file);
    form.append('category', category);
    form.append('title', title);
    form.append('pinned', pinned);

    const res = await fetch(`${API}/items/upload`, { method: 'POST', body: form });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    const item = await res.json();
    items.value = [item, ...items.value];
    await localforage.setItem(KEYS.ITEMS, items.value);
    return item;
}

// ==================== Sync ====================

export async function requestSync() {
    if (isSyncing.value || !navigator.onLine) return;
    isSyncing.value = true;

    try {
        const lastSync = await localforage.getItem(KEYS.LAST_SYNC) || '2000-01-01T00:00:00Z';
        const data = await apiFetch('/sync/pull', {
            method: 'POST',
            body: JSON.stringify({ since: lastSync }),
        });

        if (data.items && data.items.length > 0) {
            // Merge: server items take precedence (last-write-wins)
            const serverMap = new Map(data.items.map(i => [i.id, i]));
            const merged = items.value.map(i => serverMap.get(i.id) || i);
            // Add new items from server
            for (const si of data.items) {
                if (!merged.find(i => i.id === si.id)) {
                    merged.push(si);
                }
            }
            // Remove deleted
            items.value = merged.filter(i => !i.deleted);
            await localforage.setItem(KEYS.ITEMS, items.value);
        }

        await localforage.setItem(KEYS.LAST_SYNC, data.serverTime);
        syncStatus.value = 'green';
    } catch (e) {
        console.error('Sync failed:', e);
        syncStatus.value = 'red';
    } finally {
        isSyncing.value = false;
    }
}

// ==================== WebSocket ====================

let ws = null;
let wsReconnectTimer = null;

function connectWebSocket() {
    if (ws && ws.readyState <= 1) return;

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.onopen = () => {
        syncStatus.value = 'green';
        // Start ping interval
        const pingInterval = setInterval(() => {
            if (ws.readyState === 1) ws.send('ping');
            else clearInterval(pingInterval);
        }, 30000);
    };

    ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.event === 'pong') return;

            if (msg.event === 'item:created') {
                const existing = items.value.find(i => i.id === msg.data.id);
                if (!existing) {
                    items.value = [msg.data, ...items.value];
                }
            } else if (msg.event === 'item:updated') {
                items.value = items.value.map(i => i.id === msg.data.id ? msg.data : i);
            } else if (msg.event === 'item:deleted') {
                items.value = items.value.filter(i => i.id !== msg.data.id);
            }

            localforage.setItem(KEYS.ITEMS, items.value);
        } catch (e) {
            console.error('WS message error:', e);
        }
    };

    ws.onclose = () => {
        syncStatus.value = 'gray';
        wsReconnectTimer = setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = () => {
        syncStatus.value = 'red';
    };
}

// ==================== Init ====================

export async function initStore() {
    try {
        // Load from local cache first
        const cached = await localforage.getItem(KEYS.ITEMS);
        if (cached) {
            items.value = cached;
        }
        isLoading.value = false;

        // Then sync from server
        if (navigator.onLine) {
            await Promise.all([loadItems(), loadCategories()]);
            connectWebSocket();
            syncStatus.value = 'green';
        }
    } catch (e) {
        console.error('Init error:', e);
        isLoading.value = false;
    }

    // Reconnect on visibility change
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && navigator.onLine) {
            requestSync();
            connectWebSocket();
        }
    });

    window.addEventListener('online', () => {
        requestSync();
        connectWebSocket();
    });
}

// ==================== Notifications (simple) ====================

export function showNotification(message, type = 'info', duration = 3000) {
    const container = document.getElementById('notifications');
    if (!container) return;

    const el = document.createElement('div');
    el.className = `notification ${type}`;
    el.textContent = message;
    container.appendChild(el);

    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transition = 'opacity 0.3s';
        setTimeout(() => el.remove(), 300);
    }, duration);
}

// ==================== Utilities ====================

export function formatSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatTime(isoString) {
    if (!isoString) return '';
    const d = new Date(isoString);
    const now = new Date();
    const diff = now - d;

    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
    return d.toLocaleDateString();
}
