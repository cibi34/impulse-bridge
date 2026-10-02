<script lang="ts">
	import { onMount } from 'svelte';
	import { admin, type AdminSettings, type SettingsChanges } from '#lib/api/admin.js';
	import { errorMessage } from '#lib/api/index.js';
	import Icon from '#lib/components/Icon.svelte';
	import SegmentedControl from '#lib/components/SegmentedControl.svelte';
	import { toasts } from '#lib/stores/toasts.svelte.js';

	type Security = AdminSettings['smtp_security'];

	let current = $state<AdminSettings | null>(null);
	let loadError = $state<string | null>(null);

	let submissionEmail = $state('');
	let host = $state('');
	let port = $state(587);
	let security = $state<Security>('starttls');
	let username = $state('');
	let password = $state('');
	let removePassword = $state(false);
	let mailFrom = $state('');
	let saving = $state(false);

	let testTo = $state('');
	let testing = $state(false);

	onMount(async () => {
		try {
			fill(await admin.settings());
		} catch (e) {
			loadError = errorMessage(e);
		}
	});

	function fill(s: AdminSettings) {
		current = s;
		submissionEmail = s.submission_email;
		host = s.smtp_host;
		port = s.smtp_port;
		security = s.smtp_security;
		username = s.smtp_username;
		mailFrom = s.mail_from;
		password = '';
		removePassword = false;
	}

	const changes = $derived.by((): SettingsChanges => {
		if (!current) return {};
		const c: SettingsChanges = {};
		if (submissionEmail.trim() !== current.submission_email)
			c.submission_email = submissionEmail.trim();
		if (host.trim() !== current.smtp_host) c.smtp_host = host.trim();
		if (Number(port) !== current.smtp_port) c.smtp_port = Number(port);
		if (security !== current.smtp_security) c.smtp_security = security;
		if (username.trim() !== current.smtp_username) c.smtp_username = username.trim();
		if (mailFrom.trim() !== current.mail_from) c.mail_from = mailFrom.trim();
		if (password) c.smtp_password = password;
		else if (removePassword) c.smtp_password = '';
		return c;
	});
	const dirty = $derived(Object.keys(changes).length > 0);

	async function save(event: SubmitEvent) {
		event.preventDefault();
		saving = true;
		try {
			fill(await admin.saveSettings(changes));
			toasts.success('Settings saved');
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			saving = false;
		}
	}

	async function sendTest(event: SubmitEvent) {
		event.preventDefault();
		testing = true;
		try {
			const { sent_to } = await admin.testEmail(testTo.trim());
			toasts.success(
				current?.mail_log_only
					? `Test email written to the server log (to ${sent_to})`
					: `Test email sent to ${sent_to}`
			);
		} catch (e) {
			toasts.error(errorMessage(e));
		} finally {
			testing = false;
		}
	}

	const mailStatus = $derived(
		!current
			? null
			: current.mail_log_only
				? { label: 'Log only (development)', kind: 'pill-warning' }
				: current.mail_configured
					? { label: 'Email is set up', kind: 'pill-success' }
					: { label: 'Email is not set up', kind: '' }
	);
</script>

<svelte:head>
	<title>Settings — Admin — IMPULSE Curator</title>
</svelte:head>

<header class="head">
	<h1 class="large-title">Settings</h1>
	<p class="secondary">Where submissions go, and how the app sends sign-in and edit-link emails.</p>
</header>

