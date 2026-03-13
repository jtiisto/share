/**
 * CategoryManager — Full-screen category management (rename, reorder, delete, colors)
 */
import { h } from 'preact';
import { useState } from 'preact/hooks';
import htm from 'htm';
import {
    categories, loadCategories,
    updateCategory, deleteCategory, showNotification,
} from '../store.js';

const html = htm.bind(h);

function CategoryRow({ cat, onStartEdit }) {
    const onDelete = async () => {
        if (!confirm(`Delete category "${cat.name}"? Items will be uncategorized.`)) return;
        try {
            await deleteCategory(cat.name);
            showNotification(`Deleted "${cat.name}"`, 'success');
        } catch (e) {
            showNotification('Failed to delete', 'error');
        }
    };

    return html`
        <div class="cat-manager-item">
            <span class="cat-color-dot" style="background-color: ${cat.color || 'var(--text-muted)'}"></span>
            <span class="cat-name">${cat.name}</span>
            <span class="cat-sort">${cat.sort_order}</span>
            <button class="icon-btn" onClick=${() => onStartEdit(cat)} title="Edit">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
            </button>
            <button class="icon-btn" onClick=${onDelete} title="Delete">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
            </button>
        </div>
    `;
}

function EditForm({ cat, onDone }) {
    const [name, setName] = useState(cat ? cat.name : '');
    const [color, setColor] = useState(cat ? cat.color || '#6b7280' : '#6b7280');
    const [sortOrder, setSortOrder] = useState(cat ? cat.sort_order : 0);
    const isNew = !cat;

    const onSave = async () => {
        if (!name.trim()) return;
        try {
            if (isNew) {
                await fetch('/api/categories', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name.trim(), color, sort_order: sortOrder }),
                });
                await loadCategories();
                showNotification(`Created "${name.trim()}"`, 'success');
            } else {
                await updateCategory(cat.name, {
                    name: name.trim() !== cat.name ? name.trim() : undefined,
                    color,
                    sort_order: sortOrder,
                });
                showNotification(`Updated "${name.trim()}"`, 'success');
            }
            onDone();
        } catch (e) {
            showNotification('Failed to save', 'error');
        }
    };

    return html`
        <div style="padding: var(--spacing-md); background: var(--bg-card); border-radius: var(--radius-md); border: 1px solid var(--border-color);">
            <div class="cat-edit-row" style="margin-bottom: var(--spacing-sm);">
                <input class="form-input" value=${name} onInput=${e => setName(e.target.value)}
                    placeholder="Category name"/>
                <input type="color" class="color-input" value=${color}
                    onInput=${e => setColor(e.target.value)}/>
            </div>
            <div class="cat-edit-row" style="margin-bottom: var(--spacing-md);">
                <label class="form-label" style="margin:0; white-space:nowrap;">Sort order</label>
                <input class="form-input" type="number" value=${sortOrder}
                    onInput=${e => setSortOrder(parseInt(e.target.value) || 0)}
                    style="width: 80px;"/>
            </div>
            <div class="form-actions" style="margin-top:0;">
                <button class="btn-secondary" onClick=${onDone}>Cancel</button>
                <button class="btn-primary" onClick=${onSave} disabled=${!name.trim()}>
                    ${isNew ? 'Create' : 'Save'}
                </button>
            </div>
        </div>
    `;
}

export function CategoryManager({ onClose }) {
    const [editing, setEditing] = useState(null); // null | category obj | 'new'

    const onOverlayClick = (e) => {
        if (e.target === e.currentTarget) onClose();
    };

    return html`
        <div class="sheet-overlay" onClick=${onOverlayClick}>
            <div class="sheet">
                <div class="sheet-handle"></div>
                <div class="sheet-title">Manage Categories</div>

                <div class="cat-manager-list">
                    ${categories.value.map(cat => {
                        if (editing && editing !== 'new' && editing.name === cat.name) {
                            return html`<${EditForm} key=${cat.name} cat=${cat}
                                onDone=${() => setEditing(null)}/>`;
                        }
                        return html`<${CategoryRow} key=${cat.name} cat=${cat}
                            onStartEdit=${(c) => setEditing(c)}/>`;
                    })}

                    ${editing === 'new' ? html`
                        <${EditForm} cat=${null} onDone=${() => setEditing(null)}/>
                    ` : html`
                        <button class="btn-secondary" style="width:100%; margin-top: var(--spacing-sm);"
                            onClick=${() => setEditing('new')}>
                            + Add Category
                        </button>
                    `}
                </div>

                <div class="form-actions">
                    <button class="btn-secondary" onClick=${onClose}>Close</button>
                </div>
            </div>
        </div>
    `;
}
