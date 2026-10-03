<script lang="ts">
	import Icon from '../../Icon.svelte';
	import JsonTree from './JsonTree.svelte';
	import { childPath, isImageUrl, jsonType, preview } from '#lib/mapper/json.js';

	let {
		value,
		path = '',
		name = null,
		depth = 0,
		openDepth = 2,
		usage = {},
		pickVerb = 'Use',
		onpick
	}: {
		value: unknown;
		/** JMESPath of this value, relative to the result. */
		path?: string;
		name?: string | number | null;
		depth?: number;
		/** Nodes above this depth start open. */
		openDepth?: number;
		/** Which fields use a path, for badges. */
		usage?: Record<string, string[]>;
		/** Start of the accessible name of a pickable value: "Use for Title". */
		pickVerb?: string;
		onpick: (path: string, value: unknown) => void;
	} = $props();

	const SHOWN = 4;
	const type = $derived(jsonType(value));
	const container = $derived(type === 'object' || type === 'array');
	// Only the starting state: the visitor opens and closes nodes from there.
	// svelte-ignore state_referenced_locally
	let open = $state(depth < openDepth);
	let all = $state(false);

	const entries = $derived.by((): [string | number, unknown][] => {
		if (type === 'array') return (value as unknown[]).map((v, i) => [i, v]);
		if (type === 'object') return Object.entries(value as object);
		return [];
	});
	const shown = $derived(type === 'array' && !all ? entries.slice(0, SHOWN) : entries);
	const primitiveList = $derived(
		type === 'array' &&
			(value as unknown[]).length > 0 &&
			(value as unknown[]).every((v) => ['string', 'number'].includes(jsonType(v)))
	);
	const label = $derived(name === null ? '' : typeof name === 'number' ? `[${name}]` : name);
</script>

{#snippet children()}
	<ul class="tree" class:root={depth === 0}>
		{#each shown as [key, child] (key)}
			<JsonTree
				value={child}
				path={childPath(path, key)}
				name={key}
				depth={depth + 1}
				{openDepth}
				{usage}
				{pickVerb}
				{onpick}
			/>
		{/each}
		{#if type === 'array' && entries.length > SHOWN}
			<li>
				<button type="button" class="more" onclick={() => (all = !all)}>
					{all ? 'Show fewer' : `Show all ${entries.length}`}
				</button>
			</li>
		{/if}
	</ul>
{/snippet}

{#if depth === 0 && name === null}
	{#if container}{@render children()}{:else}<p class="footnote tertiary">{preview(value)}</p>{/if}
{:else}
	<li class="node">
		{#if container}
			<div class="row">
				<button type="button" class="toggle" aria-expanded={open} onclick={() => (open = !open)}>
					<span class="chevron" class:open aria-hidden="true"
						><Icon name="chevronRight" size={14} /></span
					>
					<span class="key mono">{label}</span>
					<span class="meta">{preview(value)}</span>
				</button>
				{#if primitiveList}
					<button
						type="button"
						class="use-list"
						title={path}
						aria-label="{pickVerb}: the list {path}"
						onclick={() => onpick(path, value)}>Use list</button
					>
				{/if}
				{#each usage[path] ?? [] as used (used)}<span class="badge">{used}</span>{/each}
			</div>
			{#if open}{@render children()}{/if}
		{:else}
			<button
				type="button"
				class="leaf"
				title={path}
				aria-label="{pickVerb}: {path} = {preview(value, 80)}"
				onclick={() => onpick(path, value)}
			>
				<span class="key mono">{label}</span>
				<span class="value type-{type}">{preview(value)}</span>
				{#if isImageUrl(value)}
					<img
						src={value as string}
						alt=""
						width="28"
						height="28"
						loading="lazy"
						crossorigin="anonymous"
						referrerpolicy="no-referrer"
					/>
				{/if}
				{#each usage[path] ?? [] as used (used)}<span class="badge">{used}</span>{/each}
			</button>
		{/if}
	</li>
{/if}

<style>
	.tree {
		list-style: none;
		margin: 0;
		padding: 0 0 0 14px;
		border-left: 1px solid var(--separator);
	}

	.tree.root {
		padding-left: 0;
		border-left: 0;
	}

	.node {
		margin: 1px 0;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.toggle,
	.leaf {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		padding: 4px 8px;
		border: 0;
		border-radius: 8px;
		background: transparent;
		color: var(--text);
		font-size: 13px;
		text-align: left;
	}

	.leaf {
		width: 100%;
	}

	.toggle:hover,
	.leaf:hover {
		background: var(--control);
	}

	.leaf:hover .value {
		color: var(--text);
	}

	.chevron {
		display: inline-flex;
		color: var(--text-3);
		transition: transform 0.15s ease;
	}

	.chevron.open {
		transform: rotate(90deg);
	}

	.key {
		flex-shrink: 0;
		color: var(--link);
		font-size: 12.5px;
	}

	.meta {
		color: var(--text-3);
		font-size: 12px;
	}

	.value {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--text-2);
	}

	.type-number,
	.type-boolean {
		color: var(--warning-text);
	}

	.type-null {
		color: var(--text-3);
	}

	img {
		flex-shrink: 0;
		width: 28px;
		height: 28px;
		object-fit: cover;
		border-radius: 5px;
		background: var(--control);
	}

	.badge {
		flex-shrink: 0;
		padding: 1px 7px;
		border-radius: var(--radius-pill);
		background: var(--accent-soft);
		color: var(--accent-text);
		font-size: 11px;
		font-weight: 600;
		white-space: nowrap;
	}

	.leaf .badge:first-of-type {
		margin-left: auto;
	}

	.use-list,
	.more {
		padding: 2px 8px;
		border: 1px solid var(--separator-strong);
		border-radius: var(--radius-pill);
		background: transparent;
		color: var(--text-2);
		font-size: 11.5px;
	}

	.use-list:hover,
	.more:hover {
		background: var(--control);
		color: var(--text);
	}

	.more {
		margin: 2px 0 2px 8px;
	}
</style>
