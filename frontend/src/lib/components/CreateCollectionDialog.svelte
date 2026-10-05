<script lang="ts">
	import { resolve } from '$app/paths';
	import { api, errorMessage, type Collection, type Failure } from '#lib/api/index.js';
	import { plural } from '#lib/format.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { selection } from '#lib/stores/selection.svelte.js';
	import Dialog from './Dialog.svelte';

	let {
		open = $bindable(false),
		oncreated
	}: {
		open?: boolean;
		oncreated: (result: {
			collection: Collection;
			editKey: string;
			failed: Failure[];
			/** The address the edit link was emailed to, if any. */
			emailedTo: string | null;
		}) => void;
	} = $props();

	const id = $props.id();
	let name = $state('');
	let description = $state('');
	let email = $state('');
	let busy = $state(false);
	let error = $state<string | null>(null);
	let nameInvalid = $state(false);

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		error = null;
		nameInvalid = !name.trim();
		if (nameInvalid) {
			document.getElementById(`${id}-name`)?.focus();
			return;
		}
		busy = true;
		try {
			const result = await api.createCollection({
				name: name.trim(),
				description: description.trim(),
				email: email.trim() || null,
				items: selection.refs()
			});
			oncreated({
				collection: result.collection,
				editKey: result.edit_key,
				failed: result.failed,
				emailedTo: result.emailed ? email.trim() : null
			});
			name = description = email = '';
			open = false;
		} catch (e) {
			error = errorMessage(e);
		} finally {
			busy = false;
		}
	}
</script>

<Dialog
	bind:open
	title="New collection"
	description="{plural(selection.count, 'asset')} will be added. You can change everything later."
>
	<form id="{id}-form" class="form" onsubmit={submit} novalidate>
		<div class="field">
			<label class="field-label" for="{id}-name">Name</label>
			<input
				id="{id}-name"
				data-autofocus
				class="input"
				bind:value={name}
				maxlength="120"
				required
				autocomplete="off"
				aria-invalid={nameInvalid}
				aria-describedby={nameInvalid ? `${id}-name-error` : undefined}
			/>
			{#if nameInvalid}
				<span id="{id}-name-error" class="field-error">Give your collection a name.</span>
			{/if}
		</div>
		<div class="field">
			<label class="field-label" for="{id}-description"
				>Description <span class="tertiary">(optional)</span></label
			>
			<textarea
				id="{id}-description"
				class="input"
				bind:value={description}
				maxlength="2000"
				rows="3"></textarea>
		</div>
		<div class="field">
			<label class="field-label" for="{id}-email"
				>Email <span class="tertiary">(optional)</span></label
			>
			<input
				id="{id}-email"
				class="input"
				type="email"
				bind:value={email}
				autocomplete="email"
				aria-describedby="{id}-email-hint"
			/>
			<span id="{id}-email-hint" class="field-hint">
				{#if app.config?.sign_in_available}
					We email you the edit link, and you can sign in on other devices. Never shown publicly.
				{:else}
					Stored with the collection so the team can reach you. Never shown publicly.
				{/if}
				<a href={resolve('legal/privacy')}>Privacy</a>
			</span>
		</div>
		{#if error}
			<p class="field-error" role="alert">{error}</p>
		{/if}
	</form>
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (open = false)}>Cancel</button>
		<button type="submit" form="{id}-form" class="btn btn-primary" disabled={busy}>
			{busy ? 'Creating…' : 'Create collection'}
		</button>
	{/snippet}
</Dialog>

<style>
	.form {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}
</style>
