<script lang="ts">
	import type { Asset } from '#lib/api/index.js';
	import { kindLabel } from '#lib/format.js';
	import { licenceLabel } from '#lib/licences.js';
	import AssetThumb from './AssetThumb.svelte';
	import Icon from './Icon.svelte';

	let {
		asset,
		sourceName,
		selected,
		included = false,
		disabled = false,
		ontoggle,
		onopen
	}: {
		asset: Asset;
		sourceName: string;
		selected: boolean;
		/** Already in the collection being added to. */
		included?: boolean;
		disabled?: boolean;
		ontoggle: () => void;
		onopen: () => void;
	} = $props();

	const title = $derived(asset.title || 'Untitled');
	const meta = $derived([licenceLabel(asset), sourceName].filter(Boolean).join(' · '));
</script>

<article class="card" class:selected class:included>
	<button
		type="button"
		class="media"
		aria-pressed={included ? undefined : selected}
		aria-label={included
			? `Already in the collection: ${title}`
			: `${selected ? 'Deselect' : 'Select'} ${title}`}
		disabled={disabled || included}
		onclick={ontoggle}
	>
		<AssetThumb src={asset.previewURI} contentType={asset.contentType} />
		<span class="ring" aria-hidden="true"></span>
		<span class="check" aria-hidden="true">
			{#if selected || included}<Icon name="check" size={14} strokeWidth={3} />{/if}
		</span>
		{#if included}<span class="in" aria-hidden="true">In collection</span>{/if}
		<span class="kind" aria-hidden="true">{kindLabel(asset.contentType)}</span>
	</button>
	<div class="text">
		<h3>
			<button type="button" class="title-button" onclick={onopen}>
				{title}
				<span class="visually-hidden">— show details</span>
			</button>
		</h3>
		{#if asset.creator}<p class="creator">{asset.creator}</p>{/if}
		{#if meta}<p class="meta">{meta}</p>{/if}
	</div>
</article>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
	}

	.media {
		position: relative;
		display: block;
		width: 100%;
		aspect-ratio: 4 / 5;
		padding: 0;
		border: 0;
		border-radius: var(--radius-media);
		overflow: hidden;
		background: var(--surface);
		transition: transform 0.15s ease;
	}

	.media:hover:not(:disabled) {
		transform: translateY(-2px);
	}

	.media:active:not(:disabled) {
		transform: scale(0.985);
	}

	.ring {
		position: absolute;
		inset: 0;
		border-radius: inherit;
		box-shadow: inset 0 0 0 1px var(--separator);
		transition: box-shadow 0.15s ease;
	}

	.selected .ring {
		box-shadow: inset 0 0 0 3px var(--magenta);
		background: rgb(18 18 20 / 0.12);
	}

	.check {
		position: absolute;
		top: 10px;
		right: 10px;
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		border: 2px solid rgb(255 255 255 / 0.92);
		background: rgb(18 18 20 / 0.35);
		backdrop-filter: blur(6px);
		color: #ffffff;
	}

	.selected .check {
		background: var(--magenta);
		border-color: #ffffff;
	}

	.included .ring {
		box-shadow: inset 0 0 0 3px var(--success);
		background: rgb(18 18 20 / 0.18);
	}

	.included .check {
		background: #187a35;
		border-color: #ffffff;
	}

	.in {
		position: absolute;
		top: 12px;
		left: 10px;
		padding: 3px 9px;
		border-radius: 999px;
		background: #187a35;
		color: #ffffff;
		font-size: 11px;
		font-weight: 600;
	}

	.media:disabled {
		cursor: default;
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
		backdrop-filter: blur(8px);
	}

	.text {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	h3 {
		margin: 0;
		font-size: 14px;
		line-height: 1.3;
		font-weight: 600;
	}

	.title-button {
		display: block;
		width: 100%;
		padding: 0;
		border: 0;
		background: none;
		color: var(--text);
		font: inherit;
		text-align: left;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.title-button:hover {
		text-decoration: underline;
		text-underline-offset: 3px;
	}

	.creator,
	.meta {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.creator {
		font-size: 13px;
		color: var(--text-2);
	}

	.meta {
		font-size: 12px;
		color: var(--text-3);
	}
</style>
