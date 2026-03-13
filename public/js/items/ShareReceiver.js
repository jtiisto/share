/**
 * ShareReceiver — Handles share target results and offline queue draining.
 *
 * The manifest share_target POSTs to /share/, which the service worker intercepts,
 * forwards to the backend API (or queues offline), and redirects here with a
 * ?shared=success|error|queued query param. This component reads that param
 * and shows the appropriate notification.
 */
import { h } from 'preact';
import { useEffect } from 'preact/hooks';
import htm from 'htm';
import { showNotification } from '../store.js';

const html = htm.bind(h);

export function ShareReceiver() {
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const shared = params.get('shared');

        if (shared) {
            if (shared === 'success') {
                showNotification('Shared content saved', 'success');
            } else if (shared === 'queued') {
                showNotification('Queued offline, will sync later', 'warning');
            } else if (shared === 'error') {
                showNotification('Failed to save shared content', 'error');
            }
            window.history.replaceState({}, '', '/share/');
        }

        // Tell SW to drain its offline queue (in case items were queued earlier)
        if (navigator.serviceWorker && navigator.serviceWorker.controller) {
            navigator.serviceWorker.controller.postMessage('drain-share-queue');
        }
    }, []);

    return null;
}
