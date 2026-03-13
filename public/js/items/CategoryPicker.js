/**
 * CategoryPicker — Dropdown with existing categories + inline "Add new" option
 */
import { h } from 'preact';
import { useState } from 'preact/hooks';
import htm from 'htm';
import { categories, loadCategories, showNotification } from '../store.js';

const html = htm.bind(h);

export function CategoryPicker({ value, onChange }) {
    const [adding, setAdding] = useState(false);
    const [newName, setNewName] = useState('');
    const [newColor, setNewColor] = useState('#6b7280');

    const onSelect = (e) => {
        const val = e.target.value;
        if (val === '__new__') {
            setAdding(true);
        } else {
            onChange(val);
        }
    };

    const onCreateNew = async () => {
        const name = newName.trim();
        if (!name) return;
        try {
            await fetch('/share/api/categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, color: newColor }),
            });
            await loadCategories();
            onChange(name);
            setAdding(false);
            setNewName('');
            showNotification(`Created "${name}"`, 'success');
        } catch {
            showNotification('Failed to create category', 'error');
        }
    };

    const onCancelNew = () => {
        setAdding(false);
        setNewName('');
    };

    if (adding) {
        return html`
            <div class="cat-picker-new">
                <div class="cat-picker-new-row">
                    <input class="form-input" value=${newName}
                        onInput=${e => setNewName(e.target.value)}
                        placeholder="Category name" autofocus/>
                    <input type="color" class="color-input" value=${newColor}
                        onInput=${e => setNewColor(e.target.value)}/>
                </div>
                <div class="cat-picker-new-actions">
                    <button class="btn-sm-secondary" onClick=${onCancelNew}>Cancel</button>
                    <button class="btn-sm-primary" onClick=${onCreateNew}
                        disabled=${!newName.trim()}>Add</button>
                </div>
            </div>
        `;
    }

    return html`
        <select class="form-select" value=${value} onChange=${onSelect}>
            <option value="">No category</option>
            ${categories.value.map(c => html`
                <option key=${c.name} value=${c.name}>${c.name}</option>
            `)}
            <option value="__new__">+ New category...</option>
        </select>
    `;
}
