<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import {
		api,
		ApiError,
		errorMessage,
		type Collection,
		type CollectionItem
	} from '#lib/api/index.js';
	import AssetDialog from '#lib/components/AssetDialog.svelte';
	import CopyField from '#lib/components/CopyField.svelte';
	import Credits from '#lib/components/Credits.svelte';
	import Dialog from '#lib/components/Dialog.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import ItemList from '#lib/components/ItemList.svelte';
	import SubmitDialog from '#lib/components/SubmitDialog.svelte';
	import { plural, timeAgo } from '#lib/format.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { library } from '#lib/stores/library.svelte.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';

	const id = $derived(page.params.id ?? '');

	let collection = $state<Collection | null>(null);
	let key = $state<string | null>(null);
	let loadError = $state<string | null>(null);
	let saving = $state(false);
	let savedAt = $state<string | null>(null);

	let name = $state('');
	let description = $state('');
	let email = $state('');

	let detail = $state<CollectionItem | null>(null);
	let detailOpen = $state(false);
	let submitOpen = $state(false);
	let deleteOpen = $state(false);
	let resetOpen = $state(false);
	let busy = $state(false);

	onMount(() => {
		// An edit link carries its key in the fragment (#key=…), which never
		// reaches a server. Keep it on this device and take it out of the URL.
		const fromLink = new URLSearchParams(location.hash.slice(1)).get('key');
		if (fromLink) {
			library.save(id, library.get(id)?.name ?? 'Untitled collection', fromLink);
			history.replaceState(history.state, '', location.pathname + location.search);
		}
		key = library.keyFor(id);
		load();
	});

	async function load() {
		try {
			const result = await api.collection(id, key);
			if (result.id !== id) {
				// Opened by a former id: move this device's entry and the address.
				library.follow(id, result.id);
				await goto(resolve(`c/${result.id}/edit`), { replace: true });
			}
			collection = result;
			name = result.name;
			description = result.description;
			email = result.email ?? '';
			if (result.can_edit) library.save(result.id, result.name, key);
		} catch (e) {
			loadError = e instanceof ApiError && e.status === 404 ? 'not-found' : errorMessage(e);
		}
	}

	const editable = $derived(!!collection?.can_edit && !collection.locked);
	// What Unity gets: visible assets with a licence IMPULSE accepts.
	const served = $derived(collection?.items.filter((i) => i.published && i.licence.allowed) ?? []);
	const visibleCount = $derived(served.length);
	const notAccepted = $derived(collection?.items.filter((i) => !i.licence.allowed).length ?? 0);
	const editLink = $derived(key ? `${location.origin}/c/${id}/edit#key=${key}` : null);

	async function save(changes: { name?: string; description?: string; email?: string }) {
		if (!collection || !editable) return;
		saving = true;
		try {
			const updated = await api.updateCollection(id, key, changes);
			collection = { ...collection, ...updated, items: collection.items };
			library.rename(id, updated.name);
			savedAt = new Date().toISOString();
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			saving = false;
		}
	}

	function saveName() {
		const trimmed = name.trim();
		if (!trimmed) {
			name = collection?.name ?? '';
			return;
		}
		if (trimmed !== collection?.name) save({ name: trimmed });
	}

	function saveDescription() {
		if (description.trim() !== collection?.description) save({ description: description.trim() });
	}

	function saveEmail(event: SubmitEvent) {
		event.preventDefault();
		if (email.trim() !== (collection?.email ?? '')) save({ email: email.trim() });
	}

	async function reorder(assetIds: string[]) {
		if (!collection) return;
		const previous = collection.items;
		const byId = new Map(previous.map((i) => [i.asset_id, i]));
		collection.items = assetIds.map((aid) => byId.get(aid)!).filter(Boolean);
		try {
			await api.reorder(id, key, assetIds);
			savedAt = new Date().toISOString();
		} catch (e) {
			collection.items = previous;
			toasts.error(errorMessage(e));
		}
	}

	async function togglePublished(item: CollectionItem, published: boolean) {
		if (!collection) return;
		const target = collection.items.find((i) => i.asset_id === item.asset_id);
		if (!target) return;
		target.published = published;
		try {
			await api.setPublished(id, key, item.asset_id, published);
			savedAt = new Date().toISOString();
		} catch (e) {
			target.published = !published;
			toasts.error(errorMessage(e));
		}
	}

	async function remove(item: CollectionItem) {
		if (!collection) return;
		const before = collection.items.map((i) => i.asset_id);
		collection.items = collection.items.filter((i) => i.asset_id !== item.asset_id);
		collection.item_count -= 1;
		try {
			await api.removeItem(id, key, item.asset_id);
			toasts.show(`Removed “${item.asset.title || 'asset'}”`, {
				action: { label: 'Undo', run: () => undoRemove(item, before) }
			});
		} catch (e) {
			await load();
			toasts.error(errorMessage(e));
		}
	}

	async function undoRemove(item: CollectionItem, order: string[]) {
		try {
			const { added } = await api.addItems(id, key, [
				{ source: item.source, asset_id: item.source_asset_id }
			]);
			if (added[0] && !item.published) await api.setPublished(id, key, added[0].asset_id, false);
			const restored = order.map((aid) =>
				aid === item.asset_id && added[0] ? added[0].asset_id : aid
			);
			await api.reorder(id, key, restored);
			await load();
		} catch (e) {
			toasts.error(errorMessage(e));
		}
	}

	async function refresh() {
		busy = true;
		try {
			const result = await api.refresh(id, key);
			await load();
			toasts.success(
				result.failed.length
					? `${plural(result.refreshed, 'asset')} updated, ${result.failed.length} unavailable at the source`
					: `${plural(result.refreshed, 'asset')} updated from their sources`
			);
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			busy = false;
		}
	}

	async function emailLink() {
		if (!key) return;
		try {
			const { sent_to } = await api.emailEditLink(id, key);
			toasts.success(`Edit link sent to ${sent_to}`);
		} catch (e) {
			toasts.error(errorMessage(e));
		}
	}

	async function resetKey() {
		busy = true;
		try {
			const { edit_key } = await api.resetKey(id, key);
			key = edit_key;
			library.setKey(id, edit_key);
			resetOpen = false;
			toasts.success('New edit link created — the old one no longer works');
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			busy = false;
		}
	}

	async function destroy() {
		busy = true;
		try {
			await api.deleteCollection(id, key);
			library.forget(id);
			toasts.success(`Collection “${collection?.name}” deleted`);
			goto(resolve('my'));
		} catch (e) {
			toasts.error(errorMessage(e));
			busy = false;
		}
	}

	function submitted(ids: string[]) {
		if (collection && ids.includes(collection.id))
			collection.submitted_at = new Date().toISOString();
	}
