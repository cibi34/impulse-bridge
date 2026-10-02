<script lang="ts">
	import { rightsLabel } from '#lib/rights.js';
	import type { CollectionItem } from '#lib/api/index.js';
	import { app } from '#lib/stores/app.svelte.js';
	import AssetThumb from './AssetThumb.svelte';
	import Icon from './Icon.svelte';
	import Switch from './Switch.svelte';

	let {
		items,
		disabled = false,
		onreorder,
		ontoggle,
		onremove,
		onopen
	}: {
		items: CollectionItem[];
		disabled?: boolean;
		/** Called with the new order once a move is finished. */
		onreorder: (assetIds: string[]) => void;
		ontoggle: (item: CollectionItem, published: boolean) => void;
		onremove: (item: CollectionItem) => void;
		onopen: (item: CollectionItem) => void;
	} = $props();

	// The order shown while dragging; synced from `items` otherwise.
	let order = $state<string[]>([]);
	let dragging = $state<string | null>(null);
	let announcement = $state('');
	// Row elements by asset id, for hit-testing while dragging (not state).
	// eslint-disable-next-line svelte/prefer-svelte-reactivity
	const rows = new Map<string, HTMLElement>();

	$effect(() => {
		if (!dragging) order = items.map((i) => i.asset_id);
	});

	const byId = $derived(new Map(items.map((i) => [i.asset_id, i])));
	const ordered = $derived(order.map((id) => byId.get(id)).filter((i): i is CollectionItem => !!i));

	function titleOf(item: CollectionItem) {
		return item.asset.title || 'Untitled';
	}

	function move(id: string, to: number) {
		const from = order.indexOf(id);
		if (from < 0 || to < 0 || to >= order.length || from === to) return false;
		const next = [...order];
		next.splice(from, 1);
		next.splice(to, 0, id);
		order = next;
		return true;
	}

	// ---- keyboard: arrows on the handle move the item ----
	function onkeydown(event: KeyboardEvent, item: CollectionItem) {
		const index = order.indexOf(item.asset_id);
		const targets: Record<string, number> = {
			ArrowUp: index - 1,
			ArrowDown: index + 1,
			Home: 0,
			End: order.length - 1
		};
		if (!(event.key in targets)) return;
		const to = targets[event.key];
		event.preventDefault();
		if (move(item.asset_id, to)) {
			announcement = `${titleOf(item)} moved to position ${to + 1} of ${order.length}`;
			onreorder(order);
			// Keep focus on the moved handle after the DOM reorders.
			requestAnimationFrame(() =>
				rows.get(item.asset_id)?.querySelector<HTMLElement>('.handle')?.focus()
			);
		}
	}

	// ---- pointer: drag the handle ----
	function onpointerdown(event: PointerEvent, item: CollectionItem) {
		if (disabled || event.button !== 0) return;
		(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
		dragging = item.asset_id;
	}

	function onpointermove(event: PointerEvent) {
		if (!dragging) return;
		const id = dragging;
		for (const [otherId, row] of rows) {
			if (otherId === id) continue;
			const rect = row.getBoundingClientRect();
			// Swap once the pointer crosses the middle of a neighbouring row.
			if (event.clientY > rect.top && event.clientY < rect.bottom) {
				const target = order.indexOf(otherId);
				const from = order.indexOf(id);
				const middle = rect.top + rect.height / 2;
				if (
					(target > from && event.clientY > middle) ||
					(target < from && event.clientY < middle)
				) {
					move(id, target);
				}
				break;
			}
		}
	}

	function onpointerup() {
		if (!dragging) return;
		const id = dragging;
		dragging = null;
		const before = items.map((i) => i.asset_id).join();
		if (order.join() !== before) {
			const item = byId.get(id);
			if (item)
				announcement = `${titleOf(item)} moved to position ${order.indexOf(id) + 1} of ${order.length}`;
			onreorder(order);
		}
	}

	function register(node: HTMLElement, id: string) {
		rows.set(id, node);
		return {
			destroy() {
				rows.delete(id);
			}
		};
	}
</script>

<p id="reorder-help" class="visually-hidden">
	To reorder, focus a handle and use the arrow keys, or drag it.
</p>
<ul class="items" class:dragging={!!dragging}>
	{#each ordered as item (item.asset_id)}
		<li
			use:register={item.asset_id}
			class:active={dragging === item.asset_id}
			class:hidden={!item.published}
		>
			<button
				type="button"
				class="handle"
				aria-label="Reorder {titleOf(item)}, position {order.indexOf(item.asset_id) +
					1} of {order.length}"
				aria-describedby="reorder-help"
				{disabled}
				onkeydown={(e) => onkeydown(e, item)}
				onpointerdown={(e) => onpointerdown(e, item)}
				{onpointermove}
				{onpointerup}
				onpointercancel={onpointerup}
			>
				<Icon name="grip" size={16} />
			</button>
			<button
				type="button"
				class="thumb"
				onclick={() => onopen(item)}
				tabindex="-1"
				aria-hidden="true"
			>
				<AssetThumb src={item.asset.previewURI} contentType={item.asset.contentType} />
			</button>
			<div class="text">
				<button type="button" class="name" onclick={() => onopen(item)}>
					{titleOf(item)}<span class="visually-hidden"> — show details</span>
				</button>
				<span class="meta">
					{[item.asset.creator, rightsLabel(item.asset.rights), app.sourceName(item.source)]
						.filter(Boolean)
						.join(' · ')}
				</span>
			</div>
			<Switch
				checked={item.published}
				label="Visible in Unity: {titleOf(item)}"
				visibleLabel="Visible in Unity"
				{disabled}
				onchange={(value) => ontoggle(item, value)}
			/>
			<button
				type="button"
				class="btn btn-plain btn-icon remove"
				{disabled}
				onclick={() => onremove(item)}
			>
				<Icon name="trash" label="Remove {titleOf(item)}" />
			</button>
		</li>
	{/each}
</ul>
<p class="visually-hidden" role="status" aria-live="assertive">{announcement}</p>

<style>
	.items {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	li {
		display: flex;
		align-items: center;
		gap: 14px;
		padding: 10px 14px 10px 8px;
		border-bottom: 1px solid var(--separator);
		background: var(--bg-elevated);
		transition: background-color 0.15s ease;
	}

	li:last-child {
		border-bottom: 0;
	}

	li.active {
		position: relative;
		z-index: 1;
		background: var(--control);
		box-shadow: var(--shadow-lg);
	}

	.handle {
		flex-shrink: 0;
		display: grid;
		place-items: center;
		width: 32px;
		height: 44px;
		border: 0;
		border-radius: 8px;
		background: transparent;
		color: var(--text-3);
		cursor: grab;
		touch-action: none;
	}

	.dragging,
	.dragging .handle {
		cursor: grabbing;
		user-select: none;
	}

	.handle:hover {
		background: var(--control);
		color: var(--text);
	}

	.thumb {
		flex-shrink: 0;
		width: 56px;
		height: 56px;
		padding: 0;
		border: 0;
		border-radius: 10px;
		overflow: hidden;
		background: var(--surface);
	}

	.thumb :global(.caption) {
		display: none;
	}

	.text {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.name {
		padding: 0;
		border: 0;
		background: none;
		color: var(--text);
		font-weight: 600;
		text-align: left;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.name:hover {
		text-decoration: underline;
		text-underline-offset: 3px;
	}

	.meta {
		font-size: 13px;
		color: var(--text-2);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* Hidden from Unity: dim the picture only — text keeps its contrast. */
	.hidden .thumb {
		opacity: 0.4;
	}

	.hidden .name {
		color: var(--text-2);
	}

	@media (max-width: 640px) {
		li {
			flex-wrap: wrap;
			gap: 10px;
		}
		.text {
			flex-basis: calc(100% - 120px);
		}
		li :global(.switch-wrap) {
			margin-left: 46px;
		}
		.remove {
			margin-left: auto;
		}
	}
</style>
