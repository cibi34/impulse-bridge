<script lang="ts">
	import type { Asset, Licence } from '#lib/api/index.js';
	import { dimensionsLabel, fileSizeLabel, kindLabel, megapixelsLabel } from '#lib/format.js';
	import { conditionsText, licenceLabel } from '#lib/licences.js';
	import AssetThumb from './AssetThumb.svelte';
	import Dialog from './Dialog.svelte';
	import Icon from './Icon.svelte';

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
