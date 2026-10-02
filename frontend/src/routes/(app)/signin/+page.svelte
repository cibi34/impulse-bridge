<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { api, errorMessage } from '#lib/api/index.js';
	import Icon from '#lib/components/Icon.svelte';
	import { app } from '#lib/stores/app.svelte.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';

	let phase = $state<'form' | 'verifying' | 'failed'>('form');
	let failure = $state('');
	let email = $state('');
	let sent = $state<string | null>(null);
	let sending = $state(false);

	onMount(async () => {
		// Sign-in links carry a one-time token in the fragment (#token=…).
		const token = new URLSearchParams(location.hash.slice(1)).get('token');
		if (!token) return;
		history.replaceState(history.state, '', location.pathname);
		phase = 'verifying';
		try {
			const { email: signedIn } = await api.verifySignIn(token);
			app.email = signedIn;
			toasts.success(`Signed in as ${signedIn}`);
			goto(resolve('my'), { replace: true });
		} catch (e) {
			failure = errorMessage(e);
			phase = 'failed';
		}
	});

	async function request(event: SubmitEvent) {
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
	<title>Sign in — IMPULSE Curator</title>
</svelte:head>

<div class="page">
	<div class="panel card">
		<Icon name="user" size={32} />
		{#if phase === 'verifying'}
			<h1 class="title">Signing you in…</h1>
			<p class="secondary" role="status">One moment.</p>
		{:else}
			<h1 class="title">Sign in</h1>
			{#if phase === 'failed'}
				<p class="field-error" role="alert">{failure} Request a new link below.</p>
			{/if}
			<p class="secondary">
				No password needed. Enter the email address you created your collections with, and we'll
				send you a link that signs you in on this device.
			</p>
			{#if app.config && !app.config.sign_in_available}
				<p class="notice" role="status">Sign-in by email is not available on this server yet.</p>
			{:else if sent}
				<p class="success" role="status"><Icon name="check" size={16} /> {sent}</p>
			{:else}
				<form class="form" onsubmit={request}>
					<div class="field">
						<label class="field-label" for="email">Email address</label>
						<input
							id="email"
							class="input"
							type="email"
							required
							autocomplete="email"
							bind:value={email}
						/>
					</div>
					<button type="submit" class="btn btn-primary" disabled={sending}>
						{sending ? 'Sending…' : 'Send sign-in link'}
					</button>
				</form>
			{/if}
			<p class="caption tertiary">
				The link works once and expires after 15 minutes. See <a href={resolve('legal/privacy')}
					>Privacy</a
				>.
			</p>
		{/if}
	</div>
</div>

<style>
	.page {
		display: grid;
		place-items: center;
		min-height: calc(100dvh - 60px);
		padding: 32px var(--gutter);
	}

	.card {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 16px;
		width: min(100%, 460px);
		padding: 32px;
	}

	.card > :global(svg) {
		color: var(--accent-text);
	}

	.form {
		display: flex;
		flex-direction: column;
		gap: 14px;
		width: 100%;
	}

	.success {
		display: flex;
		gap: 8px;
		color: var(--success-text);
	}

	.notice {
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
	}
</style>
