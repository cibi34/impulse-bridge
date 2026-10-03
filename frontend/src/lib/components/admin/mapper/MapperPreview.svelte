<script lang="ts">
	import type { Licence } from '#lib/api/index.js';
	import type { FilterConfig, Mapped } from '#lib/mapper/evaluate.js';
	import { FIELDS } from '#lib/mapper/fields.js';
	import { preview } from '#lib/mapper/json.js';
	import AssetThumb from '../../AssetThumb.svelte';
	import Icon from '../../Icon.svelte';

	let {
		results,
		licences,
		filter,
		onfilter,
		onshow
	}: {
		results: Mapped[];
		/** Licence readings by rights value. */
		licences: Record<string, Licence>;
		filter: FilterConfig;
		onfilter: (filter: { drop_if_missing: string[]; allowed_content_types: string[] }) => void;
		/** Show this result in the explorer. */
		onshow: (index: number) => void;
	} = $props();

	const licenceOf = (m: Mapped) => licences[String(m.asset.rights ?? '')] ?? null;
	const kept = $derived(results.filter((r) => !r.dropped));
	const usable = $derived(kept.filter((r) => licenceOf(r)?.allowed));
	const reasons = $derived.by(() => {
		const counts: Record<string, number> = {};
		for (const r of results) if (r.dropped) counts[r.dropped] = (counts[r.dropped] ?? 0) + 1;
		for (const r of kept) {
			const l = licenceOf(r);
			if (l && !l.allowed) {
				const key =
					l.code === 'other'
						? `Licence not recognised (${l.label})`
						: `Licence not accepted (${l.label})`;
				counts[key] = (counts[key] ?? 0) + 1;
			}
		}
		return Object.entries(counts).sort((a, b) => b[1] - a[1]);
	});
	const types = $derived([
		...new Set(
			results.map((r) => r.asset.contentType).filter((t): t is string => typeof t === 'string')
		)
	]);

	const drop = $derived(filter.drop_if_missing ?? []);
	const allowedTypes = $derived(filter.allowed_content_types ?? []);
	const DROPPABLE = FIELDS.filter((f) =>
		['assetURI', 'previewURI', 'title', 'assetID'].includes(f.name)
	);

	function toggleDrop(name: string, on: boolean) {
		const next = on ? [...drop, name] : drop.filter((d) => d !== name);
		onfilter({ drop_if_missing: next, allowed_content_types: allowedTypes });
	}

	function toggleType(type: string, on: boolean) {
		const next = on ? [...allowedTypes, type] : allowedTypes.filter((t) => t !== type);
		onfilter({ drop_if_missing: drop, allowed_content_types: next });
	}

	let showAll = $state(false);
	const cards = $derived(showAll ? results : results.slice(0, 12));
</script>

<div class="preview">
	<ol class="funnel" aria-label="What reaches the web app">
		<li><strong>{results.length}</strong> results in the sample</li>
		<li><strong>{kept.length}</strong> kept by the filter</li>
		<li class:good={usable.length > 0}>
			<strong>{usable.length}</strong> with an accepted licence
		</li>
	</ol>

	{#if reasons.length}
		<ul class="reasons">
			{#each reasons as [reason, count] (reason)}
				<li><span class="count">{count}×</span> {reason}</li>
			{/each}
		</ul>
	{/if}

	<div class="filters">
		<fieldset>
			<legend class="field-label">Leave out results without</legend>
			{#each DROPPABLE as f (f.name)}
				<label class="check">
					<input
						type="checkbox"
						checked={drop.includes(f.name)}
						onchange={(e) => toggleDrop(f.name, e.currentTarget.checked)}
					/>
					{f.label}
				</label>
			{/each}
		</fieldset>
		{#if types.length > 0}
			<fieldset>
				<legend class="field-label"
					>Only these content types {allowedTypes.length ? '' : '(none ticked: all)'}</legend
				>
				{#each types as type (type)}
					<label class="check mono">
						<input
							type="checkbox"
							checked={allowedTypes.includes(type)}
							onchange={(e) => toggleType(type, e.currentTarget.checked)}
						/>
						{type}
					</label>
				{/each}
			</fieldset>
		{/if}
	</div>

	{#if results.length}
		<ul class="cards">
			{#each cards as r, i (i)}
				{@const licence = licenceOf(r)}
				<li class:out={!!r.dropped || (licence && !licence.allowed)}>
					<button type="button" class="card" onclick={() => onshow(i)}>
						<span class="thumb">
							<AssetThumb
								src={(r.asset.previewURI ?? r.asset.assetURI) as string | undefined}
								contentType={r.asset.contentType as string | undefined}
							/>
						</span>
						<span class="title">{r.asset.title ? preview(r.asset.title, 80) : 'Untitled'}</span>
						{#if r.asset.creator}<span class="sub">{preview(r.asset.creator, 60)}</span>{/if}
						{#if r.dropped}
							<span class="pill pill-warning">{r.dropped}</span>
						{:else if licence}
							<span class="pill {licence.allowed ? 'pill-success' : 'pill-warning'}">
								{#if licence.allowed}<Icon name="check" size={12} strokeWidth={2.6} />{/if}
								{licence.label}
							</span>
						{/if}
						<span class="visually-hidden">— show in the explorer</span>
					</button>
				</li>
			{/each}
		</ul>
		{#if results.length > 12}
			<button type="button" class="btn btn-plain btn-sm" onclick={() => (showAll = !showAll)}>
				{showAll ? 'Show fewer' : `Show all ${results.length}`}
			</button>
		{/if}
	{/if}
</div>

<style>
	.preview {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.funnel {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: 13.5px;
		color: var(--text-2);
	}

	.funnel li {
		padding: 6px 12px;
		border-radius: var(--radius-pill);
		background: var(--control);
	}

	.funnel li + li::before {
		content: '→ ';
		color: var(--text-3);
	}

	.funnel strong {
		color: var(--text);
		font-variant-numeric: tabular-nums;
	}

	.funnel .good {
		background: var(--success-soft);
	}

	.reasons {
		margin: 0;
		padding: 10px 14px;
		list-style: none;
		border-radius: 10px;
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 13px;
	}

	.count {
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: 12px 28px;
	}

	fieldset {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 6px 14px;
		margin: 0;
		padding: 0;
		border: 0;
	}

	legend {
		width: 100%;
		margin-bottom: 4px;
	}

	.check {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: 13.5px;
	}

	.check input {
		accent-color: var(--action);
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
		gap: 16px 14px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.card {
		display: flex;
		flex-direction: column;
		gap: 4px;
		width: 100%;
		padding: 0;
		border: 0;
		background: none;
		color: var(--text);
		text-align: left;
	}

	.thumb {
		display: block;
		aspect-ratio: 1;
		margin-bottom: 4px;
		overflow: hidden;
		border-radius: 10px;
		background: var(--surface-sunken);
	}

	.title {
		font-size: 13px;
		font-weight: 600;
		line-height: 1.3;
	}

	.sub {
		font-size: 12px;
		color: var(--text-2);
	}

	.card .pill {
		align-self: flex-start;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.out .thumb {
		opacity: 0.4;
	}
</style>
