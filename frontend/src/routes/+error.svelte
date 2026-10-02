<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import Logo from '#lib/components/Logo.svelte';
</script>

<svelte:head>
	<title>{page.status === 404 ? 'Page not found' : 'Error'} — IMPULSE Curator</title>
</svelte:head>

<main class="error" id="main">
	<Logo />
	<h1 class="large-title">
		{page.status === 404 ? 'This page doesn’t exist' : 'Something went wrong'}
	</h1>
	<p class="secondary">
		{page.status === 404
			? 'The link may be broken, or the page has moved.'
			: (page.error?.message ?? 'Please try again in a moment.')}
	</p>
	<div class="actions">
		<a class="btn btn-primary" href={resolve('explore')}>Explore</a>
		<a class="btn" href={resolve('')}>Home</a>
	</div>
</main>

<style>
	.error {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		justify-content: center;
		gap: 18px;
		max-width: 560px;
		min-height: 100dvh;
		margin: 0 auto;
		padding: 32px var(--gutter);
	}

	.actions {
		display: flex;
		gap: 10px;
	}
</style>
