/**
 * ItemsView — File list with category filter + pinned section + category management
 */
import { h } from 'preact';
import { useEffect } from 'preact/hooks';
import htm from 'htm';
import { items, categories, loadCategories, selectedCategory } from '../store.js';
import { ItemCard } from './ItemCard.js';

const html = htm.bind(h);

export function ItemsView() {
    useEffect(() => {
        loadCategories();
    }, []);

    const allItems = items.value.filter(i => i.type === 'file');
    const cat = selectedCategory.value;
    const filtered = cat ? allItems.filter(i => i.category === cat) : allItems;
    const pinned = filtered.filter(i => i.pinned);
    const unpinned = filtered.filter(i => !i.pinned);

    return html`
        <div>
            <div class="category-filter">
                <button class="category-chip ${!cat ? 'active' : ''}"
                    onClick=${() => { selectedCategory.value = null; }}>All</button>
                ${categories.value.map(c => html`
                    <button key=${c.name}
                        class="category-chip ${cat === c.name ? 'active' : ''}"
                        style=${c.color ? `--chip-color: ${c.color}` : ''}
                        onClick=${() => { selectedCategory.value = c.name; }}>
                        ${c.color ? html`<span class="cat-color-dot" style="background:${c.color}; width:8px; height:8px; display:inline-block; margin-right:4px; vertical-align:middle;"></span>` : null}
                        ${c.name}
                    </button>
                `)}
            </div>

            ${filtered.length === 0 && html`
                <div class="empty-state">
                    <div class="empty-state-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                    </div>
                    <p>No files yet</p>
                    <p style="font-size: var(--font-size-sm); margin-top: 4px;">Upload files or drop them into the content directory</p>
                </div>
            `}

            <div class="item-list">
                ${pinned.map(item => html`<${ItemCard} key=${item.id} item=${item}/>`)}
                ${unpinned.map(item => html`<${ItemCard} key=${item.id} item=${item}/>`)}
            </div>
        </div>
    `;
}
