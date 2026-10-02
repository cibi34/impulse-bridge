<script lang="ts">
	import { plural } from '#lib/format.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { selection } from '#lib/stores/selection.svelte.js';
	import AssetThumb from './AssetThumb.svelte';
	import Dialog from './Dialog.svelte';
	import Icon from './Icon.svelte';

	let {
		open = $bindable(false),
		actionLabel,
		onaction
	}: { open?: boolean; actionLabel: string; onaction: () => void } = $props();

	$effect(() => {
		if (open && selection.count === 0) open = false;
	});
</script>

<Dialog bind:open title="Selection" description={plural(selection.count, 'asset')}>
	<ul class="list">
		{#each selection.items as item (item.key)}
			<li>
				<span class="thumb"
					><AssetThumb src={item.asset.previewURI} contentType={item.asset.contentType} /></span
				>
				<span class="text">
					<span class="name">{item.asset.title || 'Untitled'}</span>
					<span class="footnote secondary">{item.asset.creator || app.sourceName(item.source)}</span
					>
				</span>
				<button
					type="button"
					class="btn btn-plain btn-icon btn-sm"
					onclick={() => selection.remove(item.key)}
				>
					<Icon name="close" label="Remove {item.asset.title || 'asset'} from the selection" />
				</button>
			</li>
		{/each}
	</ul>
	{#snippet footer()}
		<button type="button" class="btn btn-plain" onclick={() => selection.clear()}>Clear all</button>
		<button
			type="button"
			class="btn btn-primary"
			onclick={() => {
				open = false;
				onaction();
			}}
		>
			{actionLabel}
		</button>
	{/snippet}
</Dialog>

<style>
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
	}

	li {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 0;
		border-bottom: 1px solid var(--separator);
	}

	.thumb {
		flex-shrink: 0;
		width: 48px;
		height: 48px;
		border-radius: 10px;
		overflow: hidden;
	}

	.thumb :global(.caption) {
		display: none;
	}

	.text {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}

	.name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
