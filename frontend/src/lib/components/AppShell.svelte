<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import type { Snippet } from 'svelte';
	import { api } from '#lib/api/index.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';
	import Dialog from './Dialog.svelte';
	import Icon, { type IconName } from './Icon.svelte';
	import Logo from './Logo.svelte';
	import SiteFooter from './SiteFooter.svelte';
	import ThemeSwitcher from './ThemeSwitcher.svelte';

	let { children }: { children: Snippet } = $props();

	let menuOpen = $state(false);

	const nav: { href: string; label: string; icon: IconName; match: string }[] = [
		{ href: resolve('explore'), label: 'Explore', icon: 'search', match: '/explore' },
		{ href: resolve('my'), label: 'My collections', icon: 'collections', match: '/my' },
		{ href: resolve('#how'), label: 'How it works', icon: 'help', match: '/#how' }
	];

	const onExplore = $derived(page.url.pathname.startsWith('/explore'));
	const activeSource = $derived(page.url.searchParams.get('source') ?? 'all');
	const currentCollection = $derived(page.params.id ?? null);

	function isActive(match: string): boolean {
		if (match === '/my')
			return page.url.pathname.startsWith('/my') || page.url.pathname.startsWith('/c/');
		return page.url.pathname.startsWith(match);
	}

	function pickSource(id: string) {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- builds a URL, not state
		const params = new URLSearchParams(page.url.search);
		if (id === 'all') params.delete('source');
		else params.set('source', id);
		const query = params.toString();
		goto(query ? resolve(`explore?${query}`) : resolve('explore'), { reset: false });
	}

	async function signOut() {
		try {
			await api.signOut();
			app.email = null;
			toasts.show('Signed out');
		} catch {
			toasts.error('Signing out failed. Please try again.');
		}
	}

	$effect(() => {
		// Close the mobile menu after navigating.
		void page.url.pathname;
		menuOpen = false;
	});
</script>

<a class="skip" href="#main">Skip to content</a>

