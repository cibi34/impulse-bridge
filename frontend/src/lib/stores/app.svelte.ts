import { api, type AppConfig, type Source } from '#lib/api/index.js';

/** Server configuration, configured sources and the signed-in email. */
class AppState {
	config = $state<AppConfig | null>(null);
	sources = $state<Source[]>([]);
	email = $state<string | null>(null);
	ready = $state(false);
	sourcesError = $state<string | null>(null);

	private loading: Promise<void> | null = null;

	load(): Promise<void> {
		this.loading ??= this.fetchAll();
		return this.loading;
	}

	private async fetchAll(): Promise<void> {
		const [config, sources, me] = await Promise.allSettled([api.config(), api.sources(), api.me()]);
		if (config.status === 'fulfilled') this.config = config.value;
		if (sources.status === 'fulfilled') this.sources = sources.value;
		else this.sourcesError = 'The archives could not be loaded. Please reload the page.';
		if (me.status === 'fulfilled') this.email = me.value.email;
		this.ready = true;
	}

	sourceName(id: string): string {
		return this.sources.find((s) => s.id === id)?.name ?? id;
	}

	/** A stable dot color per source, from the brand palette. */
	sourceColor(id: string): string {
		const palette = ['#72a1d6', '#c567a9', '#f7e240', '#ec008c', '#5fdc83', '#8fb8e6'];
		const index = this.sources.findIndex((s) => s.id === id);
		return palette[(index < 0 ? 0 : index) % palette.length];
	}
}

export const app = new AppState();
