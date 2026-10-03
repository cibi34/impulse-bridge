<script lang="ts">
	import { plural } from '#lib/format.js';
	import { previewSrc } from '#lib/images.js';
	import { selection } from '#lib/stores/selection.svelte.js';

	let {
		actionLabel,
		limit,
		busy = false,
		onaction,
		onreview
	}: {
		actionLabel: string;
		/** How many assets fit into the collection being built or added to. */
		limit?: number;
		busy?: boolean;
		onaction: () => void;
		onreview: () => void;
	} = $props();

	const thumbs = $derived(
		selection.items
			.map((item) => previewSrc(item.asset.previewURI))
			.filter((src): src is string => !!src)
			.slice(-3)
	);
</script>

{#if selection.count > 0}
	<div class="bar" role="region" aria-label="Selection">
		<button type="button" class="summary" onclick={onreview}>
			<span class="thumbs" aria-hidden="true">
				{#each thumbs as src (src)}
					<img {src} alt="" crossorigin="anonymous" referrerpolicy="no-referrer" />
				{/each}
			</span>
			<span class="count" role="status"
				>{limit !== undefined && selection.count >= limit - 5
					? `${selection.count} of ${limit} assets selected`
					: `${plural(selection.count, 'asset')} selected`}</span
			>
			<span class="visually-hidden">— review selection</span>
		</button>
		<button type="button" class="btn btn-plain btn-sm clear" onclick={() => selection.clear()}>
			Clear
		</button>
		<button type="button" class="btn btn-primary" disabled={busy} onclick={onaction}>
			{actionLabel}
		</button>
	</div>
{/if}

<style>
	.bar {
		position: fixed;
		left: 50%;
		bottom: max(20px, env(safe-area-inset-bottom));
		transform: translateX(calc(-50% + var(--bar-offset, 0px)));
		z-index: 20;
		display: flex;
		align-items: center;
		gap: 8px;
		max-width: calc(100vw - 24px);
		padding: 6px 6px 6px 8px;
		border-radius: 999px;
		background: var(--glass-strong);
		border: 1px solid var(--separator-strong);
		box-shadow: var(--shadow-lg);
		backdrop-filter: saturate(180%) blur(20px);
		-webkit-backdrop-filter: saturate(180%) blur(20px);
		animation: up 0.2s ease-out;
	}

	@keyframes up {
		from {
			opacity: 0;
			transform: translate(calc(-50% + var(--bar-offset, 0px)), 12px);
		}
	}

	.summary {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 44px;
		padding: 0 10px 0 4px;
		border: 0;
		border-radius: 999px;
		background: transparent;
		color: var(--text);
	}

	.summary:hover {
		background: var(--control);
	}

	.thumbs {
		display: flex;
		padding-left: 8px;
	}

	.thumbs img {
		width: 32px;
		height: 32px;
		margin-left: -8px;
		border-radius: 50%;
		object-fit: cover;
		border: 2px solid var(--bg-elevated);
	}

	.count {
		font-size: 14px;
		font-weight: 500;
		white-space: nowrap;
	}

	@media (max-width: 520px) {
		.thumbs,
		.clear {
			display: none;
		}
	}
</style>
