/**
 * ContentViewer — Full-screen rendered content viewer for HTML, MD, and notes
 */
import { h } from 'preact';
import { useState, useEffect } from 'preact/hooks';
import htm from 'htm';

const html = htm.bind(h);

export function ContentViewer({ item, onClose }) {
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadContent();
    }, [item.id]);

    async function loadContent() {
        setLoading(true);
        try {
            if (item.type === 'note') {
                // Try to render markdown client-side
                const text = item.content || '';
                try {
                    const { marked } = await import('marked');
                    setContent(marked(text));
                } catch {
                    setContent(`<pre style="white-space:pre-wrap">${escapeHtml(text)}</pre>`);
                }
            } else {
                // Fetch rendered content from server
                const res = await fetch(`/share/api/items/${item.id}/render`);
                if (res.ok) {
                    setContent(await res.text());
                } else {
                    setContent('<p>Unable to render this file</p>');
                }
            }
        } catch (e) {
            setContent(`<p>Error loading content: ${escapeHtml(e.message)}</p>`);
        } finally {
            setLoading(false);
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
