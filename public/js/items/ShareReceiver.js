/**
 * ShareReceiver — Handles ?title=&text=&url= query params from PWA share target
 * Falls back to local queue when offline, drains queue on reconnect.
 */
import { h } from 'preact';
import { useEffect } from 'preact/hooks';
import htm from 'htm';
import { showNotification, queueShare, processShareQueue } from '../store.js';

const html = htm.bind(h);

export function ShareReceiver() {
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const title = params.get('title');
        const text = params.get('text');
        const url = params.get('url');

        if (title || text || url) {
            handleSharedContent(title, text, url);
            window.history.replaceState({}, '', '/share/');
        }

        // Also tell SW to drain its queue
        if (navigator.serviceWorker && navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage('drain-share-queue');
        }
    }, []);

    async function handleSharedContent(title, text, url) {
        if (!navigator.onLine) {
            // Queue locally for later
            await queueShare({ title, text, url });
            showNotification('Shared content queued (offline)', 'warning');
            return;
        }

        try {
            const form = new FormData();
            if (title) form.append('title', title);
            if (text) form.append('text', text);
            if (url) form.append('url', url);

            const res = await fetch('/share/api/share', { method: 'POST', body: form });
            if (res.ok) {
                showNotification('Shared content saved', 'success');
            } else {
                // Might be queued by SW (202)
                const data = await res.json().catch(() => null);
                if (data?.queued) {
                    showNotification('Queued offline, will sync later', 'warning');
                } else {
                    showNotification('Failed to save shared content', 'error');
                }
            }
        } catch {
            // Offline — queue it
            await queueShare({ title, text, url });
            showNotification('Shared content queued (offline)', 'warning');
        }
    }

    return null;
}
