/**
 * ContentViewer — Full-screen rendered content viewer for HTML, MD, code files, and notes
 */
import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import htm from 'htm';
import { CODE_EXTS } from './ItemCard.js';

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

export function ContentViewer({ item, onClose }) {
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadContent();
    }, [item.id]);

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
        // Fetch raw file content via download endpoint
        const res = await fetch(`/share/api/items/${item.id}/download`);
        if (!res.ok) {
            setContent('<p>Unable to load file</p>');
            return;
        }
        let text = await res.text();
        const ext = getFileExt(item);

        // Pretty-print JSON
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
            // Fallback: plain pre block
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
        const res = await fetch(`/share/api/items/${item.id}/render`);
        if (res.ok) {
            setContent(await res.text());
        } else {
            setContent('<p>Unable to render this file</p>');
        }
    }

    function escapeHtml(str) {
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

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
                ${item.type === 'file' && html`
                    <button class="icon-btn"
                        onClick=${() => window.open('/share/api/items/' + item.id + '/download', '_blank')}
                        title="Download">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                            <polyline points="7 10 12 15 17 10"/>
                            <line x1="12" y1="15" x2="12" y2="3"/>
                        </svg>
                    </button>
                `}
            </div>
            <div class="content-viewer-body">
                ${loading
                    ? html`<div class="loading"><div class="loading-spinner"></div></div>`
                    : html`<div class="rendered-content" dangerouslySetInnerHTML=${{ __html: content }}/>`
                }
            </div>
        </div>
    `;
}
