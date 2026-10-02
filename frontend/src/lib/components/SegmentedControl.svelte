<script lang="ts" generics="T extends string">
	// A segmented control built on native radio buttons: arrow keys, focus and
	// screen-reader semantics come from the browser.
	let {
		legend,
		options,
		value = $bindable(),
		onchange
	}: {
		legend: string;
		options: { value: T; label: string }[];
		value: T;
		onchange?: (value: T) => void;
	} = $props();

	const name = $props.id();
</script>

<fieldset class="segmented">
	<legend class="visually-hidden">{legend}</legend>
	{#each options as option (option.value)}
		<label class:active={value === option.value}>
			<input
				type="radio"
				{name}
				value={option.value}
				checked={value === option.value}
				onchange={() => {
					value = option.value;
					onchange?.(option.value);
				}}
			/>
			<span>{option.label}</span>
		</label>
	{/each}
</fieldset>

<style>
	.segmented {
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
		display: inline-flex;
		align-items: center;
		min-height: 32px;
		padding: 0 16px;
		border-radius: 8px;
		color: var(--text-2);
		font-size: 13px;
		font-weight: 500;
		cursor: pointer;
		transition: background-color 0.15s ease;
		white-space: nowrap;
	}

	label.active {
		background: var(--raised);
		color: var(--text);
		font-weight: 600;
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
