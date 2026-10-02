<script lang="ts">
	import type { Template } from '#lib/api/admin.js';
	import Dialog from '../Dialog.svelte';
	import Icon from '../Icon.svelte';

	let {
		open = $bindable(false),
		templates,
		onpick
	}: { open?: boolean; templates: Template[]; onpick: (template: Template) => void } = $props();

	const hints: Record<string, string> = {
		'rest-generic': 'Any archive with a JSON search API — mapped field by field.',
		'iiif-manifest': 'One IIIF Presentation manifest; every canvas becomes an asset.',
		'fallback-local': 'Pre-mapped assets from a JSON file on this server.'
	};
</script>

<Dialog
	bind:open
	title="New source"
	description="Start from a template. You can change everything before saving."
>
	<ul class="list">
		{#each templates as template (template.key)}
			<li>
				<button
					type="button"
					class="choice"
					onclick={() => {
						open = false;
						onpick(template);
					}}
				>
					<span class="text">
						<span class="headline">{template.label}</span>
						<span class="footnote secondary">{hints[template.key] ?? template.key}</span>
					</span>
					<Icon name="chevronRight" />
				</button>
			</li>
		{/each}
	</ul>
</Dialog>

<style>
	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.choice {
		display: flex;
		align-items: center;
		gap: 12px;
		width: 100%;
		padding: 14px 16px;
		border: 1px solid var(--separator);
		border-radius: 14px;
		background: var(--surface);
		color: var(--text);
		text-align: left;
	}

	.choice:hover {
		border-color: var(--separator-strong);
		background: var(--control);
	}

	.text {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
</style>
