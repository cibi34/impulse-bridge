<script lang="ts">
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import Icon, { type IconName } from '#lib/components/Icon.svelte';
	import Logo from '#lib/components/Logo.svelte';
	import ThemeSwitcher from '#lib/components/ThemeSwitcher.svelte';

	let { children } = $props();

	const tabs: { href: string; label: string; icon: IconName; match: (path: string) => boolean }[] =
		[
			{
				href: resolve('admin'),
				label: 'Collections',
				icon: 'collections',
				match: (p) => p === '/admin'
			},
			{
				href: resolve('admin/sources'),
				label: 'Sources',
				icon: 'compass',
				match: (p) => p.startsWith('/admin/sources')
			},
			{
				href: resolve('admin/settings'),
				label: 'Settings',
				icon: 'key',
				match: (p) => p.startsWith('/admin/settings')
			}
		];
</script>

<svelte:head>
	<meta name="robots" content="noindex" />
</svelte:head>

<a class="skip" href="#main">Skip to content</a>

<header class="header">
	<div class="bar">
		<div class="brand">
			<Logo />
			<span class="pill pill-accent">Admin</span>
		</div>
		<nav aria-label="Admin sections" class="tabs">
			{#each tabs as tab (tab.href)}
				<a
					href={tab.href}
					class="tab"
					aria-current={tab.match(page.url.pathname) ? 'page' : undefined}
				>
					<Icon name={tab.icon} size={16} />
					{tab.label}
				</a>
			{/each}
		</nav>
		<div class="end">
			<ThemeSwitcher />
			<a class="btn btn-plain btn-sm" href={resolve('explore')}>
				<Icon name="external" size={16} /> Open the app
			</a>
		</div>
	</div>
</header>

<main id="main" tabindex="-1">
	{@render children()}
</main>

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
		gap: 24px;
		max-width: 1440px;
		margin: 0 auto;
		padding: 0 var(--gutter);
		min-height: 60px;
		flex-wrap: wrap;
	}

	.brand {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.tabs {
		display: flex;
		gap: 4px;
		padding: 3px;
		border-radius: 11px;
		background: var(--control);
	}

	.tab {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 34px;
		padding: 0 14px;
		border-radius: 8px;
		color: var(--text-2);
		font-size: 14px;
		font-weight: 500;
		text-decoration: none;
	}

	.tab:hover {
		color: var(--text);
	}

	.tab[aria-current='page'] {
		background: var(--raised);
		color: var(--text);
		box-shadow: var(--shadow-sm);
	}

	.end {
		margin-left: auto;
		display: flex;
		align-items: center;
		gap: 12px;
	}

	main {
		max-width: 1440px;
		margin: 0 auto;
		padding: 28px var(--gutter) 72px;
		outline: none;
	}

	@media (max-width: 760px) {
		.bar {
			padding-block: 10px;
			gap: 12px;
		}
		.tabs {
			order: 3;
			width: 100%;
		}
		.tab {
			flex: 1;
			justify-content: center;
		}
	}
</style>
