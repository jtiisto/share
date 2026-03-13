/**
 * ItemCard — Single item display (file or note)
 */
import { h } from 'preact';
import htm from 'htm';
import { togglePin, deleteItem, formatSize, formatTime, showNotification, viewingItem } from '../store.js';

const html = htm.bind(h);

function canRender(item) {
    if (item.type === 'note') return true;
    const ext = (item.filename || '').split('.').pop().toLowerCase();
    return ['html', 'htm', 'md', 'markdown', 'txt'].includes(ext);
}

export function ItemCard({ item }) {
    const isFile = item.type === 'file';
    const isPinned = item.pinned;

    const onPin = async (e) => {
        e.stopPropagation();
        try {
            await togglePin(item.id);
        } catch (err) {
            showNotification('Failed to toggle pin', 'error');
        }
    };

    const onDelete = async (e) => {
        e.stopPropagation();
        if (!confirm(`Delete "${item.title}"?`)) return;
        try {
            await deleteItem(item.id);
            showNotification('Deleted', 'success');
        } catch (err) {
            showNotification('Failed to delete', 'error');
        }
    };

    const onDownload = (e) => {
        e.stopPropagation();
        window.open(`/share/api/items/${item.id}/download`, '_blank');
    };

    const onClick = () => {
        if (canRender(item)) {
            viewingItem.value = item;
        } else if (isFile) {
            window.open(`/share/api/items/${item.id}/download`, '_blank');
        }
    };

    return html`
        <div class="item-card ${isPinned ? 'pinned' : ''}" onClick=${onClick}>
            <div class="item-card-header">
                <span class="item-card-title">${item.title}</span>
                <span class="item-type-badge">${isFile ? 'file' : 'note'}</span>
            </div>

            ${item.content && html`
                <div class="item-card-preview">${item.content.slice(0, 200)}</div>
            `}

            <div class="item-card-footer">
                <div class="item-card-meta">
                    ${item.category && html`<span>${item.category}</span>`}
                    ${isFile && html`<span class="file-size">${formatSize(item.size_bytes)}</span>`}
                    <span>${formatTime(item.updated_at)}</span>
                </div>
                <div class="item-card-actions">
                    <button class="icon-btn-sm" onClick=${onPin} title=${isPinned ? 'Unpin' : 'Pin'}
                        style="color: ${isPinned ? 'var(--accent-warning)' : 'var(--text-muted)'}">
                        <svg viewBox="0 0 24 24" fill="${isPinned ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M12 2L9 9H2l5.5 4.5L5 22l7-5 7 5-2.5-8.5L22 9h-7z"/>
                        </svg>
                    </button>
                    ${isFile && html`
                        <button class="icon-btn-sm" onClick=${onDownload} title="Download">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                                <polyline points="7 10 12 15 17 10"/>
                                <line x1="12" y1="15" x2="12" y2="3"/>
                            </svg>
                        </button>
                    `}
                    <button class="icon-btn-sm" onClick=${onDelete} title="Delete">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    `;
}
