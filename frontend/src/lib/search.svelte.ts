import { SvelteMap } from 'svelte/reactivity';
import { api, ApiError, type Asset, type LicenceTier } from '#lib/api/index.js';

export type ContentType = 'all' | 'image' | 'model';
export type LicenceFilter = 'all' | LicenceTier;

export interface Hit {
	source: string;
	asset: Asset;
}

export interface SearchQuery {
	sources: string[];
	q: string;
	type: ContentType;
	licence: LicenceFilter;
}

const PAGE_SIZE_SINGLE = 24;
const PAGE_SIZE_EACH = 12;
const MAX_EMPTY_PAGES = 3;

/** Interleave several result lists: a, b, c, a, b, c, … */
export function interleave<T>(lists: T[][]): T[] {
	const out: T[] = [];
	const longest = Math.max(0, ...lists.map((l) => l.length));
	for (let i = 0; i < longest; i++) {
		for (const list of lists) if (i < list.length) out.push(list[i]);
	}
	return out;
}

/**
 * Searches one or several sources and pages through them. Each source keeps
 * its own cursor; a source that fails is reported and the others go on.
 */
export class Search {
	hits = $state<Hit[]>([]);
	loading = $state(false);
	errors = $state<Record<string, string>>({});
	/** Results left out because IMPULSE doesn't accept their licence. */
	hidden = $state(0);
	/** Next offset per source; null when a source has no more results. */
	private cursors = new SvelteMap<string, number | null>();
	private controller: AbortController | null = null;
	private query: SearchQuery | null = null;

	get hasMore(): boolean {
		return [...this.cursors.values()].some((next) => next !== null);
	}

	get started(): boolean {
		return this.query !== null;
	}

	async run(query: SearchQuery): Promise<void> {
		this.controller?.abort();
		this.query = query;
		this.hits = [];
		this.errors = {};
		this.hidden = 0;
		this.cursors.clear();
		for (const source of query.sources) this.cursors.set(source, 0);
		await this.fetchNext();
	}

	async more(): Promise<void> {
		if (!this.loading && this.hasMore) await this.fetchNext();
	}

	/**
	 * Fetch the next page of every source that has more. Archives drop items
	 * without usable media after fetching, so a page can come back empty
	 * although more results exist: then keep going, a few pages at most.
	 */
	private async fetchNext(emptyPagesLeft = MAX_EMPTY_PAGES): Promise<void> {
		const query = this.query;
		if (!query) return;
		const controller = new AbortController();
		this.controller = controller;
		this.loading = true;
		const count = query.sources.length > 1 ? PAGE_SIZE_EACH : PAGE_SIZE_SINGLE;
		const pending = [...this.cursors].filter(([, next]) => next !== null) as [string, number][];

		const pages = await Promise.all(
			pending.map(async ([source, offset]) => {
				try {
					const page = await api.search(
						source,
						{
							q: query.q,
							offset,
							count,
							type: query.type === 'all' ? undefined : query.type,
							licence: query.licence === 'all' ? undefined : query.licence
						},
						controller.signal
					);
					return { source, page };
				} catch (error) {
					return { source, error };
				}
			})
		);
		if (controller.signal.aborted) return;

		const lists: Hit[][] = [];
		const errors = { ...this.errors };
		for (const result of pages) {
			if ('page' in result && result.page) {
				this.cursors.set(result.source, result.page.next_offset);
				this.hidden += result.page.hidden;
				lists.push(result.page.items.map((asset) => ({ source: result.source, asset })));
			} else {
				this.cursors.set(result.source, null);
				const error = result.error;
				if (!(error instanceof DOMException && error.name === 'AbortError')) {
					errors[result.source] =
						error instanceof ApiError ? error.message : 'This archive is not available right now.';
				}
			}
		}
		this.errors = errors;
		// Archives can shift results between pages; never show an asset twice.
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local, not state
		const seen = new Set(this.hits.map((h) => `${h.source}\u0000${h.asset.assetID}`));
		const fresh = interleave(lists).filter((h) => {
			const key = `${h.source}\u0000${h.asset.assetID}`;
			if (seen.has(key)) return false;
			seen.add(key);
			return true;
		});
		this.hits = [...this.hits, ...fresh];
		if (fresh.length === 0 && this.hasMore && emptyPagesLeft > 0) {
			await this.fetchNext(emptyPagesLeft - 1);
			return;
		}
		this.loading = false;
	}
}
