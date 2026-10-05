<script lang="ts">
	import type { Asset, Licence } from '#lib/api/index.js';
	import {
		dimensionsLabel,
		fileSizeLabel,
		isModel,
		kindLabel,
		megapixelsLabel
	} from '#lib/format.js';
	import { previewSrc } from '#lib/images.js';
	import { conditionsText, licenceLabel } from '#lib/licences.js';
	import AssetThumb from './AssetThumb.svelte';
	import Dialog from './Dialog.svelte';
	import Icon from './Icon.svelte';
	import ModelViewer from './ModelViewer.svelte';

	let {
		open = $bindable(false),
		asset,
		licence,
		sourceName,
		selected,
		included = false,
		ontoggle
	}: {
		open?: boolean;
		asset: Asset | null;
		/** The asset's licence when it isn't on the asset (collection items). */
		licence?: Licence | null;
		sourceName: string;
		selected?: boolean;
		/** Already in the collection being added to. */
		included?: boolean;
		/** Omit to show the asset without a select action. */
		ontoggle?: () => void;
	} = $props();

	const isUrl = (value: unknown): value is string =>
		typeof value === 'string' && /^https?:\/\//i.test(value);

	const assetLicence = $derived(licence ?? asset?.licence ?? null);
	const model = $derived(isModel(asset?.contentType));
	// The 3D viewer loads the model file (and its code) only when asked.
	let viewer = $state<'closed' | 'open'>('closed');
	$effect(() => {
		void asset?.assetID;
		viewer = 'closed';
	});
	const resolution = $derived.by(() => {
		const dims = asset ? dimensionsLabel(asset.width, asset.height) : null;
		if (!dims) return null;
		const mp = megapixelsLabel(asset!.width, asset!.height);
		return `${dims} px${mp ? ` (${mp})` : ''}`;
	});

	const rows = $derived(
		asset
			? ([
					['Creator', asset.creator],
					['Date', asset.date],
					['Place', asset.coverage],
					['Institution', asset.contributor],
					['Licence', assetLicence?.label ?? licenceLabel(asset)],
					['Subject', asset.subject],
					['Type', asset.type],
					['Language', asset.language],
					[
						'Media',
						kindLabel(asset.contentType) + (asset.contentType ? ` (${asset.contentType})` : '')
					],
					['Resolution', resolution],
					['File size', fileSizeLabel(asset.fileSize)],
					['Format', asset.format],
					['Source', sourceName]
				].filter(([, v]) => typeof v === 'string' && v.trim() !== '') as [string, string][])
			: []
	);
</script>

<Dialog bind:open title={asset?.title || 'Untitled'} size="lg">
	{#if asset}
		<div class="layout">
			<div class="preview">
				{#if model && viewer === 'open' && isUrl(asset.assetURI)}
					<ModelViewer
						src={asset.assetURI}
						poster={previewSrc(asset.previewURI)}
						alt={asset.title ?? ''}
					/>
				{:else}
					<AssetThumb
						src={asset.previewURI}
						contentType={asset.contentType}
						alt={asset.title ?? ''}
						eager
					/>
					{#if model && isUrl(asset.assetURI)}
						<button
							type="button"
							class="btn btn-primary btn-sm view-3d"
							onclick={() => (viewer = 'open')}
						>
							<Icon name="cube" size={16} /> View in 3D{fileSizeLabel(asset.fileSize)
								? ` (${fileSizeLabel(asset.fileSize)})`
								: ''}
						</button>
					{/if}
				{/if}
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
								{#if label === 'Licence' && assetLicence?.url}<a
										href={assetLicence.url}
										target="_blank"
										rel="noopener noreferrer">{value}</a
									>{:else if isUrl(value)}<a href={value} target="_blank" rel="noopener noreferrer"
										>{value}</a
									>{:else}{value}{/if}
								{#if label === 'Licence' && assetLicence}
									<span class="conditions">{conditionsText(assetLicence)}</span>
								{/if}
							</dd>
						</div>
					{/each}
				</dl>
				{#if asset.details?.length}
					<h3 class="details-title">From the archive</h3>
					<dl class="details">
						{#each asset.details as detail, i (i)}
							<div>
								<dt>{detail.label}</dt>
								<dd>
									{#if isUrl(detail.value)}<a
											href={detail.value}
											target="_blank"
											rel="noopener noreferrer">{detail.value}</a
										>{:else}{detail.value}{/if}
								</dd>
							</div>
						{/each}
					</dl>
				{/if}
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
		{#if ontoggle && included}
			<button type="button" class="btn" disabled>
				<Icon name="check" size={16} /> In this collection
			</button>
		{:else if ontoggle}
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
		position: relative;
		aspect-ratio: 1;
		border-radius: var(--radius-media);
		overflow: hidden;
		background: var(--surface-sunken);
	}

	.view-3d {
		position: absolute;
		left: 12px;
		bottom: 12px;
	}

	.details-title {
		margin: 8px 0 -8px;
		font-size: 12px;
		font-weight: 600;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--text-3);
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

	.conditions {
		display: block;
		margin-top: 2px;
		font-size: 12px;
		color: var(--text-2);
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
