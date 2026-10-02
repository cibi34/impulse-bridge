<script lang="ts">
	let {
		checked,
		label,
		visibleLabel,
		disabled = false,
		onchange
	}: {
		checked: boolean;
		/** Accessible name, e.g. "Visible in Unity: Young Hare". */
		label: string;
		visibleLabel?: string;
		disabled?: boolean;
		onchange: (checked: boolean) => void;
	} = $props();
</script>

<span class="switch-wrap">
	{#if visibleLabel}
		<span class="footnote secondary" aria-hidden="true">{visibleLabel}</span>
	{/if}
	<button
		type="button"
		role="switch"
		class="switch"
		aria-checked={checked}
		aria-label={label}
		{disabled}
		onclick={() => onchange(!checked)}
	>
		<span class="knob" aria-hidden="true"></span>
	</button>
</span>

<style>
	.switch-wrap {
		display: inline-flex;
		align-items: center;
		gap: 10px;
	}

	.switch {
		position: relative;
		flex-shrink: 0;
		width: 51px;
		height: 31px;
		padding: 0;
		border: 0;
		border-radius: 999px;
		background: var(--control-hover);
		transition: background-color 0.2s ease;
	}

	.switch[aria-checked='true'] {
		background: var(--success);
	}

	.switch:disabled {
		opacity: 0.5;
	}

	.knob {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 27px;
		height: 27px;
		border-radius: 50%;
		background: #ffffff;
		box-shadow: 0 2px 4px rgb(0 0 0 / 0.3);
		transition: transform 0.2s ease;
	}

	.switch[aria-checked='true'] .knob {
		transform: translateX(20px);
	}
</style>
