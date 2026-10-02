<script lang="ts">
	import { toasts } from '#lib/stores/toasts.svelte.js';
	import Icon from './Icon.svelte';
</script>

<div class="toasts" role="status" aria-live="polite" aria-relevant="additions">
	{#each toasts.items as toast (toast.id)}
		<div class="toast {toast.kind}">
			{#if toast.kind === 'success'}<Icon name="check" size={16} strokeWidth={2.4} />{/if}
			{#if toast.kind === 'error'}<Icon name="alert" size={16} />{/if}
			<span class="message">{toast.message}</span>
			{#if toast.action}
				{@const action = toast.action}
				<button
					type="button"
					class="btn btn-sm action"
					onclick={() => {
						action.run();
						toasts.dismiss(toast.id);
					}}
				>
					{action.label}
				</button>
			{/if}
			<button
				type="button"
				class="btn btn-plain btn-icon btn-sm"
				onclick={() => toasts.dismiss(toast.id)}
			>
				<Icon name="close" size={14} label="Dismiss" />
			</button>
		</div>
	{/each}
</div>

<style>
	.toasts {
		position: fixed;
		top: max(16px, env(safe-area-inset-top));
		left: 50%;
		transform: translateX(-50%);
		z-index: 60;
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: min(480px, calc(100vw - 24px));
		pointer-events: none;
	}

	.toast {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 6px 6px 6px 16px;
		border-radius: 16px;
		background: var(--glass-strong);
		border: 1px solid var(--separator-strong);
		box-shadow: var(--shadow-lg);
		backdrop-filter: saturate(180%) blur(20px);
		-webkit-backdrop-filter: saturate(180%) blur(20px);
		pointer-events: auto;
		animation: drop 0.2s ease-out;
		font-size: 14px;
	}

	@keyframes drop {
		from {
			opacity: 0;
			transform: translateY(-8px);
		}
	}

	.success :global(svg) {
		color: var(--success-text);
	}

	.error :global(svg:first-child) {
		color: var(--danger-text);
	}

	.message {
		flex: 1;
		padding: 8px 0;
	}

	.action {
		background: var(--control-hover);
	}
</style>
