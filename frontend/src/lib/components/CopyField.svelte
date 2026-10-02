<script lang="ts">
	import Icon from './Icon.svelte';

	let {
		label,
		value,
		hint,
		display
	}: {
		label: string;
		value: string;
		hint?: string;
		/** Shown instead of `value` (e.g. a masked secret). */
		display?: string;
	} = $props();

	const id = $props.id();
	let copied = $state(false);
	let timer: ReturnType<typeof setTimeout>;

	async function copy() {
		try {
			await navigator.clipboard.writeText(value);
			copied = true;
			clearTimeout(timer);
			timer = setTimeout(() => (copied = false), 1800);
		} catch {
			// Clipboard blocked: select the text so it can be copied by hand.
			const el = document.getElementById(`${id}-value`);
			if (el) window.getSelection()?.selectAllChildren(el);
		}
	}
</script>

<div class="copy-field">
	<span class="field-label" id="{id}-label">{label}</span>
	{#if hint}
		<span class="field-hint" id="{id}-hint">{hint}</span>
	{/if}
	<div class="row">
		<code id="{id}-value" class="value" aria-labelledby="{id}-label">{display ?? value}</code>
		<button
			type="button"
			class="btn btn-sm"
			onclick={copy}
			aria-describedby={hint ? `${id}-hint` : undefined}
		>
			<Icon name={copied ? 'check' : 'copy'} size={16} />
			{copied ? 'Copied' : 'Copy'}
			<span class="visually-hidden">{label}</span>
		</button>
	</div>
	<span class="visually-hidden" role="status">{copied ? `${label} copied` : ''}</span>
</div>

<style>
	.copy-field {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}

	.row {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.value {
		flex: 1;
		min-width: 0;
		padding: 10px 12px;
		border-radius: 10px;
		background: var(--surface-sunken);
		font-family: var(--font-mono);
		font-size: 12px;
		color: var(--text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.btn {
		flex-shrink: 0;
	}
</style>
