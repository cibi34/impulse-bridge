import { browser } from '$app/env';
import { readJSON, remove, writeJSON } from '#lib/storage.js';

const STORAGE_KEY = 'curator-library';

/** A collection this browser created or opened with its edit link. */
export interface LibraryEntry {
	id: string;
	name: string;
	/** The edit key; null when the collection was only viewed. */
	key: string | null;
	savedAt: string;
}

class Library {
	entries = $state<LibraryEntry[]>([]);

	constructor() {
		if (browser) this.entries = readJSON<LibraryEntry[]>(STORAGE_KEY, []);
	}

	get(id: string): LibraryEntry | undefined {
		return this.entries.find((entry) => entry.id === id);
	}

	keyFor(id: string): string | null {
		return this.get(id)?.key ?? null;
	}

	/** Add or update; a known key is never replaced by "no key". */
	save(id: string, name: string, key: string | null): void {
		const existing = this.get(id);
		const entry: LibraryEntry = {
			id,
			name,
			key: key ?? existing?.key ?? null,
			savedAt: existing?.savedAt ?? new Date().toISOString()
		};
		this.entries = [entry, ...this.entries.filter((e) => e.id !== id)];
		this.persist();
	}

	rename(id: string, name: string): void {
		const existing = this.get(id);
		if (existing && existing.name !== name) {
			this.entries = this.entries.map((e) => (e.id === id ? { ...e, name } : e));
			this.persist();
		}
	}

	setKey(id: string, key: string): void {
		this.entries = this.entries.map((e) => (e.id === id ? { ...e, key } : e));
		this.persist();
	}

	forget(id: string): void {
		this.entries = this.entries.filter((e) => e.id !== id);
		this.persist();
	}

	private persist(): void {
		if (this.entries.length > 0) writeJSON(STORAGE_KEY, this.entries);
		else remove(STORAGE_KEY);
	}
}

export const library = new Library();
