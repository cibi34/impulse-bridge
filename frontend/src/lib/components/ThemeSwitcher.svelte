<script lang="ts">
	import { theme, type Appearance } from '#lib/stores/theme.svelte.js';
	import Icon, { type IconName } from './Icon.svelte';

	const options: { value: Appearance; label: string; icon: IconName }[] = [
		{ value: 'dark', label: 'Dark', icon: 'moon' },
		{ value: 'light', label: 'Light', icon: 'sun' },
		{ value: 'system', label: 'System', icon: 'monitor' }
	];
	const name = $props.id();
</script>

<fieldset class="theme">
	<legend class="visually-hidden">Appearance</legend>
	{#each options as option (option.value)}
		<label class:active={theme.value === option.value} title={option.label}>
			<input
				type="radio"
				{name}
				value={option.value}
				checked={theme.value === option.value}
				onchange={() => theme.set(option.value)}
			/>
			<Icon name={option.icon} size={15} />
			<span class="visually-hidden">{option.label}</span>
		</label>
	{/each}
</fieldset>

<style>
	.theme {
		display: inline-flex;
		gap: 2px;
		margin: 0;
		padding: 3px;
		border: 0;
		border-radius: 10px;
		background: var(--control);
	}

	label {
		position: relative;
		display: grid;
		place-items: center;
		width: 32px;
		height: 28px;
		border-radius: 7px;
		color: var(--text-2);
		cursor: pointer;
	}

	label.active {
		background: var(--raised);
		color: var(--text);
		box-shadow: var(--shadow-sm);
	}

	input {
		position: absolute;
		inset: 0;
		margin: 0;
		opacity: 0;
		cursor: pointer;
	}

	label:has(input:focus-visible) {
		outline: 2px solid var(--focus);
		outline-offset: 2px;
	}
</style>
