<script lang="ts">
	import type { CollectionItem } from '#lib/api/index.js';
	import { slugify } from '#lib/format.js';
	import { conditionsText, creditsCsv, creditsText, summarize } from '#lib/licences.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';
	import Icon from './Icon.svelte';

	let {
		name,
		items,
		headingLevel = 2
	}: {
		name: string;
		/** The assets Unity gets: visible, with an accepted licence. */
		items: CollectionItem[];
		headingLevel?: 2 | 3;
	} = $props();

	const id = $props.id();
	const summary = $derived(summarize(items.map((i) => i.licence)));
	const needsCredit = $derived(items.some((i) => i.licence.conditions.includes('by')));
	const shareAlike = $derived(items.some((i) => i.licence.conditions.includes('sa')));
	const nonCommercial = $derived(items.some((i) => i.licence.conditions.includes('nc')));
	const noDerivatives = $derived(items.some((i) => i.licence.conditions.includes('nd')));
	const text = $derived(creditsText(name, items, (s) => app.sourceName(s)));

	async function copy() {
		try {
			await navigator.clipboard.writeText(text);
			toasts.success('Credits copied');
		} catch {
			document.getElementById(`${id}-text`)?.focus();
			toasts.error('Copying is blocked in this browser — select the text and copy it by hand.');
		}
	}

	function download() {
		// BOM: spreadsheet apps then read the file as UTF-8.
		const csv = '﻿' + creditsCsv(items, (s) => app.sourceName(s));
		const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
		const link = document.createElement('a');
		link.href = url;
		link.download = `${slugify(name) || 'collection'}-credits.csv`;
		link.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}
</script>

<section class="credits" aria-labelledby="{id}-title">
	<svelte:element this={`h${headingLevel}`} id="{id}-title" class="headline">
		Licences and credits
	</svelte:element>

	{#if items.length === 0}
		<p class="secondary footnote">No assets in Unity yet.</p>
	{:else}
		<ul class="summary">
			{#each summary as entry (entry.label)}
				<li>
					<span class="count">{entry.count}</span>
					<span class="label">
						{#if entry.url}<a href={entry.url} target="_blank" rel="noopener noreferrer"
								>{entry.label}</a
							>{:else}{entry.label}{/if}
					</span>
					<span class="conditions">
						{conditionsText({
							code: '',
							label: entry.label,
							url: entry.url,
							conditions: entry.conditions,
							allowed: true
						})}
					</span>
				</li>
			{/each}
		</ul>

		{#if needsCredit || shareAlike || nonCommercial || noDerivatives}
			<ul class="notes">
				{#if needsCredit}
					<li>
						Wherever these works are shown — for example in the credits of a Unity scene — credit
						them as listed below.
					</li>
				{/if}
				{#if shareAlike}
					<li>
						Share-alike: adaptations of these works, such as edited textures, must be shared under
						the same licence.
					</li>
				{/if}
				{#if nonCommercial}<li>Non-commercial: some works may not be used commercially.</li>{/if}
				{#if noDerivatives}<li>No derivatives: some works may not be changed.</li>{/if}
			</ul>
		{/if}

		<label class="visually-hidden" for="{id}-text">Credits text</label>
		<textarea id="{id}-text" class="text" readonly rows="6" value={text}></textarea>
		<div class="actions">
			<button type="button" class="btn btn-sm" onclick={copy}>
				<Icon name="copy" size={16} /> Copy credits
			</button>
			<button type="button" class="btn btn-sm btn-plain" onclick={download}>
				<Icon name="download" size={16} /> Download CSV
			</button>
		</div>
	{/if}
</section>

<style>
	.credits {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.summary {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.summary li {
		display: grid;
		grid-template-columns: 2.5em minmax(0, auto) minmax(0, 1fr);
		align-items: baseline;
		gap: 10px;
		font-size: 14px;
	}

	.count {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
		text-align: right;
	}

	.label {
		font-weight: 500;
		white-space: nowrap;
	}

	.conditions {
		color: var(--text-2);
		font-size: 13px;
	}

	.notes {
		margin: 0;
		padding: 12px 14px 12px 32px;
		border-radius: 12px;
		background: var(--surface-sunken);
		color: var(--text-2);
		font-size: 13px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.text {
		width: 100%;
		padding: 12px 14px;
		border: 1px solid var(--separator-strong);
		border-radius: var(--radius);
		background: var(--surface-sunken);
		color: var(--text-2);
		font-family: var(--font-mono);
		font-size: 12px;
		line-height: 1.5;
		resize: vertical;
	}

	.text:focus-visible {
		outline: 2px solid var(--focus);
		outline-offset: 1px;
	}

	.actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	@media (max-width: 640px) {
		.summary li {
			grid-template-columns: 2.5em minmax(0, 1fr);
		}
		.conditions {
			grid-column: 2;
		}
	}
</style>
