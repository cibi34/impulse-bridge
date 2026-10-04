<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { api, errorMessage, type Collection, type Failure } from '#lib/api/index.js';
	import AssetCard from '#lib/components/AssetCard.svelte';
	import AssetDialog from '#lib/components/AssetDialog.svelte';
	import CreateCollectionDialog from '#lib/components/CreateCollectionDialog.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import SearchField from '#lib/components/SearchField.svelte';
	import SegmentedControl from '#lib/components/SegmentedControl.svelte';
	import SelectionBar from '#lib/components/SelectionBar.svelte';
	import SelectionDialog from '#lib/components/SelectionDialog.svelte';
	import { plural } from '#lib/format.js';
	import { Search, type ContentType, type Hit, type LicenceFilter } from '#lib/search.svelte.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { selection } from '#lib/stores/selection.svelte.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';

	const search = new Search();

	// ---- URL state: /explore?source=…&q=…&type=…&licence=…&add=<collection id> ----
	const sourceParam = $derived(page.url.searchParams.get('source') ?? 'all');
	const q = $derived(page.url.searchParams.get('q') ?? '');
	const type = $derived((page.url.searchParams.get('type') as ContentType | null) ?? 'all');
	const licence = $derived((page.url.searchParams.get('licence') as LicenceFilter | null) ?? 'all');
	const addTo = $derived(page.url.searchParams.get('add'));

	let query = $state('');
	let typeValue = $state<ContentType>('all');
	$effect(() => {
		query = q;
		typeValue = type;
	});

	const activeSources = $derived(
		sourceParam === 'all'
			? app.sources.map((s) => s.id)
			: app.sources.some((s) => s.id === sourceParam)
				? [sourceParam]
				: []
	);

	// Search again when the query in the URL changes — and only then: the
	// search itself reads and writes its own state, which must not re-trigger
	// this effect.
	$effect(() => {
		const query = { sources: activeSources, q, type, licence };
		if (query.sources.length > 0) untrack(() => search.run(query));
	});

	function navigate(changes: Record<string, string | null>, replace = false) {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- builds a URL, not state
		const params = new URLSearchParams(page.url.search);
		for (const [key, value] of Object.entries(changes)) {
			if (value === null || value === '' || value === 'all') params.delete(key);
			else params.set(key, value);
		}
		const qs = params.toString();
		goto(qs ? resolve(`explore?${qs}`) : resolve('explore'), { reset: false, replace });
	}

	// ---- adding to an existing collection ----
	let target = $state<Collection | null>(null);
	$effect(() => {
		const id = addTo;
		target = null;
		if (id) {
			api
				.collection(id, library.keyFor(id))
				.then((c) => {
					if (c.id !== id) {
						library.follow(id, c.id);
						navigate({ add: c.id }, true);
						return;
					}
					target = c.can_edit ? c : null;
				})
				.catch(() => (target = null));
		}
	});

	// ---- dialogs ----
	let detail = $state<Hit | null>(null);
	let detailOpen = $state(false);
	let reviewOpen = $state(false);
	let createOpen = $state(false);
	let adding = $state(false);

	function openDetail(hit: Hit) {
		detail = hit;
		detailOpen = true;
	}

	// ---- size limit: a collection holds at most `limit` assets ----
	const limit = $derived(app.config?.max_assets_per_collection ?? 50);
	const room = $derived(target ? Math.max(0, limit - target.item_count) : limit);

	function toggle(hit: Hit) {
		if (!selection.has(hit.source, hit.asset.assetID) && selection.count >= room) {
			toasts.error(
				target
					? `“${target.name}” has room for ${plural(room, 'more asset')}.`
					: `A collection holds up to ${limit} assets.`
			);
			return;
		}
		selection.toggle(hit.source, hit.asset);
	}

	async function primaryAction() {
		if (!target) {
			createOpen = true;
			return;
		}
		adding = true;
		try {
			const result = await api.addItems(target.id, library.keyFor(target.id), selection.refs());
			selection.clear();
			reportFailures(result.failed);
			toasts.success(`${plural(result.added.length, 'asset')} added to “${target.name}”`);
			goto(resolve(`c/${target.id}/edit`));
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			adding = false;
		}
	}

	function reportFailures(failed: Failure[]) {
		if (failed.length > 0) {
			toasts.error(
				`${plural(failed.length, 'asset')} could not be added (${failed[0].reason.toLowerCase()}).`
			);
		}
	}

	function created(result: { collection: Collection; editKey: string; failed: Failure[] }) {
		library.save(result.collection.id, result.collection.name, result.editKey);
		selection.clear();
		reportFailures(result.failed);
		toasts.success(`Collection “${result.collection.name}” created`);
		goto(resolve(`c/${result.collection.id}/edit`));
	}

	const actionLabel = $derived(target ? `Add to “${target.name}”` : 'Create collection');
	const errorEntries = $derived(Object.entries(search.errors));
	const statusText = $derived(
		search.loading && search.hits.length === 0
			? 'Searching…'
			: search.hits.length === 0
				? ''
				: `${plural(search.hits.length, 'result')}${q ? ` for “${q}”` : ''}`
	);
	const sourceTitle = $derived(sourceParam === 'all' ? 'All sources' : app.sourceName(sourceParam));