{#if loadError}
	<p class="notice" role="alert">{loadError}</p>
{:else if current}
	<div class="columns">
		<form class="stack" onsubmit={save}>
			<section class="panel section" aria-labelledby="submission-title">
				<h2 id="submission-title" class="headline">Submissions</h2>
				<div class="field">
					<label class="field-label" for="submission">Submission address</label>
					<input
						id="submission"
						class="input"
						type="email"
						bind:value={submissionEmail}
						autocomplete="off"
						placeholder="collections@example.org"
						aria-describedby="submission-hint"
					/>
					<span id="submission-hint" class="field-hint">
						“Submit to IMPULSE” opens an email to this address. Without one, visitors are asked to
						copy the collection details and send them to their IMPULSE contact.
					</span>
				</div>
			</section>

			<section class="panel section" aria-labelledby="smtp-title">
				<div class="section-head">
					<h2 id="smtp-title" class="headline">Email (SMTP)</h2>
					{#if mailStatus}<span class="pill {mailStatus.kind}">{mailStatus.label}</span>{/if}
				</div>
				<p class="footnote secondary">
					Used for sign-in links and “Email me the edit link”. Without it, sign-in by email is
					hidden.
				</p>
				<div class="grid server">
					<div class="field">
						<label class="field-label" for="host">Server</label>
						<input
							id="host"
							class="input"
							bind:value={host}
							autocomplete="off"
							placeholder="smtp.example.org"
						/>
					</div>
					<div class="field">
						<label class="field-label" for="port">Port</label>
						<input id="port" class="input" type="number" min="1" max="65535" bind:value={port} />
					</div>
				</div>
				<div class="field">
					<span class="field-label" aria-hidden="true">Encryption</span>
					<SegmentedControl
						legend="Encryption"
						options={[
							{ value: 'starttls', label: 'STARTTLS' },
							{ value: 'ssl', label: 'SSL/TLS' },
							{ value: 'none', label: 'None' }
						]}
						bind:value={security}
					/>
				</div>
				<div class="grid">
					<div class="field">
						<label class="field-label" for="username">Username</label>
						<input id="username" class="input" bind:value={username} autocomplete="off" />
					</div>
					<div class="field">
						<label class="field-label" for="password">Password</label>
						<input
							id="password"
							class="input"
							type="password"
							bind:value={password}
							autocomplete="new-password"
							disabled={current.smtp_password_from_env}
							placeholder={current.smtp_password_set ? 'Saved — type to replace' : ''}
							aria-describedby="password-hint"
						/>
						<span id="password-hint" class="field-hint">
							{#if current.smtp_password_from_env}
								Set through the environment (BRIDGE_SMTP_PASSWORD).
							{:else if current.smtp_password_set}
								Never shown again.
								<label class="inline-check">
									<input type="checkbox" bind:checked={removePassword} disabled={!!password} /> Remove
									it
								</label>
							{:else}
								Stored on the server, never shown again.
							{/if}
						</span>
					</div>
				</div>
				<div class="field">
					<label class="field-label" for="from">Sender</label>
					<input
						id="from"
						class="input"
						bind:value={mailFrom}
						autocomplete="off"
						placeholder="IMPULSE Curator <curator@example.org>"
					/>
				</div>
			</section>

			<div class="actions">
				<button
					type="button"
					class="btn btn-plain"
					disabled={!dirty}
					onclick={() => current && fill(current)}>Revert</button
				>
				<button type="submit" class="btn btn-primary" disabled={!dirty || saving}>
					{saving ? 'Saving…' : 'Save settings'}
				</button>
			</div>
		</form>

		<div class="stack">
			<section class="panel section" aria-labelledby="test-title">
				<h2 id="test-title" class="headline">Send a test email</h2>
				<p class="footnote secondary">Uses the saved settings — save your changes first.</p>
				<form class="row" onsubmit={sendTest}>
					<label class="visually-hidden" for="test-to">Recipient</label>
					<input
						id="test-to"
						class="input"
						type="email"
						required
						bind:value={testTo}
						placeholder="you@example.org"
						autocomplete="email"
					/>
					<button type="submit" class="btn" disabled={testing || dirty}>
						<Icon name="send" size={16} />
						{testing ? 'Sending…' : 'Send'}
					</button>
				</form>
			</section>

			<section class="panel section" aria-labelledby="server-title">
				<h2 id="server-title" class="headline">Server</h2>
				<p class="footnote secondary">From the server's environment (.env); change them there.</p>
				<dl class="facts">
					<div>
						<dt>Public address</dt>
						<dd class="mono">{current.server.public_base_url}</dd>
					</div>
					<div>
						<dt>owner_id of collections</dt>
						<dd class="mono">{current.server.collection_owner_id}</dd>
					</div>
					<div>
						<dt>Default organization</dt>
						<dd>{current.server.default_organization}</dd>
					</div>
					<div>
						<dt>Assets per collection</dt>
						<dd>up to {current.server.max_assets_per_collection}</dd>
					</div>
					<div>
						<dt>Source configs</dt>
						<dd class="mono">{current.server.config_dir}</dd>
					</div>
					<div>
						<dt>Database</dt>
						<dd class="mono">{current.server.database}</dd>
					</div>
				</dl>
			</section>
		</div>
	</div>
{:else}
	<p class="secondary" role="status">Loading…</p>
{/if}

<style>
	.head {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin-bottom: 24px;
	}

	.columns {
		display: grid;
		grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
		gap: 24px;
		align-items: start;
	}

	.stack {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.section {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 22px;
	}

	.section-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
	}

	.grid.server {
		grid-template-columns: minmax(0, 1fr) 120px;
	}

	.inline-check {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		margin-left: 8px;
		color: var(--text-2);
	}

	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 10px;
	}

	.row {
		display: flex;
		gap: 8px;
	}

	.row .input {
		flex: 1;
	}

	.facts {
		margin: 0;
		display: flex;
		flex-direction: column;
	}

	.facts div {
		display: grid;
		grid-template-columns: 170px minmax(0, 1fr);
		gap: 12px;
		padding: 8px 0;
		border-bottom: 1px solid var(--separator);
		font-size: 14px;
	}

	.facts div:last-child {
		border-bottom: 0;
	}

	dt {
		color: var(--text-3);
	}

	dd {
		margin: 0;
		overflow-wrap: anywhere;
	}

	.notice {
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--warning-soft);
		color: var(--warning-text);
	}

	@media (max-width: 1000px) {
		.columns {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
