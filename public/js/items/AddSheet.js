/**
 * AddSheet — Bottom sheet for creating notes or uploading files
 */
import { h } from 'preact';
import { useState, useRef } from 'preact/hooks';
import htm from 'htm';
import { createNote, uploadFile, categories, showNotification } from '../store.js';

const html = htm.bind(h);

export function AddSheet({ onClose, defaultType = 'note' }) {
    const [type, setType] = useState(defaultType);
    const [title, setTitle] = useState('');
    const [content, setContent] = useState('');
    const [category, setCategory] = useState('');
    const [uploading, setUploading] = useState(false);
    const [dragover, setDragover] = useState(false);
    const fileRef = useRef(null);

    const onSubmitNote = async () => {
        if (!title.trim() && !content.trim()) return;
        try {
            await createNote(title.trim() || content.trim().slice(0, 50), content.trim(), category);
            showNotification('Note created', 'success');
            onClose();
        } catch (err) {
            showNotification('Failed to create note', 'error');
        }
    };

    const doUpload = async (file) => {
        if (!file) return;
        setUploading(true);
        try {
            await uploadFile(file, category, title || '', false);
            showNotification(`Uploaded: ${file.name}`, 'success');
            onClose();
        } catch (err) {
            showNotification('Upload failed', 'error');
        } finally {
            setUploading(false);
        }
    };

    const onFileSelect = (e) => {
        const file = e.target.files?.[0];
        if (file) doUpload(file);
    };

    const onDrop = (e) => {
        e.preventDefault();
        setDragover(false);
        const file = e.dataTransfer.files?.[0];
        if (file) doUpload(file);
    };

    const onOverlayClick = (e) => {
        if (e.target === e.currentTarget) onClose();
    };

    return html`
        <div class="sheet-overlay" onClick=${onOverlayClick}>
            <div class="sheet">
                <div class="sheet-handle"></div>
                <div class="sheet-title">Add ${type === 'note' ? 'Note' : 'File'}</div>

                <div style="display:flex; gap:var(--spacing-sm); margin-bottom:var(--spacing-md);">
                    <button class="category-chip ${type === 'note' ? 'active' : ''}"
                        onClick=${() => setType('note')}>Note</button>
                    <button class="category-chip ${type === 'file' ? 'active' : ''}"
                        onClick=${() => setType('file')}>File</button>
                </div>

                ${type === 'note' ? html`
                    <div class="note-editor">
                        <div class="form-group">
                            <label class="form-label">Title</label>
                            <input class="form-input" value=${title}
                                onInput=${e => setTitle(e.target.value)}
                                placeholder="Note title"/>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Content</label>
                            <textarea class="form-textarea" value=${content}
                                onInput=${e => setContent(e.target.value)}
                                placeholder="Write your note..." rows="5"/>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Category (optional)</label>
                            <input class="form-input" value=${category}
                                onInput=${e => setCategory(e.target.value)}
                                placeholder="e.g. work, personal"
                                list="cat-list"/>
                            <datalist id="cat-list">
                                ${categories.value.map(c => html`<option value=${c.name}/>`)}
                            </datalist>
                        </div>
                        <div class="form-actions">
                            <button class="btn-secondary" onClick=${onClose}>Cancel</button>
                            <button class="btn-primary" onClick=${onSubmitNote}
                                disabled=${!title.trim() && !content.trim()}>Create</button>
                        </div>
                    </div>
                ` : html`
                    <div>
                        <div class="form-group">
                            <label class="form-label">Category (optional)</label>
                            <input class="form-input" value=${category}
                                onInput=${e => setCategory(e.target.value)}
                                placeholder="e.g. docs, images"
                                list="cat-list-file"/>
                            <datalist id="cat-list-file">
                                ${categories.value.map(c => html`<option value=${c.name}/>`)}
                            </datalist>
                        </div>
                        <div class="upload-area ${dragover ? 'dragover' : ''}"
                            onClick=${() => fileRef.current?.click()}
                            onDragOver=${e => { e.preventDefault(); setDragover(true); }}
                            onDragLeave=${() => setDragover(false)}
                            onDrop=${onDrop}>
                            <input type="file" ref=${fileRef} onChange=${onFileSelect}/>
                            ${uploading
                                ? html`<div class="loading-spinner" style="margin:0 auto;"></div>`
                                : html`<p>Tap to select file or drag & drop</p>`
                            }
                        </div>
                        <div class="form-actions">
                            <button class="btn-secondary" onClick=${onClose}>Cancel</button>
                        </div>
                    </div>
                `}
            </div>
        </div>
    `;
}
