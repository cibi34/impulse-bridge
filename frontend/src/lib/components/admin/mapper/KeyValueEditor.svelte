<script lang="ts">
	import { untrack } from 'svelte';
	import Icon from '../../Icon.svelte';

	let {
		entries,
		label,
		keyPlaceholder = 'name',
		valuePlaceholder = 'value',
		onchange
	}: {
		/** The current pairs, as stored in the config. */
		entries: [string, string][];
		label: string;
		keyPlaceholder?: string;
		valuePlaceholder?: string;
		onchange: (entries: [string, string][]) => void;
	} = $props();

	// Rows being typed may have no name yet; they live here until they do.
	let rows = $state<[string, string][]>([]);
	const complete = (list: [string, string][]) => list.filter(([k]) => k.trim() !== '');

	$effect(() => {
		const stored = entries;
		untrack(() => {
			if (JSON.stringify(stored) !== JSON.stringify(complete(rows)))
				rows = stored.map((e) => [...e]);
		});
	});

	function update(index: number, part: 0 | 1, text: string) {
		rows[index][part] = text;
		onchange(complete(rows));
	}

	function remove(index: number) {
		rows.splice(index, 1);
		onchange(complete(rows));
	}
</script>

<div class="kv" role="group" aria-label={label}>
	{#each rows as row, i (i)}
		<div class="row">
			<input
				class="input mono"
				aria-label="{label}: name {i + 1}"
				placeholder={keyPlaceholder}
				value={row[0]}
				oninput={(e) => update(i, 0, e.currentTarget.value)}
			/>
			<input
				class="input mono"
				aria-label="{label}: value {i + 1}"
				placeholder={valuePlaceholder}
				value={row[1]}
				oninput={(e) => update(i, 1, e.currentTarget.value)}
			/>
			<button type="button" class="btn btn-plain btn-icon btn-sm" onclick={() => remove(i)}>
				<Icon name="close" size={16} label="Remove {row[0] || 'row'}" />
			</button>
		</div>
	{/each}
	<button type="button" class="btn btn-plain btn-sm add" onclick={() => rows.push(['', ''])}>
		<Icon name="plus" size={16} /> Add parameter
	</button>
</div>

<style>
	.kv {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.row {
		display: grid;
		grid-template-columns: minmax(0, 0.8fr) minmax(0, 1.2fr) auto;
		gap: 6px;
	}

	.row .input {
		min-height: 36px;
		padding: 6px 10px;
		font-size: 13px;
	}

	.add {
		align-self: flex-start;
	}
</style>
