/**
 * NoteCard — Single note display with quick copy
 */
import { h } from 'preact';
import { useState } from 'preact/hooks';
import htm from 'htm';
import { togglePin, deleteItem, updateItem, formatTime, showNotification, viewingItem } from '../store.js';
import { CategoryPicker } from './CategoryPicker.js';

const html = htm.bind(h);

export function NoteCard({ item }) {
    const [editing, setEditing] = useState(false);
    const [showCatPicker, setShowCatPicker] = useState(false);
    const [editTitle, setEditTitle] = useState(item.title);
    const [editContent, setEditContent] = useState(item.content || '');
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

    const onCopy = async (e) => {
        e.stopPropagation();
        const text = item.content || item.title;
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                // Fallback for non-HTTPS contexts
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.cssText = 'position:fixed;left:-9999px';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
            }
            showNotification('Copied to clipboard', 'success');
        } catch {
            showNotification('Failed to copy', 'error');
        }
    };

    const onPin = async (e) => {
        e.stopPropagation();
        await togglePin(item.id);
    };

    const onDelete = async (e) => {
        e.stopPropagation();
        if (!confirm(`Delete "${item.title}"?`)) return;
        await deleteItem(item.id);
        showNotification('Deleted', 'success');
    };

    const onEdit = (e) => {
        e.stopPropagation();
        setEditTitle(item.title);
        setEditContent(item.content || '');
        setEditing(true);
    };

    const onSave = async (e) => {
        e.stopPropagation();
        try {
            await updateItem(item.id, { title: editTitle, content: editContent });
            setEditing(false);
            showNotification('Updated', 'success');
        } catch {
            showNotification('Failed to update', 'error');
        }
    };

    const onCancel = (e) => {
        e.stopPropagation();
        setEditing(false);
    };

    if (editing) {
        return html`
            <div class="item-card" onClick=${e => e.stopPropagation()}>
                <div class="note-editor">
                    <input class="form-input" value=${editTitle}
                        onInput=${e => setEditTitle(e.target.value)}
                        placeholder="Title"/>
                    <textarea class="form-textarea" value=${editContent}
                        onInput=${e => setEditContent(e.target.value)}
                        placeholder="Content" rows="4"/>
                    <div class="form-actions">
                        <button class="btn-secondary" onClick=${onCancel}>Cancel</button>
                        <button class="btn-primary" onClick=${onSave}>Save</button>
                    </div>
                </div>
            </div>
        `;
    }

    return html`
        <div class="item-card ${isPinned ? 'pinned' : ''}" onClick=${() => { viewingItem.value = item; }}>
            <div class="item-card-header">
                <span class="item-card-title">${item.title}</span>
            </div>

            ${item.content && html`
                <div class="item-card-preview">${item.content.slice(0, 300)}</div>
            `}

            <div class="item-card-footer">
                <div class="item-card-meta">
                    ${item.category && html`<span>${item.category}</span>`}
                    <span>${formatTime(item.updated_at)}</span>
                </div>
                <div class="item-card-actions">
                    <button class="icon-btn-sm" onClick=${(e) => { e.stopPropagation(); setShowCatPicker(!showCatPicker); }} title="Change category"
                        style="color: ${showCatPicker ? 'var(--accent-primary)' : 'var(--text-muted)'}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                    </button>
                    <button class="icon-btn-sm" onClick=${onCopy} title="Copy">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                        </svg>
                    </button>
                    <button class="icon-btn-sm" onClick=${onEdit} title="Edit">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="icon-btn-sm" onClick=${onPin} title=${isPinned ? 'Unpin' : 'Pin'}
                        style="color: ${isPinned ? 'var(--accent-warning)' : 'var(--text-muted)'}">
                        <svg viewBox="0 0 24 24" fill="${isPinned ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <path d="M12 2L9 9H2l5.5 4.5L5 22l7-5 7 5-2.5-8.5L22 9h-7z"/>
                        </svg>
                    </button>
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
