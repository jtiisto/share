/**
 * FoldersView — Shared folder list and folder contents browser
 */
import { h } from 'preact';
import { useState, useEffect, useRef } from 'preact/hooks';
import { signal } from '@preact/signals';
import htm from 'htm';
import { folders, loadFolders, unshareFolder, loadFolderFiles, showNotification, viewingItem, formatSize, formatTime } from '../store.js';
import { IMAGE_EXTS } from './ItemCard.js';

const html = htm.bind(h);

// Which folder is currently open (null = show folder list)
const openFolder = signal(null);

// Viewable extensions (same set as backend)
const VIEWABLE_EXTS = new Set([
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif',
    'html', 'htm', 'md', 'markdown', 'txt',
    'js', 'mjs', 'cjs', 'jsx', 'ts', 'tsx', 'css', 'scss', 'sass', 'less',
    'json', 'yaml', 'yml', 'toml', 'xml', 'csv', 'ini', 'cfg', 'conf',
    'properties', 'env', 'graphql', 'gql', 'proto',
    'py', 'rb', 'go', 'rs', 'java', 'c', 'h', 'cpp', 'hpp', 'cc', 'cxx',
    'cs', 'swift', 'kt', 'kts', 'scala', 'dart', 'zig', 'nim', 'v',
    'sh', 'bash', 'zsh', 'fish', 'ps1', 'bat', 'cmd', 'lua', 'perl', 'pl',
    'r', 'php',
    'hs', 'elm', 'clj', 'cljs', 'ex', 'exs', 'erl', 'ml', 'fs', 'fsx',
    'lisp', 'scm',
    'sql',
    'dockerfile', 'tf', 'hcl', 'nix', 'cmake', 'gradle', 'makefile',
    'diff', 'patch', 'log',
    'asm', 'wasm', 'vhdl', 'verilog',
]);

function getExt(filename) {
    return (filename || '').split('.').pop().toLowerCase();
}

function isViewable(filename) {
    return VIEWABLE_EXTS.has(getExt(filename));
}

function isImage(filename) {
    return IMAGE_EXTS.has(getExt(filename));
}

function formatModified(mtime) {
    if (!mtime) return '';
    return formatTime(new Date(mtime * 1000).toISOString());
}

function FolderCard({ folder }) {
    const onDelete = async (e) => {
        e.stopPropagation();
        if (!confirm(`Unshare "${folder.name}"? (The original directory will not be deleted)`)) return;
        try {
            await unshareFolder(folder.name);
            showNotification('Folder unshared', 'success');
        } catch (err) {
            showNotification('Failed to unshare', 'error');
        }
    };

    return html`
        <div class="item-card" onClick=${() => { openFolder.value = folder.name; }}>
            <div class="item-card-header">
                <span class="item-card-title">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18" style="vertical-align: -3px; margin-right: 6px; color: var(--accent-warning);">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                    </svg>
                    ${folder.name}
                </span>
                <span class="item-type-badge">folder</span>
            </div>
            <div class="item-card-footer">
                <div class="item-card-meta">
                    <span>${folder.file_count} file${folder.file_count !== 1 ? 's' : ''}</span>
                    <span>${formatTime(folder.created_at)}</span>
                </div>
                <div class="item-card-actions">
                    <button class="icon-btn-sm" onClick=${onDelete} title="Unshare">
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

function FileRow({ file, folderName }) {
    const ext = getExt(file.name);
    const viewable = isViewable(file.name);

    const onClick = () => {
        const downloadUrl = `/share/api/folders/${encodeURIComponent(folderName)}/files/${encodeURIComponent(file.name)}`;
        if (viewable) {
            // Open in ContentViewer with folder-based URLs
            viewingItem.value = {
                title: file.name,
                type: 'file',
                filename: file.name,
                mime_type: file.mime_type,
                downloadUrl: downloadUrl,
                renderUrl: `${downloadUrl}/render`,
            };
        } else {
            window.open(downloadUrl, '_blank');
        }
    };

    return html`
        <div class="item-card" onClick=${onClick}>
            <div class="item-card-header">
                <span class="item-card-title">${file.name}</span>
                <span class="item-type-badge">${ext}</span>
            </div>
            <div class="item-card-footer">
                <div class="item-card-meta">
                    <span class="file-size">${formatSize(file.size)}</span>
                    <span>${formatModified(file.modified)}</span>
                </div>
                <div class="item-card-actions">
                    ${viewable && html`
                        <span style="color: var(--accent-success); font-size: var(--font-size-sm);">viewable</span>
                    `}
                </div>
            </div>
        </div>
    `;
}

function FolderContents({ name }) {
    const [files, setFiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const pollRef = useRef(null);

    async function fetchFiles() {
        try {
            const data = await loadFolderFiles(name);
            setFiles(data);
        } catch (err) {
            showNotification('Failed to load folder contents', 'error');
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        fetchFiles();
        // Poll every 10 seconds while viewing
        pollRef.current = setInterval(fetchFiles, 10000);
        return () => clearInterval(pollRef.current);
    }, [name]);

    return html`
        <div>
            <div class="folder-contents-header">
                <button class="icon-btn" onClick=${() => { openFolder.value = null; }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22">
                        <line x1="19" y1="12" x2="5" y2="12"/>
                        <polyline points="12 19 5 12 12 5"/>
                    </svg>
                </button>
                <span class="folder-contents-title">${name}</span>
                <span style="color: var(--text-muted); font-size: var(--font-size-sm);">${files.length} file${files.length !== 1 ? 's' : ''}</span>
            </div>

            ${loading ? html`
                <div class="loading"><div class="loading-spinner"></div></div>
            ` : files.length === 0 ? html`
                <div class="empty-state">
                    <p>No files in this folder</p>
                </div>
            ` : html`
                <div class="item-list">
                    ${files.map(f => html`<${FileRow} key=${f.name} file=${f} folderName=${name}/>`)}
                </div>
            `}
        </div>
    `;
}

export function FoldersView() {
    useEffect(() => {
        loadFolders();
    }, []);

    // If a folder is open, show its contents
    if (openFolder.value) {
        return html`<${FolderContents} name=${openFolder.value}/>`;
    }

    const folderList = folders.value;

    return html`
        <div>
            ${folderList.length === 0 && html`
                <div class="empty-state">
                    <div class="empty-state-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                        </svg>
                    </div>
                    <p>No shared folders</p>
                    <p style="font-size: var(--font-size-sm); margin-top: 4px;">Share directories from the server using the CLI or skill</p>
                </div>
            `}

            <div class="item-list">
                ${folderList.map(f => html`<${FolderCard} key=${f.name} folder=${f}/>`)}
            </div>
        </div>
    `;
}

// Reset open folder when navigating away
export function resetFolderView() {
    openFolder.value = null;
}
