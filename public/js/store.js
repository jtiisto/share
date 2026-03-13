/**
 * Share Store — Signals, LocalForage, API helpers, WebSocket client
 * With offline dirty tracking and background push on reconnect
 */
import { signal, batch } from '@preact/signals';
import localforage from 'localforage';

localforage.config({ name: 'ShareApp', storeName: 'share_data' });

const KEYS = {
    ITEMS: 'items',
    DIRTY: 'dirty_items',
    LAST_SYNC: 'last_sync_time',
    CATEGORIES: 'categories',
};

// ==================== Signals ====================

export const items = signal([]);
export const categories = signal([]);
export const isLoading = signal(true);
export const isSyncing = signal(false);
export const syncStatus = signal('gray');  // 'green' | 'red' | 'gray' | 'dirty'
export const dirtyCount = signal(0);
export const selectedCategory = signal(null);
export const viewingItem = signal(null);

// ==================== API Helpers ====================

const API = '/share/api';

async function apiFetch(path, opts = {}) {
    const res = await fetch(`${API}${path}`, {
        headers: { 'Content-Type': 'application/json', ...opts.headers },
        ...opts,
    });
    if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
    return res.json();
}

// ==================== Dirty Tracking ====================

async function getDirtyIds() {
    return (await localforage.getItem(KEYS.DIRTY)) || [];
}

async function markDirty(id) {
    const dirty = await getDirtyIds();
    if (!dirty.includes(id)) {
        dirty.push(id);
        await localforage.setItem(KEYS.DIRTY, dirty);
    }
    dirtyCount.value = dirty.length;
    if (syncStatus.value === 'green') syncStatus.value = 'dirty';
}

async function clearDirty(ids) {
    const dirty = await getDirtyIds();
    const remaining = dirty.filter(id => !ids.includes(id));
    await localforage.setItem(KEYS.DIRTY, remaining);
    dirtyCount.value = remaining.length;
    if (remaining.length === 0 && syncStatus.value === 'dirty') {
        syncStatus.value = 'green';
    }
}

async function refreshDirtyCount() {
    const dirty = await getDirtyIds();
    dirtyCount.value = dirty.length;
}

function generateId() {
    return crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '') :
        Array.from(crypto.getRandomValues(new Uint8Array(16)))
            .map(b => b.toString(16).padStart(2, '0')).join('');
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
    await localforage.setItem(KEYS.CATEGORIES, data);
    return data;
}

export async function createNote(title, content, category = '', pinned = false) {
    if (!navigator.onLine) {
        // Offline: create locally with dirty flag
        const id = generateId();
        const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
        const item = {
            id, type: 'note', title, content, category,
            pinned: pinned ? 1 : 0, source: 'web',
            created_at: now, updated_at: now,
            deleted: 0, _version: 1, _lastModifiedBy: '',
            filename: null, mime_type: null, size_bytes: 0,
        };
        items.value = [item, ...items.value];
        await localforage.setItem(KEYS.ITEMS, items.value);
        await markDirty(id);
        showNotification('Note saved offline', 'warning');
        return item;
    }

    const item = await apiFetch('/items', {
        method: 'POST',
        body: JSON.stringify({ title, content, category, pinned }),
    });
    items.value = [item, ...items.value];
    await localforage.setItem(KEYS.ITEMS, items.value);
    return item;
}

