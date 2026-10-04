<script lang="ts">
	import { resolve } from '$app/paths';
	import { api, errorMessage, type CollectionSummary } from '#lib/api/index.js';
	import AssetThumb from '#lib/components/AssetThumb.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import SubmitDialog from '#lib/components/SubmitDialog.svelte';
	import { plural, timeAgo } from '#lib/format.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';

	let collections = $state<CollectionSummary[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let picked = $state<string[]>([]);
	let submitOpen = $state(false);

	// Collections remembered on this device, plus — when signed in — every
	// collection created with the account's email address.
	$effect(() => {
		const ids = library.entries.map((e) => e.id);
		const signedIn = !!app.email;
		loading = true;
		Promise.all([api.summaries(ids), signedIn ? api.myCollections() : Promise.resolve([])])
			.then(([summaries, remote]) => {
				// Renamed or deleted since: keep this device's entries (and keys) in step.
				library.apply(summaries);
				const local = summaries.collections;
				// eslint-disable-next-line svelte/prefer-svelte-reactivity -- local, not state
				const merged = new Map<string, CollectionSummary>();
				for (const c of [...local, ...remote]) merged.set(c.id, c);
				collections = [...merged.values()].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
				error = null;
			})
			.catch((e) => (error = errorMessage(e)))
			.finally(() => (loading = false));
	});

	const allPicked = $derived(collections.length > 0 && picked.length === collections.length);

	function togglePick(id: string) {
		picked = picked.includes(id) ? picked.filter((p) => p !== id) : [...picked, id];
	}

	function forget(summary: CollectionSummary) {
		library.forget(summary.id);
		picked = picked.filter((p) => p !== summary.id);
		toasts.show(`“${summary.name}” removed from this device`, {
			action: { label: 'Undo', run: () => library.save(summary.id, summary.name, null) }
		});
	}

	function submitted(ids: string[]) {
		const now = new Date().toISOString();
		collections = collections.map((c) => (ids.includes(c.id) ? { ...c, submitted_at: now } : c));
		picked = [];
	}

	const submitList = $derived(picked.map((id) => ({ id, key: library.keyFor(id) })));

	// ---- sign-in by email ----
	let email = $state('');
	let sent = $state<string | null>(null);
	let sending = $state(false);

	async function requestLink(event: SubmitEvent) {
		event.preventDefault();
		sending = true;
		try {
			sent = (await api.requestSignIn(email.trim())).detail;
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			sending = false;
		}
	}
</script>

<svelte:head>
	<title>My collections — IMPULSE Curator</title>
</svelte:head>

<div class="page">
	<header class="head">
		<div>
			<h1 class="large-title">My collections</h1>
			<p class="secondary">
				{app.email
					? `On this device and created with ${app.email}.`
					: 'Collections you created or opened on this device.'}
			</p>
		</div>
		<a class="btn btn-primary" href={resolve('explore')}
			><Icon name="plus" size={16} /> New collection</a
		>
	</header>

	{#if error}
		<p class="notice" role="alert">{error}</p>
	{/if}

	{#if collections.length > 0}
		<div class="toolbar">
			<label class="check-all">
				<input
					type="checkbox"
					checked={allPicked}
					indeterminate={picked.length > 0 && !allPicked}
					onchange={() => (picked = allPicked ? [] : collections.map((c) => c.id))}
				/>
				Select all
			</label>
			<span class="footnote secondary" role="status"
				>{picked.length ? `${picked.length} selected` : ''}</span
			>
			<button
				type="button"
				class="btn btn-primary btn-sm"
				disabled={picked.length === 0}
				onclick={() => (submitOpen = true)}
			>
				<Icon name="mail" size={16} />
				Submit {picked.length > 1 ? `${picked.length} collections` : 'to IMPULSE'}
			</button>
		</div>

		<ul class="list">
			{#each collections as c (c.id)}
				{@const entry = library.get(c.id)}
				<li class:picked={picked.includes(c.id)}>
					<input
						type="checkbox"
						class="pick"
						aria-label="Select {c.name}"
						checked={picked.includes(c.id)}
						onchange={() => togglePick(c.id)}
					/>
					<span class="previews" aria-hidden="true">
						{#each [0, 1, 2, 3] as i (i)}
							<span class="cell"><AssetThumb src={c.previews[i] ?? null} /></span>
						{/each}
					</span>
					<div class="text">
						<a class="name" href={resolve(entry?.key || app.email ? `c/${c.id}/edit` : `c/${c.id}`)}
							>{c.name}</a
						>
						<span class="footnote secondary">
							{plural(c.item_count, 'asset')} · updated {timeAgo(c.updated_at)}
						</span>
						<span>
							{#if c.submitted_at}
								<span class="pill pill-success">Submitted {timeAgo(c.submitted_at)}</span>
							{:else}
								<span class="pill pill-warning">Not submitted yet</span>
							{/if}
						</span>
					</div>
					{#if entry}
						<button type="button" class="btn btn-plain btn-icon btn-sm" onclick={() => forget(c)}>
							<Icon name="close" size={16} label="Remove {c.name} from this device" />
						</button>
					{/if}
				</li>
			{/each}
		</ul>
	{:else if !loading}
		<div class="empty">
			<Icon name="collections" size={36} />
			<h2 class="headline">No collections yet</h2>
			<p class="secondary">
				Explore the archives, select what you like and create your first collection.
			</p>
			<a class="btn btn-primary" href={resolve('explore')}>Start exploring</a>
		</div>
	{/if}

	{#if app.config?.sign_in_available && !app.email}
		<section class="panel signin" aria-labelledby="signin-title">
			<div>
				<h2 id="signin-title" class="headline">Using another device?</h2>
				<p class="footnote secondary">
					Get a sign-in link for the email address you created your collections with.
				</p>
			</div>
			{#if sent}
				<p class="footnote success" role="status"><Icon name="check" size={16} /> {sent}</p>
			{:else}
				<form class="row" onsubmit={requestLink}>
					<label class="visually-hidden" for="signin-email">Email address</label>
					<input
						id="signin-email"
						class="input"
						type="email"
						required
						autocomplete="email"
						bind:value={email}
						placeholder="you@example.org"
					/>
					<button type="submit" class="btn" disabled={sending}
						>{sending ? 'Sending…' : 'Send link'}</button
					>
				</form>
			{/if}
		</section>
	{/if}
</div>

<SubmitDialog bind:open={submitOpen} collections={submitList} onsubmitted={submitted} />

<style>
	.page {
		max-width: 960px;
		padding: 32px var(--gutter) 72px;
	}

	.head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 20px;
		flex-wrap: wrap;
		margin-bottom: 28px;
	}

	.toolbar {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 0 12px 12px;
	}

	.toolbar .btn {
		margin-left: auto;
	}

	.check-all {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 14px;
	}

	input[type='checkbox'] {
		width: 20px;
		height: 20px;
		margin: 0;
		accent-color: var(--action);
	}

	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		border-radius: var(--radius-panel);
		background: var(--bg-elevated);
		border: 1px solid var(--separator);
		overflow: hidden;
	}

	li {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 14px 12px;
		border-bottom: 1px solid var(--separator);
	}

	li:last-child {
		border-bottom: 0;
	}

	li.picked {
		background: var(--accent-soft);
	}

	.previews {
		flex-shrink: 0;
		display: grid;
		grid-template-columns: repeat(2, 30px);
		gap: 2px;
		border-radius: 10px;
		overflow: hidden;
	}

	.cell {
		width: 30px;
		height: 30px;
		background: var(--surface);
	}

	.cell :global(.caption),
	.cell :global(svg) {
		display: none;
	}

	.text {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
		align-items: flex-start;
	}

	.name {
		color: var(--text);
		font-weight: 600;
		font-size: 16px;
		text-decoration: none;
	}

	.name:hover {
		text-decoration: underline;
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 64px 16px;
		text-align: center;
		color: var(--text-3);
	}

	.empty h2 {
		color: var(--text);
	}

	.signin {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 20px;
		flex-wrap: wrap;
		margin-top: 32px;
		padding: 20px 22px;
	}

	.row {
		display: flex;
		gap: 8px;
		flex: 1 1 320px;
		max-width: 440px;
	}

	.success {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--success-text);
	}

	.notice {
		padding: 12px 14px;
		margin-bottom: 18px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
	}
</style>
