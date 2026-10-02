import { browser } from '$app/env';
import { readString, writeString } from '#lib/storage.js';

export type Appearance = 'dark' | 'light' | 'system';

const STORAGE_KEY = 'curator-theme';

class Theme {
	value = $state<Appearance>('dark');

	constructor() {
		if (browser) {
			const saved = readString(STORAGE_KEY);
			if (saved === 'light' || saved === 'system') this.value = saved;
		}
	}

	set(value: Appearance): void {
		this.value = value;
		document.documentElement.setAttribute('data-theme', value);
		writeString(STORAGE_KEY, value);
	}
}

export const theme = new Theme();
