<script lang="ts">
	import { beforeNavigate, goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { onMount, tick } from 'svelte';
	import {
		admin,
		validationIssues,
		type SourceSummary,
		type Template,
		type ValidationIssue
	} from '#lib/api/admin.js';
	import { ApiError, errorMessage } from '#lib/api/index.js';
	import Mapper from '#lib/components/admin/mapper/Mapper.svelte';
	import TemplateDialog from '#lib/components/admin/TemplateDialog.svelte';
	import TestPanel from '#lib/components/admin/TestPanel.svelte';
	import YamlEditor from '#lib/components/admin/YamlEditor.svelte';
	import Dialog from '#lib/components/Dialog.svelte';
	import Icon from '#lib/components/Icon.svelte';
	import SegmentedControl from '#lib/components/SegmentedControl.svelte';
	import { parseConfig } from '#lib/mapper/config.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';

	let sources = $state<SourceSummary[]>([]);
	let templates = $state<Template[]>([]);
	let listError = $state<string | null>(null);

	// The open document: a file on disk, or a new one (filename null).
	let filename = $state<string | null>(null);
	let isNew = $state(false);
	let saved = $state('');
	let text = $state('');
	let loadedFlag = $state(false);
	let loadError = $state<string | null>(null);
	let issues = $state<ValidationIssue[]>([]);
	let validating = $state(false);
	let saving = $state(false);
	let opening = $state(false);

	let templateOpen = $state(false);
	let deleteOpen = $state(false);
	let editor: YamlEditor | undefined = $state();

	// REST sources open in the mapper; everything else (and broken YAML) in the editor.
	type View = 'mapper' | 'yaml';
	let view = $state<View>('yaml');
	function defaultView(yaml: string): View {
		return parseConfig(yaml).data.adapter?.kind === 'rest' ? 'mapper' : 'yaml';
	}

	async function showLine(line: number) {
		view = 'yaml';
		await tick();
		editor?.goToLine(line);
	}

	const dirty = $derived((isNew && text !== '') || text !== saved);
	const current = $derived(sources.find((s) => s.filename === filename) ?? null);
	const fileParam = $derived(page.url.searchParams.get('file'));

	onMount(() => {
		refreshList();
		admin
			.templates()
			.then((t) => (templates = t))
			.catch(() => {});
		const warn = (event: BeforeUnloadEvent) => {
			if (dirty) event.preventDefault();
		};
		window.addEventListener('beforeunload', warn);
		return () => window.removeEventListener('beforeunload', warn);
	});

	beforeNavigate(({ cancel, to }) => {
		const leavingDoc =
			to?.url.searchParams.get('file') !== filename || to?.url.pathname !== page.url.pathname;
		if (dirty && leavingDoc && !confirm('Discard your unsaved changes?')) cancel();
	});

	// Open the file named in the URL.
	$effect(() => {
		const name = fileParam;
		if (name && name !== filename) open(name);
		if (!name && !isNew) clearDoc();
	});

	async function refreshList() {
		try {
			sources = (await admin.sources()).sources;
			listError = null;
		} catch (e) {
			listError = errorMessage(e);
		}
	}

	function clearDoc() {
		filename = null;
		saved = text = '';
		issues = [];
		loadError = null;
	}

	async function open(name: string) {
		opening = true;
		try {
			const file = await admin.file(name);
			filename = file.filename;
			isNew = false;
			saved = text = file.yaml;
			issues = file.errors;
			loadedFlag = file.loaded;
			loadError = file.load_error;
			view = defaultView(file.yaml);
		} catch (e) {
			toasts.error(errorMessage(e));
			goto(resolve('admin/sources'), { replace: true });
		} finally {
			opening = false;
		}
	}

	function select(name: string) {
		goto(resolve(`admin/sources?file=${encodeURIComponent(name)}`));
	}

	function startNew(template: Template) {
		if (dirty && !confirm('Discard your unsaved changes?')) return;
		goto(resolve('admin/sources'), { replace: true }).then(() => {
			filename = null;
			isNew = true;
			saved = '';
			text = template.yaml;
			loadError = null;
			loadedFlag = false;
			view = defaultView(template.yaml);
		});
	}

	// Live validation, shortly after typing stops.
	let timer: ReturnType<typeof setTimeout>;
	let controller: AbortController | null = null;
	$effect(() => {
		const value = text;
		if (!value) return;
		clearTimeout(timer);
		timer = setTimeout(async () => {
			controller?.abort();
			controller = new AbortController();
			validating = true;
			try {
				issues = (await admin.validate(value, controller.signal)).errors;
			} catch {
				/* aborted or offline: keep the last result */
			} finally {
				validating = false;
			}
		}, 400);
		return () => clearTimeout(timer);
	});

	async function save() {
		saving = true;
		try {
			const file = isNew ? await admin.createFile(text) : await admin.saveFile(filename!, text);
			const created = isNew;
			isNew = false;
			filename = file.filename;
			saved = text = file.yaml;
			issues = file.errors;
			loadedFlag = file.loaded;
			loadError = file.load_error;
			await refreshList();
			if (created)
				goto(resolve(`admin/sources?file=${encodeURIComponent(file.filename)}`), { replace: true });
			if (file.load_error)
				toasts.error(`Saved, but the source could not start: ${file.load_error}`);
			else
				toasts.success(
					`Saved ${file.filename} — ${file.loaded ? 'the source is live' : 'not loaded'}`
				);
		} catch (e) {
			const found = validationIssues(e);
			if (found) {
				issues = found;
				toasts.error('Fix the problems shown in the editor first.');
			} else {
				toasts.error(e instanceof ApiError && e.status === 409 ? e.message : errorMessage(e));
			}
		} finally {
			saving = false;
		}
	}

	async function destroy() {
		if (!filename) return;
		try {
			await admin.deleteFile(filename);
			toasts.success(`Deleted ${filename}`);
			deleteOpen = false;
			saved = text;
			clearDoc();
			await refreshList();
			goto(resolve('admin/sources'), { replace: true });
		} catch (e) {
			toasts.error(errorMessage(e));
		}
	}

	async function reload() {
		try {
			const result = await admin.reload();
			sources = result.sources;
			const broken = result.sources.filter((s) => s.error).length;
			toasts.show(
				`Reloaded from disk: ${result.loaded_count} live` +
					(broken ? `, ${broken} with problems` : ''),
				{ kind: broken ? 'error' : 'success' }
			);
			if (filename && !dirty) open(filename);
		} catch (e) {
			toasts.error(errorMessage(e));
		}
	}

	const problems = $derived(issues.map((i) => ({ line: i.line, message: i.msg })));
	const status = $derived(
		isNew
			? { label: 'New — not saved', kind: 'pill-warning' }
			: loadError
				? { label: 'Not running', kind: 'pill-warning' }
				: loadedFlag
					? { label: 'Live', kind: 'pill-success' }
					: { label: 'Not loaded', kind: '' }
	);
</script>

<svelte:head>
	<title>Sources — Admin — IMPULSE Curator</title>
</svelte:head>

<div class="layout">
	<aside class="list-pane" aria-labelledby="sources-title">
		<div class="list-head">
			<h1 id="sources-title" class="title">Sources</h1>
			<div class="row">
				<button type="button" class="btn btn-primary btn-sm" onclick={() => (templateOpen = true)}>
					<Icon name="plus" size={16} /> New
				</button>
				<button type="button" class="btn btn-sm" onclick={reload}>
					<Icon name="refresh" size={16} /> Reload from disk
				</button>
			</div>
		</div>
		{#if listError}
			<p class="field-error" role="alert">{listError}</p>
		{/if}
		<ul class="files">
			{#each sources as source (source.filename)}
				<li>
					<button
						type="button"
						class="file"
						aria-current={source.filename === filename ? 'true' : undefined}
						onclick={() => select(source.filename)}
					>
						<span
							class="dot"
							class:ok={source.loaded && !source.error}
							class:bad={!!source.error}
							aria-hidden="true"
						></span>
						<span class="file-text">
							<span class="file-name">{source.name ?? source.id ?? source.filename}</span>
							<span class="caption tertiary">
								<span class="mono">{source.filename}</span>{source.kind ? ` · ${source.kind}` : ''}
							</span>
							{#if source.error}
								<span class="caption error-line">{source.error}</span>
							{/if}
						</span>
						<span class="visually-hidden">
							{source.error ? '(has problems)' : source.loaded ? '(live)' : '(not loaded)'}
						</span>
					</button>
				</li>
			{/each}
		</ul>
	</aside>

	<section class="doc" aria-label="Editor">
		{#if filename || isNew}
			<div class="doc-head">
				<div class="doc-title">
					<h2 class="title">{current?.name ?? (isNew ? 'New source' : filename)}</h2>
					<div class="row">
						<span class="pill {status.kind}">{status.label}</span>
						{#if filename}<span class="mono caption tertiary">{filename}</span>{/if}
						{#if dirty}<span class="pill pill-warning">Unsaved changes</span>{/if}
					</div>
				</div>
				<div class="row">
					{#if dirty && !isNew}
						<button type="button" class="btn btn-plain btn-sm" onclick={() => (text = saved)}
							>Revert</button
						>
					{/if}
					{#if filename}
						<button
							type="button"
							class="btn btn-plain btn-sm danger"
							onclick={() => (deleteOpen = true)}
						>
							<Icon name="trash" size={16} /> Delete
						</button>
					{/if}
					<button
						type="button"
						class="btn btn-primary btn-sm"
						disabled={saving || (!dirty && !isNew)}
						onclick={save}
					>
						{saving ? 'Saving…' : isNew ? 'Create source' : 'Save'}
					</button>
				</div>
			</div>

			{#if loadError}
				<p class="notice" role="status">
					<Icon name="alert" size={16} /><span><strong>Not running:</strong> {loadError}</span>
				</p>
			{/if}

			<div class="view-switch">
				<SegmentedControl
					legend="View"
					options={[
						{ value: 'mapper', label: 'Mapper' },
						{ value: 'yaml', label: 'YAML' }
					]}
					bind:value={view}
				/>
				<span class="caption tertiary">
					{view === 'mapper'
						? 'Fetch a sample, then map its values to IMPULSE fields. Changes go into the YAML.'
						: 'The whole configuration. Comments and formatting are kept.'}
				</span>
			</div>

			{#if view === 'mapper'}
				{#key filename ?? 'new'}
					<Mapper bind:text />
				{/key}
			{:else}
				<div class="editor-wrap" aria-busy={opening}>
					<YamlEditor
						bind:this={editor}
						bind:value={text}
						{problems}
						label="Source configuration (YAML)"
					/>
				</div>
			{/if}

			<div class="validation" role="status" aria-live="polite">
				{#if validating}
					<span class="footnote tertiary">Checking…</span>
				{:else if issues.length === 0}
					<span class="footnote ok"><Icon name="check" size={16} /> Valid configuration</span>
				{:else}
					<ul>
						{#each issues as issue, i (i)}
							<li>
								<button
									type="button"
									class="issue"
									disabled={!issue.line}
									onclick={() => issue.line && showLine(issue.line)}
								>
									<span class="mono">{issue.line ? `Line ${issue.line}` : 'File'}</span>
									<span class="loc mono">{issue.loc.join('.')}</span>
									<span>{issue.msg}</span>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			{#if view === 'yaml'}<TestPanel yaml={text} />{/if}
		{:else}
			<div class="empty">
				<Icon name="compass" size={32} />
				<h2 class="headline">Pick a source, or create one</h2>
				<p class="secondary">
					Each source is one YAML file in <span class="mono">configs/sources/</span> describing how to
					search and map an archive. Changes go live when you save.
				</p>
				<button type="button" class="btn btn-primary" onclick={() => (templateOpen = true)}>
					<Icon name="plus" size={16} /> New source
				</button>
			</div>
		{/if}
	</section>
</div>

<TemplateDialog bind:open={templateOpen} {templates} onpick={startNew} />

<Dialog bind:open={deleteOpen} title="Delete this source?" size="sm">
	<p class="secondary">
		<span class="mono">{filename}</span> is removed from disk and the archive disappears from the web
		app. Collections keep the assets they already contain.
	</p>
	{#snippet footer()}
		<button type="button" class="btn" onclick={() => (deleteOpen = false)}>Cancel</button>
		<button type="button" class="btn btn-danger" onclick={destroy}>Delete</button>
	{/snippet}
</Dialog>

<style>
	.layout {
		display: grid;
		grid-template-columns: 320px minmax(0, 1fr);
		gap: 28px;
		align-items: start;
	}

	.list-pane {
		position: sticky;
		top: 88px;
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.list-head {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	.files {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.file {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		width: 100%;
		padding: 10px 12px;
		border: 1px solid transparent;
		border-radius: 12px;
		background: transparent;
		color: var(--text);
		text-align: left;
	}

	.file:hover {
		background: var(--surface);
	}

	.file[aria-current='true'] {
		background: var(--surface);
		border-color: var(--separator-strong);
	}

	.dot {
		flex-shrink: 0;
		width: 8px;
		height: 8px;
		margin-top: 6px;
		border-radius: 50%;
		background: var(--text-3);
	}

	.dot.ok {
		background: var(--success);
	}

	.dot.bad {
		background: var(--danger-text);
	}

	.file-text {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.file-name {
		font-weight: 600;
		font-size: 14px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.error-line {
		color: var(--danger-text);
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.doc {
		display: flex;
		flex-direction: column;
		gap: 16px;
		min-width: 0;
	}

	.doc-head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
	}

	.doc-title {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.editor-wrap {
		height: min(62vh, 640px);
	}

	.view-switch {
		display: flex;
		align-items: center;
		gap: 14px;
		flex-wrap: wrap;
	}

	.validation ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.issue {
		display: flex;
		gap: 12px;
		width: 100%;
		padding: 8px 12px;
		border: 0;
		border-radius: 10px;
		background: var(--danger-soft);
		color: var(--danger-text);
		font-size: 13px;
		text-align: left;
	}

	.issue:disabled {
		cursor: default;
	}

	.issue .mono {
		flex-shrink: 0;
	}

	.loc {
		color: var(--text-2);
	}

	.ok {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--success-text);
	}

	.danger {
		color: var(--danger-text);
	}

	.notice {
		display: flex;
		gap: 10px;
		align-items: flex-start;
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
		margin: 72px auto;
		text-align: center;
		color: var(--text-3);
	}

	.empty h2 {
		color: var(--text);
	}

	@media (max-width: 1000px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
		}
		.list-pane {
			position: static;
		}
	}
</style>
