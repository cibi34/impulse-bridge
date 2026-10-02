<script lang="ts">
	import { rightsLabel } from '#lib/rights.js';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import {
		api,
		ApiError,
		errorMessage,
		type Collection,
		type CollectionItem
	} from '#lib/api/index.js';
	import AssetDialog from '#lib/components/AssetDialog.svelte';
	import AssetThumb from '#lib/components/AssetThumb.svelte';
	import CopyField from '#lib/components/CopyField.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import { kindLabel, plural, timeAgo } from '#lib/format.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';

	const id = $derived(page.params.id ?? '');
	let collection = $state<Collection | null>(null);
	let error = $state<string | null>(null);
	let detail = $state<CollectionItem | null>(null);
	let detailOpen = $state(false);

	$effect(() => {
		const current = id;
		collection = null;
		error = null;
		api
			.collection(current, library.keyFor(current))
			.then((c) => (collection = c))
			.catch(
				(e) => (error = e instanceof ApiError && e.status === 404 ? 'not-found' : errorMessage(e))
			);
	});

	// The public view shows what Unity gets: published assets only.
	const items = $derived(collection?.items.filter((i) => i.published) ?? []);
</script>

<svelte:head>
	<title>{collection?.name ?? 'Collection'} — IMPULSE Curator</title>
</svelte:head>

<div class="page">
	{#if error === 'not-found'}
		<div class="empty">
			<h1 class="title">This collection doesn't exist</h1>
			<p class="secondary">It may have been deleted, or the link is incomplete.</p>
			<a class="btn btn-primary" href={resolve('explore')}>Explore</a>
		</div>
	{:else if error}
		<p class="notice" role="alert">{error}</p>
	{:else if collection}
		<header class="head">
			<div class="titles">
				<p class="eyebrow">Collection</p>
				<h1 class="large-title">{collection.name}</h1>
				{#if collection.description}<p class="secondary lead">{collection.description}</p>{/if}
				<div class="pills">
					<span class="pill">{plural(items.length, 'asset')}</span>
					<span class="pill">Updated {timeAgo(collection.updated_at)}</span>
					{#if collection.organization}<span class="pill">{collection.organization}</span>{/if}
				</div>
			</div>
			{#if collection.can_edit}
				<a class="btn btn-primary" href={resolve(`c/${id}/edit`)}>
					<Icon name="collections" size={16} /> Edit collection
				</a>
			{/if}
		</header>

		<div class="uri">
			<CopyField label="Collection URL for IMPULSE" value={collection.uri} />
		</div>

		{#if items.length > 0}
			<ul class="grid">
				{#each items as item (item.asset_id)}
					<li>
						<button
							type="button"
							class="card"
							onclick={() => {
								detail = item;
								detailOpen = true;
							}}
						>
							<span class="media">
								<AssetThumb src={item.asset.previewURI} contentType={item.asset.contentType} />
								<span class="kind">{kindLabel(item.asset.contentType)}</span>
							</span>
							<span class="name">{item.asset.title || 'Untitled'}</span>
							<span class="meta">
								{[item.asset.creator, rightsLabel(item.asset.rights)].filter(Boolean).join(' · ') ||
									app.sourceName(item.source)}
							</span>
						</button>
					</li>
				{/each}
			</ul>
		{:else}
			<div class="empty"><p class="secondary">This collection has no assets yet.</p></div>
		{/if}

		<p class="caption tertiary report">
			Rights stay with the institutions that hold the works; each asset lists its licence and
			source. Something wrong with this collection? <a href={resolve('report')}>Report it</a>.
		</p>
	{:else}
		<p class="secondary" role="status">Loading…</p>
	{/if}
</div>

<AssetDialog
	bind:open={detailOpen}
	asset={detail?.asset ?? null}
	sourceName={detail ? app.sourceName(detail.source) : ''}
/>

<style>
	.page {
		padding: 32px var(--gutter) 72px;
	}

	.head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 24px;
		flex-wrap: wrap;
		margin-bottom: 24px;
	}

	.titles {
		display: flex;
		flex-direction: column;
		gap: 8px;
		max-width: 760px;
	}

	.lead {
		font-size: 17px;
	}

	.pills {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		margin-top: 4px;
	}

	.uri {
		max-width: 560px;
		margin-bottom: 32px;
	}

	.grid {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(196px, 1fr));
		gap: 28px 22px;
	}

	.card {
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: 100%;
		padding: 0;
		border: 0;
		background: none;
		color: var(--text);
		text-align: left;
	}

	.media {
		position: relative;
		display: block;
		aspect-ratio: 4 / 5;
		border-radius: var(--radius-media);
		overflow: hidden;
		background: var(--surface);
		transition: transform 0.15s ease;
	}

	.card:hover .media {
		transform: translateY(-2px);
	}

	.kind {
		position: absolute;
		left: 10px;
		bottom: 10px;
		padding: 3px 8px;
		border-radius: 999px;
		background: rgb(18 18 20 / 0.72);
		color: #e6e6ea;
		font-size: 11px;
		font-weight: 500;
	}

	.name {
		font-size: 14px;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meta {
		font-size: 12px;
		color: var(--text-3);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.report {
		margin-top: 40px;
	}

	@media (max-width: 600px) {
		.grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 20px 12px;
		}
	}

	.notice {
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		margin: 64px auto;
		text-align: center;
	}
</style>
