<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		title,
		updated,
		draft = true,
		children
	}: { title: string; updated?: string; draft?: boolean; children: Snippet } = $props();
</script>

<svelte:head>
	<title>{title} — IMPULSE Curator</title>
</svelte:head>

<article class="container legal">
	<header>
		<h1 class="large-title">{title}</h1>
		{#if updated}<p class="footnote tertiary">Last updated: {updated}</p>{/if}
	</header>
	{#if draft}
		<p class="draft" role="note">
			<strong>Draft.</strong> This page is a placeholder. Text in [brackets] still has to be provided
			and the content reviewed before launch.
		</p>
	{/if}
	<div class="prose">
		{@render children()}
	</div>
</article>

<style>
	.legal {
		max-width: 820px;
		padding-block: 56px 88px;
	}

	header {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 24px;
	}

	.draft {
		margin-bottom: 32px;
		padding: 12px 16px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 14px;
	}

	.prose :global(h2) {
		margin: 36px 0 10px;
		font-size: 20px;
		font-weight: 600;
		letter-spacing: -0.01em;
	}

	.prose :global(h3) {
		margin: 24px 0 8px;
		font-size: 16px;
		font-weight: 600;
	}

	.prose :global(p),
	.prose :global(li) {
		color: var(--text-2);
		max-width: 68ch;
	}

	.prose :global(p + p) {
		margin-top: 10px;
	}

	.prose :global(ul) {
		padding-left: 20px;
		margin: 10px 0;
	}

	.prose :global(li + li) {
		margin-top: 6px;
	}

	.prose :global(strong) {
		color: var(--text);
		font-weight: 600;
	}

	.prose :global(address) {
		font-style: normal;
		color: var(--text-2);
	}
</style>
