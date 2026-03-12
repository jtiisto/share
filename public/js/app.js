/**
 * Share App Shell — Bottom nav, view routing, WebSocket connection
 */
import { h, render } from 'preact';
import { signal, effect } from '@preact/signals';
import htm from 'htm';
import { initStore, syncStatus, isSyncing, requestSync } from './store.js';
import { ItemsView } from './items/ItemsView.js';
import { NotesView } from './items/NotesView.js';
import { AddSheet } from './items/AddSheet.js';
import { ContentViewer } from './items/ContentViewer.js';
import { ShareReceiver } from './items/ShareReceiver.js';

const html = htm.bind(h);

// ==================== State ====================

const activeView = signal(localStorage.getItem('share_active_view') || 'files');
const showAddSheet = signal(false);
export const viewingItem = signal(null);

// ==================== Icons ====================

const ICONS = {
    files: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="22" height="22">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
    </svg>`,
    notes: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="22" height="22">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
    </svg>`,
    plus: html`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" width="24" height="24">
        <line x1="12" y1="5" x2="12" y2="19"/>
        <line x1="5" y1="12" x2="19" y2="12"/>
    </svg>`,
};

function selectView(id) {
    activeView.value = id;
    localStorage.setItem('share_active_view', id);
}

// ==================== Components ====================

function SyncIndicator() {
    const status = syncStatus.value;
    const syncing = isSyncing.value;
    const cls = syncing ? 'syncing' : status;

    return html`
        <button class="icon-btn" onClick=${requestSync} title="Sync status">
            <span class="sync-dot ${cls}"></span>
        </button>
    `;
}

function Header() {
    const title = activeView.value === 'files' ? 'Files' : 'Notes';
    return html`
        <div class="header">
            <span class="header-title">${title}</span>
            <div class="header-actions">
                <${SyncIndicator}/>
            </div>
        </div>
    `;
}

function ViewContent() {
    if (activeView.value === 'notes') {
        return html`<${NotesView}/>`;
    }
    return html`<${ItemsView}/>`;
}

function NavBar() {
    return html`
        <nav class="nav-bar">
            <button class="nav-btn ${activeView.value === 'files' ? 'active' : ''}"
                onClick=${() => selectView('files')}>
                <span class="nav-icon">${ICONS.files}</span>
                <span class="nav-label">Files</span>
            </button>
            <button class="nav-btn ${activeView.value === 'notes' ? 'active' : ''}"
                onClick=${() => selectView('notes')}>
                <span class="nav-icon">${ICONS.notes}</span>
                <span class="nav-label">Notes</span>
            </button>
        </nav>
    `;
}

function App() {
    return html`
        <div class="shell">
            <${Header}/>
            <main class="view-content">
                <${ViewContent}/>
            </main>
            <button class="fab" onClick=${() => { showAddSheet.value = true; }} title="Add item">
                ${ICONS.plus}
            </button>
            <${NavBar}/>
            ${showAddSheet.value && html`
                <${AddSheet} onClose=${() => { showAddSheet.value = false; }}
                    defaultType=${activeView.value === 'notes' ? 'note' : 'file'}/>
            `}
            ${viewingItem.value && html`
                <${ContentViewer} item=${viewingItem.value}
                    onClose=${() => { viewingItem.value = null; }}/>
            `}
            <${ShareReceiver}/>
            <${Notifications}/>
        </div>
    `;
}

function Notifications() {
    return html`<div class="notification-container" id="notifications"></div>`;
}

// ==================== Init ====================

initStore();
render(html`<${App}/>`, document.getElementById('app'));
