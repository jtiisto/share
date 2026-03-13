/**
 * NotesView — Note list with category filter + inline editing
 */
import { h } from 'preact';
import { useEffect } from 'preact/hooks';
import htm from 'htm';
import { items, categories, loadCategories, selectedNoteCategory } from '../store.js';
import { NoteCard } from './NoteCard.js';

const html = htm.bind(h);

export function NotesView() {
    useEffect(() => {
        loadCategories();
    }, []);

    const allNotes = items.value.filter(i => i.type === 'note');
    const cat = selectedNoteCategory.value;
    const notes = cat ? allNotes.filter(i => i.category === cat) : allNotes;
    const pinned = notes.filter(i => i.pinned);
    const unpinned = notes.filter(i => !i.pinned);

    return html`
        <div>
            <div class="category-filter">
                <button class="category-chip ${!cat ? 'active' : ''}"
                    onClick=${() => { selectedNoteCategory.value = null; }}>All</button>
                ${categories.value.map(c => html`
                    <button key=${c.name}
                        class="category-chip ${cat === c.name ? 'active' : ''}"
                        style=${c.color ? `--chip-color: ${c.color}` : ''}
                        onClick=${() => { selectedNoteCategory.value = c.name; }}>
                        ${c.color ? html`<span class="cat-color-dot" style="background:${c.color}; width:8px; height:8px; display:inline-block; margin-right:4px; vertical-align:middle;"></span>` : null}
                        ${c.name}
                    </button>
                `)}
            </div>

            ${notes.length === 0 && html`
                <div class="empty-state">
                    <div class="empty-state-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
                            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </div>
                    <p>No notes yet</p>
                    <p style="font-size: var(--font-size-sm); margin-top: 4px;">Tap + to create a note</p>
                </div>
            `}

            <div class="item-list">
                ${pinned.map(note => html`<${NoteCard} key=${note.id} item=${note}/>`)}
                ${unpinned.map(note => html`<${NoteCard} key=${note.id} item=${note}/>`)}
            </div>
        </div>
    `;
}