<div class="shell">
	<aside class="sidebar" aria-label="Main navigation">
		<div class="brand"><Logo /></div>

		<nav aria-label="Sections" class="nav">
			{#each nav as item (item.href)}
				<a
					href={item.href}
					class="nav-item"
					aria-current={isActive(item.match) ? 'page' : undefined}
				>
					<Icon name={item.icon} />
					{item.label}
				</a>
			{/each}
		</nav>

		{#if onExplore && app.sources.length > 0}
			<section class="group" aria-labelledby="sources-heading">
				<h2 id="sources-heading" class="group-title">Sources</h2>
				<ul>
					<li>
						<button
							type="button"
							class="source"
							aria-pressed={activeSource === 'all'}
							onclick={() => pickSource('all')}
						>
							<span class="dot all" aria-hidden="true"></span>All sources
						</button>
					</li>
					{#each app.sources as source (source.id)}
						<li>
							<button
								type="button"
								class="source"
								aria-pressed={activeSource === source.id}
								onclick={() => pickSource(source.id)}
							>
								<span class="dot" style:background={app.sourceColor(source.id)} aria-hidden="true"
								></span>
								<span class="source-name">{source.name ?? source.id}</span>
							</button>
						</li>
					{/each}
				</ul>
			</section>
		{:else if library.entries.length > 0}
			<section class="group" aria-labelledby="device-heading">
				<h2 id="device-heading" class="group-title">On this device</h2>
				<ul>
					{#each library.entries.slice(0, 8) as entry (entry.id)}
						<li>
							<a
								class="source"
								href={resolve(entry.key ? `c/${entry.id}/edit` : `c/${entry.id}`)}
								aria-current={currentCollection === entry.id ? 'page' : undefined}
							>
								<span class="source-name">{entry.name}</span>
							</a>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<div class="sidebar-bottom">
			{#if app.email}
				<div class="account">
					<Icon name="user" size={16} />
					<span class="email" title={app.email}>{app.email}</span>
					<button type="button" class="btn btn-plain btn-icon btn-sm" onclick={signOut}>
						<Icon name="signOut" size={16} label="Sign out" />
					</button>
				</div>
			{:else if app.config?.sign_in_available}
				<a class="account-link" href={resolve('signin')}>
					<Icon name="user" size={16} /> Sign in to see your collections
				</a>
			{/if}
			<ThemeSwitcher />
			<SiteFooter compact />
		</div>
	</aside>

	<header class="topbar">
		<Logo height={15} />
		<button
			type="button"
			class="btn btn-plain btn-icon"
			aria-haspopup="dialog"
			onclick={() => (menuOpen = true)}
		>
			<Icon name="menu" size={22} label="Menu" />
		</button>
	</header>

	<main id="main" tabindex="-1">
		{@render children()}
	</main>
</div>

<Dialog bind:open={menuOpen} title="Menu" size="sm">
	<nav aria-label="Sections" class="menu-nav">
		{#each nav as item (item.href)}
			<a href={item.href} class="nav-item" aria-current={isActive(item.match) ? 'page' : undefined}>
				<Icon name={item.icon} />
				{item.label}
			</a>
		{/each}
		{#if app.email}
			<button type="button" class="nav-item" onclick={signOut}>
				<Icon name="signOut" /> Sign out ({app.email})
			</button>
		{:else if app.config?.sign_in_available}
			<a class="nav-item" href={resolve('signin')}><Icon name="user" /> Sign in</a>
		{/if}
	</nav>
	<div class="menu-bottom">
		<ThemeSwitcher />
		<SiteFooter compact />
	</div>
</Dialog>

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

	.shell {
		display: grid;
		grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
		min-height: 100dvh;
		/* Floating bars centre on the content, not on the window. */
		--bar-offset: calc(var(--sidebar-width) / 2);
	}

	.sidebar {
		position: sticky;
		top: 0;
		height: 100dvh;
		display: flex;
		flex-direction: column;
		gap: 28px;
		padding: 22px 14px 20px;
		overflow-y: auto;
		background: var(--bg-elevated);
		border-right: 1px solid var(--separator);
	}

	.brand {
		padding: 4px 10px;
	}

	.nav,
	.menu-nav {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.nav-item {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 40px;
		padding: 0 10px;
		border: 0;
		border-radius: 9px;
		background: transparent;
		color: var(--text);
		font: inherit;
		text-align: left;
		text-decoration: none;
	}

	.nav-item:hover {
		background: var(--control);
	}

	.nav-item[aria-current='page'] {
		background: var(--accent-soft);
		color: var(--accent-text);
		font-weight: 500;
	}

	.group ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.group-title {
		margin: 0 0 6px;
		padding: 0 10px;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-3);
	}

	.source {
		display: flex;
		align-items: center;
		gap: 10px;
		width: 100%;
		min-height: 36px;
		padding: 0 10px;
		border: 0;
		border-radius: 9px;
		background: transparent;
		color: var(--text-2);
		font: inherit;
		font-size: 14px;
		text-align: left;
		text-decoration: none;
	}

	.source:hover {
		background: var(--control);
		color: var(--text);
	}

	.source[aria-pressed='true'],
	.source[aria-current='page'] {
		background: var(--control);
		color: var(--text);
		font-weight: 500;
	}

	.source-name {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.dot {
		flex-shrink: 0;
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}

	.dot.all {
		background: var(--brand-gradient);
	}

	.sidebar-bottom {
		margin-top: auto;
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 16px 10px 0;
		border-top: 1px solid var(--separator);
	}

	.account,
	.account-link {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 13px;
		color: var(--text-2);
	}

	.account-link {
		text-decoration: none;
		color: var(--link);
	}

	.email {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.topbar {
		display: none;
	}

	main {
		min-width: 0;
		outline: none;
	}

	.menu-bottom {
		display: flex;
		flex-direction: column;
		gap: 18px;
		margin-top: 22px;
		padding-top: 18px;
		border-top: 1px solid var(--separator);
	}

	@media (max-width: 900px) {
		.shell {
			grid-template-columns: minmax(0, 1fr);
			--bar-offset: 0px;
		}
		.sidebar {
			display: none;
		}
		.topbar {
			position: sticky;
			top: 0;
			z-index: 10;
			display: flex;
			align-items: center;
			justify-content: space-between;
			height: 56px;
			padding: 0 6px 0 16px;
			background: var(--glass);
			backdrop-filter: saturate(180%) blur(20px);
			-webkit-backdrop-filter: saturate(180%) blur(20px);
			border-bottom: 1px solid var(--separator);
		}
	}
</style>
