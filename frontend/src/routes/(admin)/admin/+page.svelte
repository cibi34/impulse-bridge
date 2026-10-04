<script lang="ts">
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { admin, type AdminCollection } from '#lib/api/admin.js';
	import { collectionIdProblem, suggestCollectionId } from '#lib/collection-id.js';
	import { errorMessage } from '#lib/api/index.js';
	import CopyField from '#lib/components/CopyField.svelte';
	import Dialog from '#lib/components/Dialog.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import SearchField from '#lib/components/SearchField.svelte';
	import SegmentedControl from '#lib/components/SegmentedControl.svelte';
	import Switch from '#lib/components/Switch.svelte';
	import { formatDate, plural, timeAgo } from '#lib/format.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';

	type Filter = 'all' | 'submitted' | 'listed' | 'locked';

	let collections = $state<AdminCollection[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let query = $state('');
	let applied = $state('');
	let filter = $state<Filter>('all');

	let keyFor = $state<AdminCollection | null>(null);
	let newLink = $state<string | null>(null);
	let keyOpen = $state(false);
	let deleting = $state<AdminCollection | null>(null);
	let deleteOpen = $state(false);
	let busy = $state(false);

	// ---- changing an id: validated as you type, confirmed by typing the old id ----
	let renaming = $state<AdminCollection | null>(null);
	let renameOpen = $state(false);
	let newId = $state('');
	let confirmText = $state('');
	let renamed = $state<{ from: string; uri: string } | null>(null);

	const wantedId = $derived(newId.trim());
	const idProblem = $derived.by((): string | null => {
		if (!renaming || !wantedId) return null;
		if (wantedId === renaming.id) return 'That is already the collection’s ID.';
		const taken = collections.find((c) => c.id === wantedId);
		if (taken) return `Already used by “${taken.name}”.`;
		const former = collections.find(
			(c) => c.id !== renaming!.id && c.former_ids.includes(wantedId)
		);
		if (former) return `A former ID of “${former.name}” — its old links lead there.`;
		return collectionIdProblem(wantedId);
	});
	const idSuggestion = $derived(wantedId && idProblem ? suggestCollectionId(wantedId) : null);
	const newUri = $derived(renaming ? renaming.uri.replace(/[^/]+$/, wantedId) : '');
	const canRename = $derived(
		!!renaming && !!wantedId && !idProblem && confirmText.trim() === renaming.id && !busy
	);

	function askRename(c: AdminCollection) {
		renaming = c;
		newId = '';
		confirmText = '';
		renamed = null;
		renameOpen = true;
	}

	async function rename() {
		if (!renaming || !canRename) return;
		busy = true;
		const target = renaming;
		try {
			const result = await admin.renameCollection(target.id, wantedId, confirmText.trim());
			const { previous_id, ...updated } = result;
			collections = collections.map((c) => (c.id === previous_id ? updated : c));
			renamed = { from: previous_id, uri: updated.uri };
			renaming = updated;
			toasts.success(`“${updated.name}” now has the ID ${updated.id}`);
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			busy = false;
		}
	}

	onMount(load);

	async function load() {
		try {
			collections = await admin.collections();
			error = null;
		} catch (e) {
			error = errorMessage(e);
		} finally {
			loading = false;
		}
	}

	const counts = $derived({
		all: collections.length,
		submitted: collections.filter((c) => c.submitted_at).length,
		listed: collections.filter((c) => c.listed).length,
		locked: collections.filter((c) => c.disabled).length
	});

	const visible = $derived(
		collections.filter((c) => {
			if (filter === 'submitted' && !c.submitted_at) return false;
			if (filter === 'listed' && !c.listed) return false;
			if (filter === 'locked' && !c.disabled) return false;
			const q = applied.toLowerCase();
			return (
				!q || [c.name, c.id, c.email ?? '', c.description].some((v) => v.toLowerCase().includes(q))
			);
		})
	);

	async function setFlag(c: AdminCollection, flag: 'listed' | 'disabled', value: boolean) {
		const previous = c[flag];
		c[flag] = value;
		try {
			Object.assign(c, await admin.updateCollection(c.id, { [flag]: value }));
			const what =
				flag === 'listed'
					? value
						? 'now listed in /collections'
						: 'no longer listed'
					: value
						? 'locked'
						: 'unlocked';
			toasts.success(`“${c.name}” ${what}`);
		} catch (e) {
			c[flag] = previous;
			toasts.error(errorMessage(e));
		}
	}

	function askNewKey(c: AdminCollection) {
		keyFor = c;
		newLink = null;
		keyOpen = true;
	}

	async function createKey() {
		if (!keyFor) return;
		busy = true;
		try {
			const { edit_key } = await admin.newEditKey(keyFor.id);
			newLink = `${location.origin}/c/${keyFor.id}/edit#key=${edit_key}`;
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			busy = false;
		}
	}

	function askDelete(c: AdminCollection) {
		deleting = c;
		deleteOpen = true;
	}

	async function destroy() {
		if (!deleting) return;
		busy = true;
		const target = deleting;
		try {
			await admin.deleteCollection(target.id);
			collections = collections.filter((c) => c.id !== target.id);
			deleteOpen = false;
			toasts.success(`“${target.name}” deleted`);
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			busy = false;
		}
	}
</script>

<svelte:head>
	<title>Collections — Admin — IMPULSE Curator</title>
</svelte:head>

<header class="head">
	<div>
		<h1 class="large-title">Collections</h1>
		<p class="secondary">
			Curated by visitors. Listed collections appear in the Impulse API's <code>/collections</code>;
			every collection is reachable through its own URL unless it is locked.
		</p>
	</div>
	<dl class="stats">
		<div>
			<dt>Total</dt>
			<dd>{counts.all}</dd>
		</div>
		<div>
			<dt>Submitted</dt>
			<dd>{counts.submitted}</dd>
		</div>
		<div>
			<dt>Listed</dt>
			<dd>{counts.listed}</dd>
		</div>
		<div>
			<dt>Locked</dt>
			<dd>{counts.locked}</dd>
		</div>
	</dl>
</header>

<div class="toolbar">
	<div class="search">
		<SearchField
			bind:value={query}
			label="Search collections"
			placeholder="Search by name, id or email"
			onsubmit={(value) => (applied = value)}
		/>
	</div>
	<SegmentedControl
		legend="Show"
		options={[
			{ value: 'all', label: 'All' },
			{ value: 'submitted', label: 'Submitted' },
			{ value: 'listed', label: 'Listed' },
			{ value: 'locked', label: 'Locked' }
		]}
		bind:value={filter}
	/>
	<p class="footnote secondary" role="status">
		{loading ? 'Loading…' : plural(visible.length, 'collection')}
	</p>
</div>

{#if error}
	<p class="notice" role="alert">{error}</p>
{:else if !loading && visible.length === 0}
	<div class="empty">
		<Icon name="collections" size={32} />
		<p class="secondary">
			{collections.length === 0 ? 'No collections yet.' : 'No collections match.'}
		</p>
	</div>
{:else if visible.length > 0}
	<div class="table-wrap panel">
		<table>
			<thead>
				<tr>
					<th scope="col">Collection</th>
					<th scope="col">Assets</th>
					<th scope="col">Contact</th>
					<th scope="col">Status</th>
					<th scope="col">Listed</th>
					<th scope="col">Locked</th>
					<th scope="col"><span class="visually-hidden">Actions</span></th>
				</tr>
			</thead>
			<tbody>
				{#each visible as c (c.id)}
					<tr class:locked={c.disabled}>
						<td>
							<div class="name-cell">
								<a href={resolve(`c/${c.id}`)} class="name">{c.name}</a>
								<span class="mono id">{c.id}</span>
								{#if c.former_ids.length}
									<span class="caption tertiary">formerly {c.former_ids.join(', ')}</span>
								{/if}
							</div>
						</td>
						<td>{c.item_count}</td>
						<td class="email">{c.email ?? '—'}</td>
						<td>
							{#if c.submitted_at}
								<span class="pill pill-success" title={formatDate(c.submitted_at)}
									>Submitted {timeAgo(c.submitted_at)}</span
								>
							{:else}
								<span class="pill">Not submitted</span>
							{/if}
							<span class="caption tertiary updated">Updated {timeAgo(c.updated_at)}</span>
						</td>
						<td>
							<Switch
								checked={c.listed}
								label="Listed in /collections: {c.name}"
								disabled={c.disabled}
								onchange={(value) => setFlag(c, 'listed', value)}
							/>
						</td>
						<td>
							<Switch
								checked={c.disabled}
								label="Locked: {c.name}"
								onchange={(value) => setFlag(c, 'disabled', value)}
							/>
						</td>
						<td class="actions">
							<button
								type="button"
								class="btn btn-plain btn-icon btn-sm"
								onclick={() => askRename(c)}
							>
								<Icon name="link" size={16} label="Change the ID of {c.name}" />
							</button>
							<button
								type="button"
								class="btn btn-plain btn-icon btn-sm"
								onclick={() => askNewKey(c)}
							>
								<Icon name="key" size={16} label="New edit link for {c.name}" />
							</button>
							<button
								type="button"
								class="btn btn-plain btn-icon btn-sm danger"
								onclick={() => askDelete(c)}
							>
								<Icon name="trash" size={16} label="Delete {c.name}" />
							</button>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}

<Dialog bind:open={keyOpen} title="New edit link" size="md" description={keyFor?.name}>
	{#if newLink}
		<div class="stack">
			<CopyField
				label="Edit link"
				value={newLink}
				hint="Shown only now. Send it to the collection's creator."
			/>
			<p class="footnote secondary">The previous edit link no longer works.</p>
		</div>
	{:else}
		<p class="secondary">
			For a creator who lost the link. The current edit link stops working immediately; signed-in
			creators keep access through their email.
		</p>
	{/if}
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (keyOpen = false)}
			>{newLink ? 'Done' : 'Cancel'}</button
		>
		{#if !newLink}
			<button type="button" class="btn btn-primary" disabled={busy} onclick={createKey}
				>Create new link</button
			>
		{/if}
	{/snippet}
</Dialog>

<Dialog bind:open={renameOpen} title="Change the ID" size="md" description={renaming?.name}>
	{#if renaming && renamed}
		<div class="stack">
			<p class="secondary">
				The collection now has the ID <code>{renaming.id}</code>.
			</p>
			<CopyField
				label="New collection URL"
				value={renamed.uri}
				hint="Use this URL from now on — in IMPULSE and wherever you enter it."
			/>
			<p class="footnote secondary">
				<code>…/collections/{renamed.from}</code> keeps forwarding here, so existing entries don't break.
				The creator's edit link and their browser follow to the new ID on their own.
			</p>
		</div>
	{:else if renaming}
		<form
			class="stack"
			id="rename-form"
			onsubmit={(e) => {
				e.preventDefault();
				rename();
			}}
		>
			<dl class="current">
				<div>
					<dt>Current ID</dt>
					<dd class="mono">{renaming.id}</dd>
				</div>
				<div>
					<dt>Current URL</dt>
					<dd class="mono">{renaming.uri}</dd>
				</div>
			</dl>

			<div class="warning" role="note">
				<Icon name="alert" size={16} />
				<ul>
					<li>
						<strong>The collection gets a new URL.</strong> The old one keeps working as a forwarding
						address — for Unity entries, edit links and browsers that still use it — and stays reserved
						for this collection.
					</li>
					{#if renaming.listed}
						<li>
							It is <strong>listed</strong> in <code>/collections</code> and will appear there under the
							new URL.
						</li>
					{/if}
					{#if renaming.submitted_at}
						<li>
							It was <strong>submitted {timeAgo(renaming.submitted_at)}</strong> — the IMPULSE team may
							have registered the old URL. It keeps working, but tell them the new one.
						</li>
					{/if}
				</ul>
			</div>

			<div class="field">
				<label class="field-label" for="rename-new">New ID</label>
				<input
					id="rename-new"
					class="input mono"
					autocomplete="off"
					spellcheck="false"
					aria-invalid={!!idProblem}
					aria-describedby="rename-new-hint"
					bind:value={newId}
				/>
				<p id="rename-new-hint" class={idProblem ? 'field-error' : 'field-hint'} aria-live="polite">
					{#if idProblem}
						{idProblem}
						{#if idSuggestion}
							<button type="button" class="link" onclick={() => (newId = idSuggestion ?? '')}
								>Use “{idSuggestion}”</button
							>
						{/if}
					{:else if wantedId}
						New URL: <span class="mono">{newUri}</span>
					{:else}
						Lowercase letters, digits and single hyphens, 3–80 characters.
					{/if}
				</p>
			</div>

			<div class="field">
				<label class="field-label" for="rename-confirm">
					To confirm, type the current ID <code>{renaming.id}</code>
				</label>
				<input
					id="rename-confirm"
					class="input mono"
					autocomplete="off"
					spellcheck="false"
					bind:value={confirmText}
				/>
			</div>
		</form>
	{/if}
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (renameOpen = false)}
			>{renamed ? 'Done' : 'Cancel'}</button
		>
		{#if !renamed}
			<button type="submit" form="rename-form" class="btn btn-danger" disabled={!canRename}>
				{busy ? 'Changing…' : 'Change ID'}
			</button>
		{/if}
	{/snippet}
</Dialog>

<Dialog bind:open={deleteOpen} title="Delete this collection?" size="sm">
	<p class="secondary">
		“{deleting?.name}” and its {plural(deleting?.item_count ?? 0, 'asset')} will be removed. Impulse can
		no longer load it. This can't be undone.
	</p>
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (deleteOpen = false)}>Cancel</button>
		<button type="button" class="btn btn-danger" disabled={busy} onclick={destroy}>Delete</button>
	{/snippet}
</Dialog>

<style>
	.head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 24px;
		flex-wrap: wrap;
		margin-bottom: 24px;
	}

	.head p {
		max-width: 640px;
		margin-top: 6px;
	}

	.stats {
		display: flex;
		gap: 10px;
		margin: 0;
	}

	.stats div {
		min-width: 92px;
		padding: 12px 16px;
		border-radius: 14px;
		background: var(--surface);
		border: 1px solid var(--separator);
	}

	dt {
		font-size: 12px;
		color: var(--text-3);
	}

	dd {
		margin: 2px 0 0;
		font-size: 22px;
		font-weight: 600;
	}

	.toolbar {
		display: flex;
		align-items: center;
		gap: 12px 16px;
		flex-wrap: wrap;
		margin-bottom: 18px;
	}

	.search {
		flex: 0 1 360px;
		min-width: 220px;
	}

	.table-wrap {
		overflow-x: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 14px;
	}

	th {
		padding: 12px 16px;
		text-align: left;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-3);
		border-bottom: 1px solid var(--separator);
		white-space: nowrap;
	}

	td {
		padding: 12px 16px;
		border-bottom: 1px solid var(--separator);
		vertical-align: middle;
	}

	tbody tr:last-child td {
		border-bottom: 0;
	}

	tr.locked .name {
		color: var(--text-2);
	}

	.name-cell {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 220px;
	}

	.name {
		color: var(--text);
		font-weight: 600;
		text-decoration: none;
	}

	.name:hover {
		text-decoration: underline;
	}

	.id {
		color: var(--text-3);
		font-size: 12px;
	}

	.email {
		color: var(--text-2);
		max-width: 220px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.updated {
		display: block;
		margin-top: 4px;
	}

	.actions {
		white-space: nowrap;
		text-align: right;
	}

	.danger {
		color: var(--danger-text);
	}

	.stack {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.notice {
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
	}

	.empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 64px 16px;
		color: var(--text-3);
	}

	code {
		font-family: var(--font-mono);
		font-size: 0.9em;
	}

	.current {
		margin: 0;
		padding: 10px 14px;
		border-radius: 10px;
		background: var(--surface-sunken);
		font-size: 13px;
	}

	.current div {
		display: grid;
		grid-template-columns: 100px minmax(0, 1fr);
		gap: 12px;
		padding: 3px 0;
	}

	.current dt {
		color: var(--text-2);
	}

	.current dd {
		margin: 0;
		overflow-wrap: anywhere;
	}

	.warning {
		display: flex;
		gap: 10px;
		align-items: flex-start;
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 13.5px;
	}

	.warning ul {
		margin: 0;
		padding-left: 18px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.link {
		padding: 0;
		border: 0;
		background: none;
		color: var(--link);
		font-size: inherit;
		text-decoration: underline;
		text-underline-offset: 3px;
	}
</style>
