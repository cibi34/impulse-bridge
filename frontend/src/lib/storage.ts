/**
 * localStorage access that never throws (private mode, blocked storage, SSR).
 *
 * Nothing is written before the visitor does something that needs it
 * (selecting an asset, creating or opening a collection, choosing an
 * appearance) — storage that is strictly necessary for a service the user
 * asked for needs no consent (§ 25 (2) TDDDG).
 */

export function readJSON<T>(key: string, fallback: T): T {
	try {
		const raw = globalThis.localStorage?.getItem(key);
		return raw ? (JSON.parse(raw) as T) : fallback;
	} catch {
		return fallback;
	}
}

export function writeJSON(key: string, value: unknown): void {
	try {
		globalThis.localStorage?.setItem(key, JSON.stringify(value));
	} catch {
		/* storage full or unavailable: the app keeps working in memory */
	}
}

export function readString(key: string): string | null {
	try {
		return globalThis.localStorage?.getItem(key) ?? null;
	} catch {
		return null;
	}
}

export function writeString(key: string, value: string): void {
	try {
		globalThis.localStorage?.setItem(key, value);
	} catch {
		/* ignore */
	}
}

export function remove(key: string): void {
	try {
		globalThis.localStorage?.removeItem(key);
	} catch {
		/* ignore */
	}
}
