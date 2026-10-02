<script lang="ts">
	import { resolve } from '$app/paths';
	import Logo from '#lib/components/Logo.svelte';
	import SiteFooter from '#lib/components/SiteFooter.svelte';

	let { children } = $props();
</script>

<a class="skip" href="#main">Skip to content</a>

<header class="header">
	<div class="container bar">
		<Logo />
		<nav aria-label="Main" class="nav">
			<a href={resolve('explore')}>Explore</a>
			<a href={resolve('my')}>My collections</a>
			<a href={resolve('#how')}>How it works</a>
		</nav>
		<a class="btn btn-primary btn-sm cta" href={resolve('explore')}>Start a collection</a>
	</div>
</header>

<main id="main" tabindex="-1">
	{@render children()}
</main>

<div class="footer-wrap">
	<div class="container">
		<SiteFooter />
	</div>
</div>

<style>
	.skip {
		position: fixed;
		top: 8px;
		left: 8px;
		z-index: 100;
		padding: 10px 16px;
		border-radius: 10px;
		background: var(--action);
		color: var(--text-on-action);
		font-weight: 600;
		text-decoration: none;
		transform: translateY(-200%);
	}

	.skip:focus-visible {
		transform: none;
	}

	.header {
		position: sticky;
		top: 0;
		z-index: 10;
		background: var(--glass);
		backdrop-filter: saturate(180%) blur(20px);
		-webkit-backdrop-filter: saturate(180%) blur(20px);
		border-bottom: 1px solid var(--separator);
	}

	.bar {
		display: flex;
		align-items: center;
		gap: 28px;
		height: 60px;
	}

	.nav {
		display: flex;
		gap: 22px;
		font-size: 14px;
	}

	.nav a {
		color: var(--text-2);
		text-decoration: none;
	}

	.nav a:hover {
		color: var(--text);
	}

	.cta {
		margin-left: auto;
	}

	main {
		outline: none;
	}

	.footer-wrap {
		padding: 40px 0 48px;
		border-top: 1px solid var(--separator);
		background: var(--bg-elevated);
	}

	@media (max-width: 720px) {
		.nav {
			display: none;
		}
	}
</style>
