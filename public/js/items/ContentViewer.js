/**
 * ContentViewer — Full-screen rendered content viewer for HTML, MD, code files, and notes
 */
import { h } from 'preact';
import { useState, useEffect, useRef, useCallback } from 'preact/hooks';
import htm from 'htm';
import { CODE_EXTS, IMAGE_EXTS } from './ItemCard.js';

const html = htm.bind(h);

// Map file extensions to highlight.js language names where they differ
const EXT_TO_LANG = {
    js: 'javascript', mjs: 'javascript', cjs: 'javascript',
    jsx: 'javascript', ts: 'typescript', tsx: 'typescript',
    py: 'python', rb: 'ruby', rs: 'rust', kt: 'kotlin', kts: 'kotlin',
    cs: 'csharp', sh: 'bash', zsh: 'bash', fish: 'bash',
    ps1: 'powershell', bat: 'dos', cmd: 'dos',
    pl: 'perl', hs: 'haskell', ex: 'elixir', exs: 'elixir',
    erl: 'erlang', ml: 'ocaml', fs: 'fsharp', fsx: 'fsharp',
    clj: 'clojure', cljs: 'clojure', scm: 'scheme',
    yml: 'yaml', tf: 'hcl', gql: 'graphql',
    h: 'c', hpp: 'cpp', cc: 'cpp', cxx: 'cpp',
    dockerfile: 'dockerfile', makefile: 'makefile',
    cfg: 'ini', conf: 'ini', properties: 'ini', env: 'bash',
    svg: 'xml',
};

function getFileExt(item) {
    return (item.filename || '').split('.').pop().toLowerCase();
}

function isCodeItem(item) {
    if (item.type === 'note') return false;
    return CODE_EXTS.has(getFileExt(item));
}

function isImageItem(item) {
    if (item.type === 'note') return false;
    return IMAGE_EXTS.has(getFileExt(item));
}

function getDownloadUrl(item) {
    if (item.downloadUrl) return item.downloadUrl;
    return `/share/api/items/${item.id}/download`;
}

function getRenderUrl(item) {
    if (item.renderUrl) return item.renderUrl;
    return `/share/api/items/${item.id}/render`;
}

export function ContentViewer({ item, onClose }) {
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);
    const [zoomed, setZoomed] = useState(false);
    const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });
    const imgContainerRef = useRef(null);
    const dragRef = useRef({ dragging: false, startX: 0, startY: 0, startPanX: 0, startPanY: 0 });
    const isImage = isImageItem(item);
    const downloadUrl = getDownloadUrl(item);

    useEffect(() => {
        if (!isImage) loadContent();
        else setLoading(false);
    }, [item.id || item.title]);

    // Reset zoom state when item changes
    useEffect(() => {
        setZoomed(false);
        setPanOffset({ x: 0, y: 0 });
    }, [item.id || item.title]);

    async function loadContent() {
        setLoading(true);
        try {
            if (isCodeItem(item)) {
                await loadCodeContent();
            } else if (item.type === 'note') {
                await loadNoteContent();
            } else {
                await loadRenderedContent();
            }
        } catch (e) {
            setContent(`<p>Error loading content: ${escapeHtml(e.message)}</p>`);
        } finally {
            setLoading(false);
        }
    }

    async function loadCodeContent() {
        const res = await fetch(downloadUrl);
        if (!res.ok) {
            setContent('<p>Unable to load file</p>');
            return;
        }
        let text = await res.text();
        const ext = getFileExt(item);

        if (ext === 'json') {
            try {
                text = JSON.stringify(JSON.parse(text), null, 2);
            } catch { /* use raw text */ }
        }

        try {
            const hljs = (await import('highlight.js')).default;
            const lang = EXT_TO_LANG[ext] || ext;
            let result;
            if (hljs.getLanguage(lang)) {
                result = hljs.highlight(text, { language: lang });
            } else {
                result = hljs.highlightAuto(text);
            }
            setContent(`<pre class="hljs"><code>${result.value}</code></pre>`);
        } catch {
            setContent(`<pre style="white-space:pre-wrap">${escapeHtml(text)}</pre>`);
        }
    }

    async function loadNoteContent() {
        const text = item.content || '';
        try {
            const { marked } = await import('marked');
            setContent(marked(text));
        } catch {
            setContent(`<pre style="white-space:pre-wrap">${escapeHtml(text)}</pre>`);
        }
    }

    async function loadRenderedContent() {
        const res = await fetch(getRenderUrl(item));
        if (res.ok) {
            setContent(await res.text());
        } else {
            setContent('<p>Unable to render this file</p>');
        }
    }

    function escapeHtml(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // Image zoom/pan handlers
    const toggleZoom = useCallback((e) => {
        // Don't toggle if we just finished a drag/pan
        if (dragRef.current.didDrag) {
            dragRef.current.didDrag = false;
            return;
        }
        if (zoomed) {
            setZoomed(false);
            setPanOffset({ x: 0, y: 0 });
        } else {
            setZoomed(true);
            setPanOffset({ x: 0, y: 0 });
        }
    }, [zoomed]);

    const onPointerDown = useCallback((e) => {
        if (!zoomed) return;
        dragRef.current = { dragging: true, didDrag: false, startX: e.clientX, startY: e.clientY, startPanX: panOffset.x, startPanY: panOffset.y };
        e.currentTarget.setPointerCapture(e.pointerId);
    }, [zoomed, panOffset]);

    const onPointerMove = useCallback((e) => {
        if (!dragRef.current.dragging) return;
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;
        if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragRef.current.didDrag = true;
        setPanOffset({ x: dragRef.current.startPanX + dx, y: dragRef.current.startPanY + dy });
    }, []);

    const onPointerUp = useCallback(() => {
        dragRef.current.dragging = false;
    }, []);

    const showDownload = item.type === 'file' || item.downloadUrl;

    return html`
        <div class="content-viewer">
            <div class="content-viewer-header">
                <button class="icon-btn" onClick=${onClose}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="22" height="22">
                        <line x1="19" y1="12" x2="5" y2="12"/>
                        <polyline points="12 19 5 12 12 5"/>
                    </svg>
                </button>
                <span style="font-weight:500; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                    ${item.title}
                </span>
                ${showDownload && html`
                    <button class="icon-btn"
                        onClick=${() => window.open(downloadUrl, '_blank')}
                        title="Download">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </button>
                `}
            </div>
            ${isImage ? html`
                <div class="content-viewer-image ${zoomed ? 'zoomed' : ''}"
                    ref=${imgContainerRef}
                    onClick=${toggleZoom}
                    onPointerDown=${onPointerDown}
                    onPointerMove=${onPointerMove}
                    onPointerUp=${onPointerUp}>
                    <img src=${downloadUrl}
                        alt=${item.title}
                        class="viewer-img ${zoomed ? 'zoomed' : ''}"
                        style=${zoomed ? `transform: translate(${panOffset.x}px, ${panOffset.y}px)` : ''}
                        draggable="false"/>
                </div>
            ` : html`
                <div class="content-viewer-body">
                    ${loading
                        ? html`<div class="loading"><div class="loading-spinner"></div></div>`
                        : html`<div class="rendered-content" dangerouslySetInnerHTML=${{ __html: content }}/>`
                    }
                </div>
            `}
        </div>
    `;
}
