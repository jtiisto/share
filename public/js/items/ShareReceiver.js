/**
 * ShareReceiver — Handles ?shared= query param from PWA share target
 */
import { h } from 'preact';
import { useEffect } from 'preact/hooks';
import htm from 'htm';
import { showNotification } from '../store.js';

const html = htm.bind(h);

export function ShareReceiver() {
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const title = params.get('title');
        const text = params.get('text');
        const url = params.get('url');

        if (title || text || url) {
            handleSharedContent(title, text, url);
            // Clean URL
            window.history.replaceState({}, '', '/');
        }
    }, []);

    async function handleSharedContent(title, text, url) {
        try {
            const form = new FormData();
            if (title) form.append('title', title);
            if (text) form.append('text', text);
            if (url) form.append('url', url);

            const res = await fetch('/api/share', { method: 'POST', body: form });
            if (res.ok) {
                showNotification('Shared content saved', 'success');
            } else {
                showNotification('Failed to save shared content', 'error');
            }
        } catch {
            showNotification('Failed to save shared content', 'error');
        }
    }

    return null;
}
