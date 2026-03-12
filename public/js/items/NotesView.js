/**
 * NotesView — Note list with inline editing
 */
import { h } from 'preact';
import htm from 'htm';
import { items } from '../store.js';
import { NoteCard } from './NoteCard.js';

const html = htm.bind(h);

export function NotesView() {
    const notes = items.value.filter(i => i.type === 'note');
    const pinned = notes.filter(i => i.pinned);
    const unpinned = notes.filter(i => !i.pinned);

    return html`
        <div>
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
