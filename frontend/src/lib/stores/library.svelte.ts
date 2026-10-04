import { browser } from '$app/env';
import { api, type Summaries } from '#lib/api/index.js';
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
	private synced = false;

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

	/**
	 * An admin gave a collection a new id; the server still finds it by the
	 * old one and answers with the new one. Move what this browser stored
	 * (name, edit key) over to the new id. Returns whether anything moved.
	 */
	follow(oldId: string, newId: string): boolean {
		if (oldId === newId) return false;
		const old = this.get(oldId);
		if (!old) return false;
		const current = this.get(newId);
		const merged: LibraryEntry = {
			...old,
			...current,
			id: newId,
			key: current?.key ?? old.key
		};
		this.entries = [merged, ...this.entries.filter((e) => e.id !== oldId && e.id !== newId)];
		this.persist();
		return true;
	}

	/**
	 * Bring what this browser stored in line with the server's answer:
	 * follow renamed collections, take over current names, and forget
	 * collections that were deleted. Locked ones still exist and are kept.
	 */
	apply({ collections, moved, missing }: Summaries): void {
		for (const [from, to] of Object.entries(moved)) this.follow(from, to);
		for (const c of collections) this.rename(c.id, c.name);
		for (const id of missing) this.forget(id);
	}

	/** Check the stored collections against the server, once per visit. */
	async sync(): Promise<void> {
		if (this.synced || this.entries.length === 0) return;
		this.synced = true;
		try {
			this.apply(await api.summaries(this.entries.map((e) => e.id)));
		} catch {
			this.synced = false; // offline or failing: keep everything, try again later
		}
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
