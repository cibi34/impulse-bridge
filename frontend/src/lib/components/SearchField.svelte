<script lang="ts">
	import Icon from './Icon.svelte';

	let {
		value = $bindable(''),
		label = 'Search',
		placeholder = 'Search',
		onsubmit
	}: {
		value?: string;
		label?: string;
		placeholder?: string;
		onsubmit: (value: string) => void;
	} = $props();

	const id = $props.id();
</script>

<form
	role="search"
	class="search"
	onsubmit={(event) => {
		event.preventDefault();
		onsubmit(value.trim());
	}}
>
	<label for={id} class="visually-hidden">{label}</label>
	<span class="icon"><Icon name="search" size={16} strokeWidth={2} /></span>
	<input
		{id}
		type="search"
		bind:value
		{placeholder}
		autocomplete="off"
		spellcheck="false"
		enterkeyhint="search"
		oninput={(event) => {
			// Clearing the field — the browser's ✕ button, Escape, or deleting
			// the text — is a search for nothing; don't wait for Enter.
			if (event.currentTarget.value.trim() === '') onsubmit('');
		}}
	/>
</form>

<style>
	.search {
		position: relative;
		width: 100%;
	}

	.icon {
		position: absolute;
		left: 12px;
		top: 50%;
		transform: translateY(-50%);
		color: var(--text-3);
		pointer-events: none;
	}

	input {
		width: 100%;
		height: 40px;
		padding: 0 14px 0 36px;
		border: 1px solid var(--separator);
		border-radius: 11px;
		background: var(--control);
		color: var(--text);
	}

	input::placeholder {
		color: var(--text-3);
	}

	input:focus-visible {
		outline: 2px solid var(--focus);
		outline-offset: 1px;
	}
</style>