export async function updateItem(id, updates) {
    if (!navigator.onLine) {
        // Offline: update locally with dirty flag
        const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
        items.value = items.value.map(i => {
            if (i.id !== id) return i;
            return { ...i, ...updates, updated_at: now };
        });
        await localforage.setItem(KEYS.ITEMS, items.value);
        await markDirty(id);
        showNotification('Updated offline', 'warning');
        return items.value.find(i => i.id === id);
    }

    const item = await apiFetch(`/items/${id}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
    });
    items.value = items.value.map(i => i.id === id ? item : i);
    await localforage.setItem(KEYS.ITEMS, items.value);
    return item;
}

export async function deleteItem(id) {
    if (!navigator.onLine) {
        const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
        items.value = items.value.map(i => {
            if (i.id !== id) return i;
            return { ...i, deleted: 1, updated_at: now };
        }).filter(i => !i.deleted);
        await localforage.setItem(KEYS.ITEMS, items.value);
        await markDirty(id);
        showNotification('Deleted offline', 'warning');
        return;
    }

    await apiFetch(`/items/${id}`, { method: 'DELETE' });
    items.value = items.value.filter(i => i.id !== id);
    await localforage.setItem(KEYS.ITEMS, items.value);
}

export async function togglePin(id) {
    const item = items.value.find(i => i.id === id);
    if (!item) return null;

    if (!navigator.onLine) {
        const newPinned = item.pinned ? 0 : 1;
        return updateItem(id, { pinned: newPinned });
    }

    const updated = await apiFetch(`/items/${id}/pin`, { method: 'PATCH' });
    items.value = items.value.map(i => i.id === id ? updated : i);
    await localforage.setItem(KEYS.ITEMS, items.value);
    return updated;
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

// ==================== Category Management ====================

export async function updateCategory(name, updates) {
    const cat = await apiFetch(`/categories/${encodeURIComponent(name)}`, {
        method: 'PUT',
        body: JSON.stringify(updates),
    });
    await loadCategories();
    // If renamed, update items in local state
    if (updates.name && updates.name !== name) {
        items.value = items.value.map(i =>
            i.category === name ? { ...i, category: updates.name } : i
        );
        await localforage.setItem(KEYS.ITEMS, items.value);
    }
    return cat;
}

export async function deleteCategory(name) {
    await apiFetch(`/categories/${encodeURIComponent(name)}`, { method: 'DELETE' });
    // Clear category from local items
    items.value = items.value.map(i =>
        i.category === name ? { ...i, category: '' } : i
    );
    await localforage.setItem(KEYS.ITEMS, items.value);
    await loadCategories();
    if (selectedCategory.value === name) {
        selectedCategory.value = null;
    }
}

// ==================== Sync ====================

async function pushDirtyItems() {
    const dirtyIds = await getDirtyIds();
    if (dirtyIds.length === 0) return;

    const dirtyItems = items.value.filter(i => dirtyIds.includes(i.id));
    if (dirtyItems.length === 0) {
        await clearDirty(dirtyIds);
        return;
    }

    try {
        await apiFetch('/sync/push', {
            method: 'POST',
            body: JSON.stringify({ items: dirtyItems }),
        });
        await clearDirty(dirtyIds);
    } catch (e) {
        console.error('Failed to push dirty items:', e);
    }
}

export async function requestSync() {
    if (isSyncing.value || !navigator.onLine) return;
    isSyncing.value = true;

    try {
        // Push any dirty items first
        await pushDirtyItems();

        // Then pull
        const lastSync = await localforage.getItem(KEYS.LAST_SYNC) || '2000-01-01T00:00:00Z';
        const data = await apiFetch('/sync/pull', {
            method: 'POST',
            body: JSON.stringify({ since: lastSync }),
        });

        if (data.items && data.items.length > 0) {
            const serverMap = new Map(data.items.map(i => [i.id, i]));
            const merged = items.value.map(i => serverMap.get(i.id) || i);
            for (const si of data.items) {
                if (!merged.find(i => i.id === si.id)) {
                    merged.push(si);
                }
            }
            items.value = merged.filter(i => !i.deleted);
            await localforage.setItem(KEYS.ITEMS, items.value);
        }

        await localforage.setItem(KEYS.LAST_SYNC, data.serverTime);
        const remainingDirty = await getDirtyIds();
        syncStatus.value = remainingDirty.length > 0 ? 'dirty' : 'green';
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
    ws = new WebSocket(`${proto}//${location.host}/share/ws`);

    ws.onopen = () => {
        if (dirtyCount.value > 0) {
            syncStatus.value = 'dirty';
        } else {
            syncStatus.value = 'green';
        }
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
        syncStatus.value = dirtyCount.value > 0 ? 'dirty' : 'gray';
        wsReconnectTimer = setTimeout(connectWebSocket, 5000);
    };

    ws.onerror = () => {
        syncStatus.value = 'red';
    };
}

// ==================== Share Queue (offline) ====================

export async function processShareQueue() {
    try {
        const queue = await localforage.getItem('share_queue') || [];
        if (queue.length === 0) return;

        for (const entry of queue) {
            const form = new FormData();
            if (entry.title) form.append('title', entry.title);
            if (entry.text) form.append('text', entry.text);
            if (entry.url) form.append('url', entry.url);

            await fetch('/share/api/share', { method: 'POST', body: form });
        }

        await localforage.removeItem('share_queue');
        showNotification(`Synced ${queue.length} queued share(s)`, 'success');
    } catch (e) {
        console.error('Failed to process share queue:', e);
    }
}

export async function queueShare(data) {
    const queue = await localforage.getItem('share_queue') || [];
    queue.push(data);
    await localforage.setItem('share_queue', queue);
}

// ==================== Init ====================

export async function initStore() {
    try {
        const [cached, cachedCats] = await Promise.all([
            localforage.getItem(KEYS.ITEMS),
            localforage.getItem(KEYS.CATEGORIES),
        ]);
        if (cached) items.value = cached;
        if (cachedCats) categories.value = cachedCats;
        await refreshDirtyCount();
        isLoading.value = false;

        if (navigator.onLine) {
            await Promise.all([loadItems(), loadCategories()]);
            await processShareQueue();
            await pushDirtyItems();
            connectWebSocket();
            const remainingDirty = await getDirtyIds();
            syncStatus.value = remainingDirty.length > 0 ? 'dirty' : 'green';
        } else {
            syncStatus.value = dirtyCount.value > 0 ? 'dirty' : 'gray';
        }
    } catch (e) {
        console.error('Init error:', e);
        isLoading.value = false;
    }

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && navigator.onLine) {
            requestSync();
            connectWebSocket();
        }
    });

    window.addEventListener('online', () => {
        requestSync();
        processShareQueue();
        connectWebSocket();
    });

    window.addEventListener('offline', () => {
        syncStatus.value = dirtyCount.value > 0 ? 'dirty' : 'gray';
    });
}

// ==================== Notifications ====================

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
