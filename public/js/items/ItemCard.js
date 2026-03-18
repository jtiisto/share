/**
 * ItemCard — Single item display (file or note)
 */
import { h } from 'preact';
import { useState } from 'preact/hooks';
import htm from 'htm';
import { togglePin, deleteItem, updateItem, formatSize, formatTime, showNotification, viewingItem } from '../store.js';
import { CategoryPicker } from './CategoryPicker.js';

const html = htm.bind(h);

// Extensions renderable as markup (existing behavior)
const MARKUP_EXTS = new Set(['html', 'htm', 'md', 'markdown', 'txt']);

// Extensions renderable with syntax highlighting (highlight.js supported languages)
const CODE_EXTS = new Set([
    // Web
    'js', 'mjs', 'cjs', 'jsx', 'ts', 'tsx', 'css', 'scss', 'sass', 'less',
    // Data / config
    'json', 'yaml', 'yml', 'toml', 'xml', 'svg', 'csv', 'ini', 'cfg', 'conf',
    'properties', 'env', 'graphql', 'gql', 'proto',
    // Systems / compiled
    'py', 'rb', 'go', 'rs', 'java', 'c', 'h', 'cpp', 'hpp', 'cc', 'cxx',
    'cs', 'swift', 'kt', 'kts', 'scala', 'dart', 'zig', 'nim', 'v',
    // Scripting / shell
    'sh', 'bash', 'zsh', 'fish', 'ps1', 'bat', 'cmd', 'lua', 'perl', 'pl',
    'r', 'php',
    // Functional
    'hs', 'elm', 'clj', 'cljs', 'ex', 'exs', 'erl', 'ml', 'fs', 'fsx',
    'lisp', 'scm',
    // Database / query
    'sql',
    // Infra / build
    'dockerfile', 'tf', 'hcl', 'nix', 'cmake', 'gradle', 'makefile',
    // Docs / diff
    'diff', 'patch', 'log',
    // Other
    'asm', 'wasm', 'vhdl', 'verilog',
]);

function canRender(item) {
    if (item.type === 'note') return true;
    const ext = (item.filename || '').split('.').pop().toLowerCase();
    return MARKUP_EXTS.has(ext) || CODE_EXTS.has(ext);
}

function isCodeFile(item) {
    const ext = (item.filename || '').split('.').pop().toLowerCase();
    return CODE_EXTS.has(ext);
}

export { CODE_EXTS };

export function ItemCard({ item }) {
    const [showCatPicker, setShowCatPicker] = useState(false);
    const isFile = item.type === 'file';
    const isPinned = item.pinned;

    const onCategoryChange = async (category) => {
        try {
            await updateItem(item.id, { category });
            setShowCatPicker(false);
            showNotification('Category updated', 'success');
        } catch {
            showNotification('Failed to update category', 'error');
        }
    };

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
                    <button class="icon-btn-sm" onClick=${(e) => { e.stopPropagation(); setShowCatPicker(!showCatPicker); }} title="Change category"
                        style="color: ${showCatPicker ? 'var(--accent-primary)' : 'var(--text-muted)'}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                    </button>
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

            ${showCatPicker && html`
                <div class="item-card-category-picker" onClick=${(e) => e.stopPropagation()}>
                    <${CategoryPicker} value=${item.category || ''} onChange=${onCategoryChange}/>
                </div>
            `}
        </div>
    `;
}
