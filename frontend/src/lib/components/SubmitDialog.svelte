<script lang="ts">
	import { api, errorMessage, type ImpulseCollection } from '#lib/api/index.js';
	import { plural } from '#lib/format.js';
	import { app } from '#lib/stores/app.svelte.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';
	import { buildSubmission, shortMailto, type Submission } from '#lib/submission.js';
	import Dialog from './Dialog.svelte';
	import Icon from './Icon.svelte';

	let {
		open = $bindable(false),
		collections,
		onsubmitted
	}: {
		open?: boolean;
		/** Collections to submit, each with the key that may mark it submitted. */
		collections: { id: string; key: string | null }[];
		onsubmitted?: (ids: string[]) => void;
	} = $props();

	const id = $props.id();
	let entries = $state<ImpulseCollection[]>([]);
	let loading = $state(false);
	let error = $state<string | null>(null);
	let note = $state('');
	let copied = $state(false);

	const to = $derived(app.config?.submission_email ?? null);
	const submission = $derived<Submission | null>(
		to && entries.length > 0 ? buildSubmission(to, entries, note) : null
	);

	$effect(() => {
		if (!open) return;
		const ids = collections.map((c) => c.id);
		loading = true;
		error = null;
		copied = false;
		Promise.all(ids.map((cid) => api.impulseCollection(cid)))
			.then((result) => (entries = result))
			.catch((e) => (error = errorMessage(e)))
			.finally(() => (loading = false));
	});

	async function markSubmitted() {
		const done: string[] = [];
		await Promise.all(
			collections.map(async (c) => {
				try {
					await api.markSubmitted(c.id, c.key);
					done.push(c.id);
				} catch {
					/* not editable from here: the email still goes out */
				}
			})
		);
		onsubmitted?.(done);
	}

	async function copyText(text: string): Promise<boolean> {
		try {
			await navigator.clipboard.writeText(text);
			return true;
		} catch {
			return false;
		}
	}

	async function copy() {
		if (!submission) return;
		copied = await copyText(
			`To: ${submission.to}\nSubject: ${submission.subject}\n\n${submission.body}`
		);
		if (copied) {
			toasts.success('Email text copied');
			await markSubmitted();
		} else {
			document.getElementById(`${id}-body`)?.focus();
			toasts.error('Copying is blocked in this browser — select the text and copy it by hand.');
		}
	}

	async function openMail(event: MouseEvent) {
		if (!submission) return;
		if (!submission.mailto) {
			// Too long for a mailto: link — the full text goes to the clipboard.
			event.preventDefault();
			const ok = await copyText(submission.body);
			window.location.href = shortMailto(submission);
			toasts.show(
				ok
					? 'The text is in your clipboard — paste it into the email.'
					: 'Copy the text below into the email.'
			);
		}
		await markSubmitted();
	}
</script>

<Dialog
	bind:open
	title="Submit to IMPULSE"
	description={collections.length > 1
		? `${plural(collections.length, 'collection')} in one email to the IMPULSE team.`
		: 'An email to the IMPULSE team, who add the collection to the platform.'}
	size="lg"
>
	{#if loading}
		<p class="secondary" role="status">Preparing the email…</p>
	{:else if error}
		<p class="field-error" role="alert">{error}</p>
	{:else if !to}
		<p class="notice" role="status">
			<Icon name="info" size={16} />
			The submission address has not been set up yet. Copy the collection details below and send them
			to your IMPULSE contact.
		</p>
		<pre class="body">{JSON.stringify(entries.length === 1 ? entries[0] : entries, null, 2)}</pre>
	{:else if submission}
		<dl class="meta">
			<div>
				<dt>To</dt>
				<dd>{submission.to}</dd>
			</div>
			<div>
				<dt>Subject</dt>
				<dd>{submission.subject}</dd>
			</div>
		</dl>
		<div class="field">
			<label class="field-label" for="{id}-note"
				>Message <span class="tertiary">(optional)</span></label
			>
			<textarea
				id="{id}-note"
				class="input"
				rows="2"
				bind:value={note}
				placeholder="Anything the team should know, e.g. which scene it is for"></textarea>
		</div>
		<div class="field">
			<label class="field-label" for="{id}-body">Email text</label>
			<textarea id="{id}-body" class="input body" rows="12" readonly value={submission.body}
			></textarea>
		</div>
	{/if}
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (open = false)}>Close</button>
		{#if submission}
			<button type="button" class="btn" onclick={copy}>
				<Icon name={copied ? 'check' : 'copy'} size={16} />
				{copied ? 'Copied' : 'Copy text'}
			</button>
			<a
				class="btn btn-primary"
				href={submission.mailto ?? shortMailto(submission)}
				onclick={openMail}
			>
				<Icon name="mail" size={16} /> Open in mail app
			</a>
		{/if}
	{/snippet}
</Dialog>

<style>
	.meta {
		margin: 0 0 18px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.meta div {
		display: grid;
		grid-template-columns: 80px minmax(0, 1fr);
		gap: 12px;
	}

	dt {
		color: var(--text-3);
	}

	dd {
		margin: 0;
		overflow-wrap: anywhere;
	}

	.field + .field {
		margin-top: 16px;
	}

	.body {
		font-family: var(--font-mono);
		font-size: 12px;
		line-height: 1.5;
		white-space: pre;
		overflow: auto;
	}

	pre.body {
		margin: 16px 0 0;
		padding: 14px;
		border-radius: var(--radius);
		background: var(--surface-sunken);
	}

	.notice {
		display: flex;
		gap: 10px;
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 14px;
	}
</style>