</script>

<svelte:head>
	<title>{collection?.name ?? 'Collection'} — IMPULSE Curator</title>
</svelte:head>

<div class="page">
	<nav aria-label="Breadcrumb" class="crumbs footnote">
		<a href={resolve('my')}>My collections</a>
		<span aria-hidden="true">›</span>
		<span aria-current="page">{collection?.name ?? '…'}</span>
	</nav>

	{#if loadError === 'not-found'}
		<div class="empty">
			<h1 class="title">This collection doesn't exist</h1>
			<p class="secondary">It may have been deleted. Check the link, or start a new collection.</p>
			<a class="btn btn-primary" href={resolve('explore')}>Explore</a>
		</div>
	{:else if loadError}
		<p class="notice" role="alert">{loadError}</p>
	{:else if collection && !collection.can_edit}
		<div class="empty">
			<Icon name="lock" size={32} />
			<h1 class="title">You need the edit link</h1>
			<p class="secondary">
				Open the collection with its edit link{app.config?.sign_in_available
					? ', or sign in with the email address it was created with'
					: ''}.
			</p>
			<div class="row">
				<a class="btn" href={resolve(`c/${id}`)}>View the collection</a>
				{#if app.config?.sign_in_available}<a class="btn btn-primary" href={resolve('signin')}
						>Sign in</a
					>{/if}
			</div>
		</div>
	{:else if collection}
		{#if collection.locked}
			<p class="notice" role="status">
				<Icon name="lock" size={16} /> An administrator locked this collection. It can't be changed and
				isn't served to IMPULSE.
			</p>
		{/if}
		<h1 class="visually-hidden">Edit “{collection.name}”</h1>
		<div class="editor">
			<div class="main">
				<div class="field">
					<label class="field-label" for="name">Collection name</label>
					<input
						id="name"
						class="name-input"
						bind:value={name}
						maxlength="120"
						disabled={!editable}
						onblur={saveName}
						onkeydown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLInputElement).blur()}
					/>
				</div>
				<div class="field">
					<label class="field-label" for="description">Description</label>
					<textarea
						id="description"
						class="input"
						rows="2"
						maxlength="2000"
						bind:value={description}
						disabled={!editable}
						onblur={saveDescription}
						placeholder="What is this collection for?"></textarea>
				</div>
				<div class="pills">
					<span class="pill"
						>{plural(collection.item_count, 'asset')} · {visibleCount} visible in Unity</span
					>
					<span class="pill" role="status">
						{saving
							? 'Saving…'
							: savedAt
								? `Saved ${timeAgo(savedAt)}`
								: `Updated ${timeAgo(collection.updated_at)}`}
					</span>
					{#if collection.submitted_at}
						<span class="pill pill-success">Submitted {timeAgo(collection.submitted_at)}</span>
					{:else}
						<span class="pill pill-warning">Not submitted yet</span>
					{/if}
				</div>

				<section class="panel assets" aria-labelledby="assets-title">
					<div class="panel-head">
						<h2 id="assets-title" class="headline">Assets</h2>
						{#if editable}
							<a class="btn btn-sm" href={resolve(`explore?add=${encodeURIComponent(id)}`)}>
								<Icon name="plus" size={16} /> Add assets
							</a>
						{/if}
					</div>
					{#if collection.items.length > 0}
						<ItemList
							items={collection.items}
							disabled={!editable}
							onreorder={reorder}
							ontoggle={togglePublished}
							onremove={remove}
							onopen={(item) => {
								detail = item;
								detailOpen = true;
							}}
						/>
					{:else}
						<div class="empty small">
							<p class="secondary">No assets yet.</p>
							{#if editable}
								<a
									class="btn btn-primary btn-sm"
									href={resolve(`explore?add=${encodeURIComponent(id)}`)}>Add assets</a
								>
							{/if}
						</div>
					{/if}
					{#if notAccepted > 0}
						<p class="licence-note footnote" role="note">
							<Icon name="alert" size={16} />
							<span>
								{plural(notAccepted, 'asset')}
								{notAccepted === 1 ? 'has' : 'have'} a licence IMPULSE doesn't accept (any more) and {notAccepted ===
								1
									? "isn't"
									: "aren't"} sent to Unity. Remove {notAccepted === 1 ? 'it' : 'them'}, or ask the
								IMPULSE team.
							</span>
						</p>
					{/if}
				</section>

				<section class="panel credits">
					<Credits name={collection.name} items={served} />
					<p class="caption tertiary">Lists the assets that are visible in Unity.</p>
				</section>
			</div>

			<aside class="panel share" aria-labelledby="share-title">
				<h2 id="share-title" class="headline">Share</h2>
				<CopyField
					label="Collection URL"
					hint="Read-only. This is what IMPULSE and Unity use."
					value={collection.uri}
				/>
				{#if editLink}
					<CopyField
						label="Edit link"
						hint="Anyone with this link can change the collection. Keep it private."
						value={editLink}
						display={editLink.replace(/#key=.*/, '#key=••••••••')}
					/>
				{/if}

				<form class="email" onsubmit={saveEmail}>
					<label class="field-label" for="email"
						>Your email <span class="tertiary">(optional)</span></label
					>
					<div class="row">
						<input
							id="email"
							class="input"
							type="email"
							autocomplete="email"
							bind:value={email}
							disabled={!editable}
						/>
						<button
							type="submit"
							class="btn btn-sm"
							disabled={!editable || email.trim() === (collection.email ?? '')}>Save</button
						>
					</div>
					<span class="field-hint">
						{app.config?.sign_in_available ? 'To sign in on other devices. ' : ''}Never shown
						publicly.
					</span>
					{#if key && collection.email && app.config?.sign_in_available}
						<button type="button" class="link" onclick={emailLink}>Email me the edit link</button>
					{/if}
				</form>

				<div class="divider"></div>

				<button
					type="button"
					class="btn btn-primary submit"
					disabled={!editable}
					onclick={() => (submitOpen = true)}
				>
					<Icon name="mail" /> Submit to IMPULSE
				</button>
				<p class="caption tertiary center">
					Opens a pre-filled email to the IMPULSE team. Several collections can be submitted at once
					from <a href={resolve('my')}>My collections</a>.
				</p>

				<div class="divider"></div>

				<div class="actions">
					<a class="btn btn-plain btn-sm" href={resolve(`c/${id}`)}
						><Icon name="eye" size={16} /> View public page</a
					>
					<button
						type="button"
						class="btn btn-plain btn-sm"
						disabled={!editable || busy}
						onclick={refresh}
					>
						<Icon name="refresh" size={16} /> Update from sources
					</button>
					<button
						type="button"
						class="btn btn-plain btn-sm"
						disabled={!editable || busy}
						onclick={() => (resetOpen = true)}
					>
						<Icon name="key" size={16} /> New edit link
					</button>
					<button
						type="button"
						class="btn btn-plain btn-sm danger"
						disabled={!editable || busy}
						onclick={() => (deleteOpen = true)}
					>
						<Icon name="trash" size={16} /> Delete collection
					</button>
				</div>
			</aside>
		</div>
	{:else}
		<p class="secondary" role="status">Loading…</p>
	{/if}
</div>

<AssetDialog
	bind:open={detailOpen}
	asset={detail?.asset ?? null}
	licence={detail?.licence}
	sourceName={detail ? app.sourceName(detail.source) : ''}
/>
<SubmitDialog bind:open={submitOpen} collections={[{ id, key }]} onsubmitted={submitted} />

<Dialog bind:open={resetOpen} title="Create a new edit link?" size="sm">
	<p class="secondary">
		The current edit link stops working immediately, on every device it was shared with.
	</p>
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (resetOpen = false)}>Cancel</button>
		<button type="button" class="btn btn-primary" disabled={busy} onclick={resetKey}
			>Create new link</button
		>
	{/snippet}
</Dialog>

<Dialog bind:open={deleteOpen} title="Delete this collection?" size="sm">
	<p class="secondary">
		“{collection?.name}” will be removed for everyone, and IMPULSE can no longer load it. This can't
		be undone.
	</p>
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (deleteOpen = false)}>Cancel</button>
		<button type="button" class="btn btn-danger" disabled={busy} onclick={destroy}>Delete</button>
	{/snippet}
</Dialog>

<style>
	.page {
		padding: 28px var(--gutter) 72px;
	}

	.crumbs {
		display: flex;
		gap: 6px;
		margin-bottom: 18px;
		color: var(--text-3);
	}

	.crumbs a {
		color: var(--text-2);
		text-decoration: none;
	}

	.crumbs a:hover {
		text-decoration: underline;
	}

	.editor {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 360px;
		gap: 32px;
		align-items: start;
	}

	.main {
		display: flex;
		flex-direction: column;
		gap: 20px;
		min-width: 0;
	}

	.name-input {
		margin: 0;
		padding: 2px 0;
		border: 0;
		border-radius: 6px;
		background: transparent;
		color: var(--text);
		font-size: clamp(28px, 4vw, 34px);
		line-height: 1.15;
		font-weight: 700;
		letter-spacing: -0.025em;
	}

	.name-input:hover:not(:disabled) {
		background: var(--control);
	}

	.pills {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	.assets {
		overflow: hidden;
	}

	.licence-note {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		margin: 0;
		padding: 12px 20px;
		border-top: 1px solid var(--separator);
		background: var(--warning-soft);
		color: var(--warning-text);
	}

	.credits {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 20px 22px;
	}

	.panel-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 14px 16px 14px 20px;
		border-bottom: 1px solid var(--separator);
	}

	.share {
		position: sticky;
		top: 28px;
		display: flex;
		flex-direction: column;
		gap: 18px;
		padding: 22px;
	}

	.email {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.row {
		display: flex;
		gap: 8px;
		align-items: center;
		flex-wrap: wrap;
	}

	.email .row .input {
		flex: 1;
		min-width: 0;
	}

	.link {
		align-self: flex-start;
		padding: 4px 0;
		border: 0;
		background: none;
		color: var(--link);
		font-size: 13px;
	}

	.link:hover {
		text-decoration: underline;
	}

	.divider {
		height: 1px;
		background: var(--separator);
	}

	.submit {
		width: 100%;
	}

	.center {
		text-align: center;
	}

	.actions {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
	}

	.actions .btn {
		width: 100%;
		justify-content: flex-start;
	}

	.danger {
		color: var(--danger-text);
	}

	.notice {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 18px;
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 14px;
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		max-width: 520px;
		margin: 64px auto;
		text-align: center;
		color: var(--text-3);
	}

	.empty h1 {
		color: var(--text);
	}

	.empty.small {
		margin: 32px auto;
	}

	@media (max-width: 1100px) {
		.editor {
			grid-template-columns: minmax(0, 1fr);
		}
		.share {
			position: static;
		}
	}
</style>
