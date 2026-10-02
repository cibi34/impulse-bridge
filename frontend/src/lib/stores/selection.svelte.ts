import { browser } from '$app/env';
import type { Asset, AssetRef } from '#lib/api/index.js';
import { readJSON, remove, writeJSON } from '#lib/storage.js';

const STORAGE_KEY = 'curator-selection';

/** What we keep of a selected asset: enough to show it without refetching. */
export interface SelectedAsset {
	key: string;
	source: string;
	asset: Pick<Asset, 'assetID' | 'title' | 'creator' | 'rights' | 'previewURI' | 'contentType'>;
}

export function assetKey(source: string, assetId: string): string {
	return `${source}\u0000${assetId}`;
}

/** Assets picked while exploring; survives reloads and source switches. */
class Selection {
	items = $state<SelectedAsset[]>([]);

	constructor() {
		if (browser) this.items = readJSON<SelectedAsset[]>(STORAGE_KEY, []);
	}

	get count(): number {
		return this.items.length;
	}

	has(source: string, assetId: string): boolean {
		const key = assetKey(source, assetId);
		return this.items.some((item) => item.key === key);
	}

	toggle(source: string, asset: Asset): boolean {
		const key = assetKey(source, asset.assetID);
		if (this.items.some((item) => item.key === key)) {
			this.items = this.items.filter((item) => item.key !== key);
			this.persist();
			return false;
		}
		const { assetID, title, creator, rights, previewURI, contentType } = asset;
		this.items = [
			...this.items,
			{ key, source, asset: { assetID, title, creator, rights, previewURI, contentType } }
		];
		this.persist();
		return true;
	}

	remove(key: string): void {
		this.items = this.items.filter((item) => item.key !== key);
		this.persist();
	}

	clear(): void {
		this.items = [];
		this.persist();
	}

	refs(): AssetRef[] {
		return this.items.map((item) => ({ source: item.source, asset_id: item.asset.assetID }));
	}

	private persist(): void {
		if (this.items.length > 0) writeJSON(STORAGE_KEY, this.items);
		else remove(STORAGE_KEY);
	}
}

export const selection = new Selection();