</script>

<svelte:head>
	<title>Explore — IMPULSE Curator</title>
</svelte:head>

<header class="head">
	{#if target}
		<div class="adding" role="status">
			<Icon name="plus" size={16} />
			<span>Adding to <strong>{target.name}</strong></span>
			<a class="btn btn-plain btn-sm" href={resolve(`c/${target.id}/edit`)}>Done</a>
		</div>
	{/if}
	<div class="title-row">
		<div class="titles">
			<h1 class="large-title">Explore</h1>
			<p class="secondary">Search open cultural heritage and pick assets for your collection.</p>
		</div>
		<div class="search">
			<SearchField
				bind:value={query}
				label="Search {sourceTitle}"
				placeholder="Search {sourceTitle.toLowerCase() === 'all sources'
					? 'all archives'
					: sourceTitle}"
				onsubmit={(value) => navigate({ q: value })}
			/>
		</div>
	</div>
	<div class="filter-row">
		<label class="source-select">
			<span class="visually-hidden">Archive</span>
			<select
				class="input"
				value={sourceParam}
				onchange={(e) => navigate({ source: e.currentTarget.value })}
			>
				<option value="all">All sources</option>
				{#each app.sources as source (source.id)}
					<option value={source.id}>{source.name ?? source.id}</option>
				{/each}
			</select>
		</label>
		<label class="licence-select">
			<span class="visually-hidden">Licence</span>
			<select
				class="input"
				value={licence}
				onchange={(e) => navigate({ licence: e.currentTarget.value }, true)}
			>
				<option value="all">Any accepted licence</option>
				<option value="by">Public domain, CC0 and CC BY</option>
				<option value="free">Public domain and CC0 only</option>
			</select>
		</label>
		<SegmentedControl
			legend="Content type"
			options={[
				{ value: 'all', label: 'All' },
				{ value: 'image', label: 'Images' },
				{ value: 'model', label: '3D models' }
			]}
			bind:value={typeValue}
			onchange={(value) => navigate({ type: value }, true)}
		/>
		<p class="status footnote secondary" role="status" aria-live="polite">{statusText}</p>
	</div>
</header>

<section class="results" aria-labelledby="results-title" aria-busy={search.loading}>
	<h2 id="results-title" class="visually-hidden">Results</h2>
	{#if app.sourcesError}
		<p class="notice" role="alert">{app.sourcesError}</p>
	{/if}
	{#each errorEntries as [source, message] (source)}
		<p class="notice" role="alert">
			<Icon name="alert" size={16} />
			<span><strong>{app.sourceName(source)}:</strong> {message}</span>
		</p>
	{/each}

	{#if search.hits.length > 0}
		<ul class="grid">
			{#each search.hits as hit (hit.source + '\u0000' + hit.asset.assetID)}
				<li>
					<AssetCard
						asset={hit.asset}
						sourceName={app.sourceName(hit.source)}
						selected={selection.has(hit.source, hit.asset.assetID)}
						ontoggle={() => toggle(hit)}
						onopen={() => openDetail(hit)}
					/>
				</li>
			{/each}
		</ul>
	{:else if search.loading || !app.ready}
		<ul class="grid" aria-hidden="true">
			{#each Array.from({ length: 12 }, (_, i) => i) as i (i)}
				<li class="skeleton"><span></span><span></span><span></span></li>
			{/each}
		</ul>
	{:else if search.started && search.hidden > 0}
		<div class="empty">
			<Icon name="info" size={32} />
			<h2 class="headline">No results with an accepted licence{q ? ` for “${q}”` : ''}</h2>
			<p class="secondary">
				{plural(search.hidden, 'result')}
				{search.hidden === 1 ? 'was' : 'were'} left out: their licence isn't accepted for IMPULSE collections,
				or their rights are unclear.
			</p>
		</div>
	{:else if search.started}
		<div class="empty">
			<Icon name="search" size={32} />
			<h2 class="headline">No results{q ? ` for “${q}”` : ''}</h2>
			<p class="secondary">
				Try other words, another archive, “All” content types{licence !== 'all'
					? ', or any accepted licence'
					: ''}.
			</p>
		</div>
	{/if}

	{#if search.hidden > 0 && search.hits.length > 0 && !search.loading}
		<p class="hidden-note footnote tertiary">
			<Icon name="info" size={16} />
			<span>
				{plural(search.hidden, 'result')} left out: their licence isn't accepted for IMPULSE collections,
				or their rights are unclear.
			</span>
		</p>
	{/if}

	{#if search.hasMore && search.hits.length > 0}
		<div class="more">
			<button type="button" class="btn" disabled={search.loading} onclick={() => search.more()}>
				{search.loading ? 'Loading…' : 'Show more'}
			</button>
		</div>
	{/if}
</section>

<SelectionBar
	{actionLabel}
	limit={room}
	busy={adding}
	onaction={primaryAction}
	onreview={() => (reviewOpen = true)}
/>

<AssetDialog
	bind:open={detailOpen}
	asset={detail?.asset ?? null}
	sourceName={detail ? app.sourceName(detail.source) : ''}
	selected={detail ? selection.has(detail.source, detail.asset.assetID) : false}
	ontoggle={() => detail && toggle(detail)}
/>
<SelectionDialog bind:open={reviewOpen} {actionLabel} onaction={primaryAction} />
<CreateCollectionDialog bind:open={createOpen} oncreated={created} />

<style>
	.head {
		position: sticky;
		top: 0;
		z-index: 5;
		display: flex;
		flex-direction: column;
		gap: 18px;
		padding: 28px var(--gutter) 18px;
		background: var(--glass);
		backdrop-filter: saturate(180%) blur(20px);
		-webkit-backdrop-filter: saturate(180%) blur(20px);
		border-bottom: 1px solid var(--separator);
	}

	.adding {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 6px 6px 6px 14px;
		border-radius: 12px;
		background: var(--accent-soft);
		color: var(--accent-text);
		font-size: 14px;
	}

	.adding strong {
		color: var(--text);
	}

	.adding a {
		margin-left: auto;
	}

	.title-row {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 24px;
		flex-wrap: wrap;
	}

	.titles {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.search {
		flex: 0 1 400px;
		min-width: 240px;
	}

	.filter-row {
		display: flex;
		align-items: center;
		gap: 12px 16px;
		flex-wrap: wrap;
	}

	.source-select {
		display: none;
	}

	.licence-select select {
		min-height: 36px;
		padding-block: 6px;
		font-size: 14px;
	}

	.hidden-note {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		margin-top: 28px;
		text-align: center;
	}

	.status {
		margin-left: auto;
	}

	.results {
		padding: 28px var(--gutter) 140px;
	}

	.notice {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 18px;
		padding: 10px 14px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 14px;
	}

	.notice strong {
		font-weight: 600;
	}

	.grid {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
		gap: 28px 22px;
	}

	.skeleton {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.skeleton span {
		border-radius: 8px;
		background: var(--surface);
		animation: pulse 1.4s ease-in-out infinite;
	}

	.skeleton span:nth-child(1) {
		aspect-ratio: 4 / 5;
		border-radius: var(--radius-media);
	}

	.skeleton span:nth-child(2) {
		height: 14px;
		width: 80%;
	}

	.skeleton span:nth-child(3) {
		height: 12px;
		width: 55%;
	}

	@keyframes pulse {
		50% {
			opacity: 0.5;
		}
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 72px 16px;
		text-align: center;
		color: var(--text-3);
	}

	.empty h2 {
		color: var(--text);
	}

	.more {
		display: flex;
		justify-content: center;
		margin-top: 36px;
	}

	@media (max-width: 900px) {
		.head {
			position: static;
			padding-top: 20px;
		}
		.source-select {
			display: block;
			flex: 1 1 180px;
		}
		.status {
			margin-left: 0;
			width: 100%;
		}
		.grid {
			grid-template-columns: repeat(auto-fill, minmax(min(150px, 45%), 1fr));
			gap: 20px 12px;
		}
	}
</style>
