<script lang="ts">
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	let {
		open = $bindable(false),
		title,
		description,
		size = 'md',
		onclose,
		children,
		footer
	}: {
		open?: boolean;
		title: string;
		description?: string;
		size?: 'sm' | 'md' | 'lg';
		onclose?: () => void;
		children: Snippet;
		footer?: Snippet;
	} = $props();

	let dialog: HTMLDialogElement | undefined = $state();
	const id = $props.id();

	// Native <dialog> + showModal(): focus is trapped, Escape closes, the rest
	// of the page is inert, and focus returns to the opener when it closes.
	$effect(() => {
		if (!dialog) return;
		if (open && !dialog.open) {
			dialog.showModal();
			// showModal() focuses the first control (the close button); a field
			// marked data-autofocus is the better start, e.g. a form's first input.
			dialog.querySelector<HTMLElement>('[data-autofocus]')?.focus();
		}
		if (!open && dialog.open) dialog.close();
	});

	function handleClose() {
		if (open) {
			open = false;
			onclose?.();
		}
	}

	function handleBackdrop(event: MouseEvent) {
		// A click on the dialog element itself (not its content) is the backdrop.
		if (event.target === dialog) handleClose();
	}
</script>

<dialog
	bind:this={dialog}
	class="dialog size-{size}"
	aria-labelledby="{id}-title"
	aria-describedby={description ? `${id}-description` : undefined}
	onclose={handleClose}
	onclick={handleBackdrop}
>
	{#if open}
		<div class="sheet">
			<header>
				<div class="heading">
					<h2 id="{id}-title" class="title">{title}</h2>
					{#if description}
						<p id="{id}-description" class="footnote secondary">{description}</p>
					{/if}
				</div>
				<button type="button" class="btn btn-plain btn-icon btn-sm close" onclick={handleClose}>
					<Icon name="close" label="Close" />
				</button>
			</header>
			<div class="body">
				{@render children()}
			</div>
			{#if footer}
				<footer>
					{@render footer()}
				</footer>
			{/if}
		</div>
	{/if}
</dialog>

<style>
	.dialog {
		padding: 0;
		border: 1px solid var(--separator-strong);
		border-radius: 20px;
		background: var(--bg-elevated);
		color: var(--text);
		box-shadow: var(--shadow-lg);
		width: min(100vw - 32px, var(--dialog-width));
		max-height: min(100dvh - 48px, 880px);
		overflow: hidden;
	}

	.size-sm {
		--dialog-width: 420px;
	}
	.size-md {
		--dialog-width: 560px;
	}
	.size-lg {
		--dialog-width: 880px;
	}

	.dialog::backdrop {
		background: var(--overlay);
		backdrop-filter: blur(4px);
	}

	.dialog[open] {
		animation: rise 0.2s ease-out;
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(12px) scale(0.98);
		}
	}

	.sheet {
		display: flex;
		flex-direction: column;
		max-height: inherit;
	}

	header {
		display: flex;
		align-items: flex-start;
		gap: 16px;
		padding: 22px 22px 6px 24px;
	}

	.heading {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}

	.close {
		margin: -6px -6px 0 0;
		flex-shrink: 0;
	}

	.body {
		padding: 14px 24px 22px;
		overflow-y: auto;
	}

	footer {
		display: flex;
		justify-content: flex-end;
		gap: 10px;
		flex-wrap: wrap;
		padding: 16px 24px 22px;
		border-top: 1px solid var(--separator);
	}

	@media (max-width: 600px) {
		.dialog {
			width: 100vw;
			max-width: 100vw;
			max-height: calc(100dvh - 24px);
			margin: auto 0 0;
			border-radius: 20px 20px 0 0;
			border-bottom: 0;
		}
		footer {
			padding-bottom: max(22px, env(safe-area-inset-bottom));
		}
		footer :global(.btn) {
			flex: 1;
		}
	}
</style>
