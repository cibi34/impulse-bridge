<script lang="ts">
	import type { Asset } from '#lib/api/index.js';
	import { kindLabel } from '#lib/format.js';
	import { rightsLabel, rightsUrl } from '#lib/rights.js';
	import AssetThumb from './AssetThumb.svelte';
	import Dialog from './Dialog.svelte';
	import Icon from './Icon.svelte';

	let {
		open = $bindable(false),
		asset,
		sourceName,
		selected,
		ontoggle
	}: {
		open?: boolean;
		asset: Asset | null;
		sourceName: string;
		selected?: boolean;
		/** Omit to show the asset without a select action. */
		ontoggle?: () => void;
	} = $props();

	const isUrl = (value: unknown): value is string =>
		typeof value === 'string' && /^https?:\/\//i.test(value);

	const rows = $derived(
		asset
			? ([
					['Creator', asset.creator],
					['Date', asset.date],
					['Institution', asset.contributor],
					['Rights', rightsLabel(asset.rights)],
					['Subject', asset.subject],
					['Type', asset.type],
					['Language', asset.language],
					[
						'Format',
						kindLabel(asset.contentType) + (asset.contentType ? ` (${asset.contentType})` : '')
					],
					['Source', sourceName]
				].filter(([, v]) => typeof v === 'string' && v.trim() !== '') as [string, string][])
			: []
	);
</script>

<Dialog bind:open title={asset?.title || 'Untitled'} size="lg">
	{#if asset}
		<div class="layout">
			<div class="preview">
				<AssetThumb
					src={asset.previewURI}
					contentType={asset.contentType}
					alt={asset.title ?? ''}
					eager
				/>
			</div>
			<div class="info">
				{#if asset.description}
					<p class="description">{asset.description}</p>
				{/if}
				<dl>
					{#each rows as [label, value] (label)}
						<div>
							<dt>{label}</dt>
							<dd>
								{#if label === 'Rights' && rightsUrl(asset.rights)}<a
										href={rightsUrl(asset.rights)}
										target="_blank"
										rel="noopener noreferrer">{value}</a
									>{:else if isUrl(value)}<a href={value} target="_blank" rel="noopener noreferrer"
										>{value}</a
									>{:else}{value}{/if}
							</dd>
						</div>
					{/each}
				</dl>
				<div class="links">
					{#if isUrl(asset.identifier)}
						<a class="btn btn-sm" href={asset.identifier} target="_blank" rel="noopener noreferrer">
							<Icon name="external" size={16} /> View at the source
						</a>
					{/if}
					{#if isUrl(asset.assetURI)}
						<a
							class="btn btn-sm btn-plain"
							href={asset.assetURI}
							target="_blank"
							rel="noopener noreferrer"
						>
							<Icon name="link" size={16} /> Original file
						</a>
					{/if}
				</div>
			</div>
		</div>
	{/if}
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (open = false)}>Close</button>
		{#if ontoggle}
			<button
				type="button"
				class="btn {selected ? '' : 'btn-primary'}"
				aria-pressed={selected}
				onclick={ontoggle}
			>
				<Icon name={selected ? 'check' : 'plus'} size={16} />
				{selected ? 'Selected' : 'Add to selection'}
			</button>
		{/if}
	{/snippet}
</Dialog>

<style>
	.layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		gap: 24px;
		align-items: start;
	}

	.preview {
		aspect-ratio: 1;
		border-radius: var(--radius-media);
		overflow: hidden;
		background: var(--surface-sunken);
	}

	.preview :global(img) {
		object-fit: contain;
		background: var(--surface-sunken);
	}

	.info {
		display: flex;
		flex-direction: column;
		gap: 16px;
		min-width: 0;
	}

	.description {
		color: var(--text-2);
		display: -webkit-box;
		-webkit-line-clamp: 6;
		line-clamp: 6;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	dl {
		margin: 0;
		display: flex;
		flex-direction: column;
	}

	dl div {
		display: grid;
		grid-template-columns: 110px minmax(0, 1fr);
		gap: 12px;
		padding: 8px 0;
		border-bottom: 1px solid var(--separator);
		font-size: 14px;
	}

	dt {
		color: var(--text-3);
	}

	dd {
		margin: 0;
		overflow-wrap: anywhere;
	}

	.links {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	@media (max-width: 720px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
		.preview {
			aspect-ratio: 4 / 3;
		}
	}
</style>
