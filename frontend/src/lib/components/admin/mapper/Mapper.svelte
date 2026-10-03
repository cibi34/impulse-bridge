<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import type { Document } from 'yaml';
	import { admin, type TestRun } from '#lib/api/admin.js';
	import { errorMessage, type Licence } from '#lib/api/index.js';
	import { edit, parseConfig, setField, setValue } from '#lib/mapper/config.js';
	import {
		evaluateField,
		extractItems,
		mapItem,
		slugify,
		type FieldMapping
	} from '#lib/mapper/evaluate.js';
	import { FIELDS, GROUP_LABELS, type FieldDef, type FieldGroup } from '#lib/mapper/fields.js';
	import { findLists, preview } from '#lib/mapper/json.js';
	import { AUTO_SCORE, suggest, type Suggestion } from '#lib/mapper/suggest.js';
	import { plural } from '#lib/format.js';
	import { toasts } from '#lib/stores/toasts.svelte.js';
	import CopyField from '../../CopyField.svelte';
	import Icon from '../../Icon.svelte';
	import JsonTree from './JsonTree.svelte';
	import MapperField from './MapperField.svelte';
	import MapperLookup from './MapperLookup.svelte';
	import MapperPreview from './MapperPreview.svelte';
	import MapperRequest from './MapperRequest.svelte';

	let { text = $bindable('') }: { text?: string } = $props();

	const parsed = $derived(parseConfig(text));
	const data = $derived(parsed.data);
	const fields = $derived(data.mapping?.fields ?? {});
	const itemsPath = $derived(data.mapping?.items_path ?? '');

	function onedit(change: (doc: Document) => void) {
		text = edit(text, change);
	}

	// ---- 2. Sample ----
	let query = $state('');
	let count = $state(20);
	let loading = $state(false);
	let run = $state<TestRun | null>(null);
	let fetchError = $state<string | null>(null);
	let fetchedFor = $state('');
	const requestKey = $derived(JSON.stringify([data.adapter, data.search]));
	const stale = $derived(!!run && fetchedFor !== requestKey);
	const raw = $derived(run?.raw_upstream ?? null);
	const lists = $derived(raw ? findLists(raw) : []);

	async function fetchSample(event?: SubmitEvent) {
		event?.preventDefault();
		loading = true;
		fetchError = null;
		const key = requestKey;
		try {
			run = await admin.test(text, query.trim(), count);
			fetchedFor = key;
			index = 0;
			if (!itemsPath && lists.length > 0 && !Array.isArray(raw)) setItemsPath(lists[0].path);
			// Point at the first field that still needs a value (the sample can
			// show that a mapped field gives nothing).
			if (items.length && (!active || !needsValue(active))) active = firstOpenField();
		} catch (e) {
			fetchError = errorMessage(e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		if (data.adapter?.kind === 'rest' && data.adapter.base_url) fetchSample();
	});

	function setItemsPath(path: string) {
		onedit((doc) => setValue(doc, ['mapping', 'items_path'], path));
	}

	// ---- 3. Results and fields ----
	const extracted = $derived.by((): { items: unknown[]; error: string | null } => {
		if (raw === null) return { items: [], error: null };
		try {
			return { items: extractItems(raw, itemsPath), error: null };
		} catch (e) {
			return { items: [], error: e instanceof Error ? e.message : String(e) };
		}
	});
	const items = $derived(extracted.items);
	let index = $state(0);
	const item = $derived(items[Math.min(index, Math.max(0, items.length - 1))]);

	const suggestions = $derived.by((): Record<string, Suggestion[]> => {
		const list = items;
		return list.length ? Object.fromEntries(FIELDS.map((f) => [f.name, suggest(f, list)])) : {};
	});

	const results = $derived(items.map((it) => mapItem(it, data.mapping ?? {}, data.filter ?? {})));

	// Licence readings come from the server, so they match app/licensing.py.
	let licences = $state<Record<string, Licence>>({});
	$effect(() => {
		const known = untrack(() => licences);
		const wanted = [...new Set(results.map((r) => String(r.asset.rights ?? '')))].filter(
			(v) => !(v in known)
		);
		if (wanted.length === 0) return;
		const timer = setTimeout(async () => {
			try {
				const read = await admin.licences(wanted);
				licences = { ...licences, ...Object.fromEntries(wanted.map((v, i) => [v, read[i]])) };
			} catch {
				/* the preview just shows no licence */
			}
		}, 250);
		return () => clearTimeout(timer);
	});
	const currentLicence = $derived(
		results[index] ? (licences[String(results[index].asset.rights ?? '')] ?? null) : null
	);

	const label = (name: string) => FIELDS.find((f) => f.name === name)?.label ?? name;
	const mappedField = (fm: FieldMapping | null | undefined) =>
		!!fm && (!!fm.expr || (fm.literal !== null && fm.literal !== undefined));
	const filled = (v: unknown) =>
		v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0);

	/** Still to do: unmapped, or mapped to something that gives nothing usable
	 * for any result of the sample (a template placeholder, a wrong path, a
	 * licence nobody can read). */
	function needsValue(name: string): boolean {
		if (!mappedField(fields[name])) return true;
		if (results.length === 0) return false;
		if (results.every((r) => !filled(r.asset[name]))) return true;
		if (name === 'rights') {
			const read = results.map((r) => licences[String(r.asset.rights ?? '')]);
			return read.every((l) => l && l.code === 'other');
		}
		return false;
	}

	/** Paths used by fields, for the badges in the explorer. */
	const usage = $derived.by(() => {
		const out: Record<string, string[]> = {};
		for (const [name, fm] of Object.entries(fields)) {
			const expr = fm?.expr?.trim();
			if (!expr) continue;
			const inner =
				/^to_string\((.+)\)$/.exec(expr)?.[1] ??
				/^join\('[^']*', (.+?)\[\]\.to_string\(@\)\)$/.exec(expr)?.[1] ??
				expr;
			for (const path of new Set([expr, inner])) (out[path] ??= []).push(label(name));
		}
		return out;
	});

	// ---- Assigning values ----
	let active = $state<string | null>(null);
	let openDepth = $state(2);
	let treeVersion = $state(0);

	function expandTree(depth: number) {
		openDepth = depth;
		treeVersion += 1;
	}

	/** The first field (outside "More") that still needs a value. */
	function firstOpenField(): string | null {
		return FIELDS.find((f) => f.group !== 'more' && needsValue(f.name))?.name ?? null;
	}
	let picked = $state<{ path: string; value: unknown } | null>(null);
	let pickTarget = $state('');
	let announcement = $state('');

	function mappingFor(def: FieldDef, path: string, value: unknown): FieldMapping {
		const previous = fields[def.name];
		let expr = path;
		if (Array.isArray(value)) {
			expr =
				def.kind === 'list' || def.kind === 'genre'
					? `join(', ', ${path}[].to_string(@))`
					: `${path}[0]`;
			value = value[0];
		} else if (def.kind === 'id' && typeof value === 'number') {
			expr = `to_string(${path})`;
		}
		const fm: FieldMapping = { expr };
		if (
			def.kind === 'id' &&
			(previous?.transform === 'slugify' || previous?.transform === 'base32')
		) {
			fm.transform = previous.transform;
		} else if (typeof value === 'string' && /<[a-z][^>]*>/i.test(value)) {
			fm.transform = 'strip_html';
		} else if (def.kind === 'title' && typeof value === 'string' && /^(file|image):/i.test(value)) {
			fm.transform = 'file_title';
		}
		return fm;
	}

	function assign(name: string, path: string, value: unknown) {
		const def = FIELDS.find((f) => f.name === name);
		if (!def) return;
		onedit((doc) => setField(doc, name, mappingFor(def, path, value)));
		announcement = `${def.label} now uses ${path}`;
		picked = null;
		// Move on to the next field that still needs a value.
		const order = FIELDS.filter((f) => f.group !== 'more');
		const start = order.findIndex((f) => f.name === name);
		const next = [...order.slice(start + 1), ...order.slice(0, start)].find(
			(f) => f.name !== name && needsValue(f.name)
		);
		active = next?.name ?? null;
	}

	function pick(path: string, value: unknown) {
		if (active) assign(active, path, value);
		else {
			picked = { path, value };
			pickTarget = '';
		}
	}

	function change(name: string, fm: FieldMapping | null) {
		onedit((doc) => setField(doc, name, fm));
	}

	function autoMap() {
		const fills: [string, Suggestion][] = [];
		for (const def of FIELDS) {
			if (!needsValue(def.name)) continue;
			// One path per field: the media file may double as the preview, nothing else.
			const taken = new Set(
				[
					...Object.entries(fields)
						.filter(([name]) => !needsValue(name))
						.map(([, fm]) => fm?.expr),
					...fills.map(([, s]) => s.expr)
				].filter(Boolean)
			);
			const best = suggestions[def.name]?.find(
				(s) =>
					s.expr !== fields[def.name]?.expr && (def.name === 'previewURI' || !taken.has(s.expr))
			);
			if (best && best.score >= AUTO_SCORE) fills.push([def.name, best]);
		}
		if (fills.length === 0) {
			toasts.show('No confident suggestions left — pick the remaining values by hand.');
			return;
		}
		onedit((doc) => {
			for (const [name, s] of fills) setField(doc, name, { expr: s.expr, transform: s.transform });
		});
		toasts.success(
			`Filled ${plural(fills.length, 'field')}: ${fills.map(([n]) => label(n)).join(', ')}`
		);
	}

	const required = FIELDS.filter((f) => f.group === 'required');
	const requiredDone = $derived(required.filter((f) => !needsValue(f.name)).length);
	const groups: FieldGroup[] = ['required', 'recommended', 'more'];
	const moreInUse = $derived(FIELDS.some((f) => f.group === 'more' && mappedField(fields[f.name])));

	const sampleIds = $derived(
		results.map((r) => r.asset.assetID).filter((id): id is string => typeof id === 'string')
	);
	const lookupOn = $derived(!!data.asset_detail?.enabled);
	/** Does the assetID's slug transform change the archive's ids? */
	const lossyIds = $derived.by(() => {
		const fm = fields.assetID;
		if (fm?.transform !== 'slugify' || !fm.expr) return false;
		return items.some((it) => {
			try {
				const id = evaluateField(it, { ...fm, transform: undefined });
				return typeof id === 'string' && slugify(id) !== id;
			} catch {
				return false;
			}
		});
	});
	let requestOpen = $state(false);
	let lookupOpen = $state(false);
	onMount(() => {
		requestOpen = !data.adapter?.base_url;
	});
</script>

{#if parsed.error}
	<p class="notice" role="alert">
		<Icon name="alert" size={16} />
		<span
			>The YAML has a syntax error ({parsed.error}). Fix it in the YAML view; the mapper picks up
			from there.</span
		>
	</p>
{:else if data.adapter?.kind !== 'rest'}
	<div class="notice info">
		<Icon name="info" size={16} />
		<span>
			{data.adapter?.kind === 'custom'
				? 'IIIF manifests map themselves: the adapter reads titles, images and the licence from the manifest.'
				: 'Local sources describe their assets in a manifest file.'}
			There is nothing to map — edit this source in the YAML view.
		</span>
	</div>
{:else}
	<div class="mapper">
		<details class="step panel" bind:open={requestOpen}>
			<summary>
				<span class="num">1</span>
				<span class="step-title">Request</span>
				<span class="step-meta mono"
					>{data.adapter?.base_url ?? 'not set'}{data.search?.path ?? ''}</span
				>
			</summary>
			<div class="body"><MapperRequest {data} {onedit} /></div>
		</details>

		<section class="step panel" aria-labelledby="mapper-sample">
			<div class="step-head">
				<span class="num">2</span>
				<h3 id="mapper-sample" class="step-title">Sample</h3>
				{#if run && !stale}<span class="pill pill-success">{plural(items.length, 'result')}</span
					>{/if}
				{#if stale}<span class="pill pill-warning">Request changed — fetch again</span>{/if}
			</div>
			<form class="sample-form" onsubmit={fetchSample}>
				<label class="visually-hidden" for="mapper-query">Search for</label>
				<input
					id="mapper-query"
					class="input"
					placeholder="Search (empty: {data.search?.query?.pattern_when_empty ||
						'the default query'})"
					bind:value={query}
				/>
				<label class="visually-hidden" for="mapper-count">Number of results</label>
				<select id="mapper-count" class="input count" bind:value={count}>
					<option value={10}>10 results</option>
					<option value={20}>20 results</option>
					<option value={50}>50 results</option>
				</select>
				<button
					type="submit"
					class="btn btn-primary btn-sm"
					disabled={loading || !data.adapter?.base_url}
				>
					<Icon name="refresh" size={16} />
					{loading ? 'Fetching…' : run ? 'Fetch again' : 'Fetch sample'}
				</button>
			</form>
			{#if fetchError}<p class="field-error" role="alert">{fetchError}</p>{/if}
			{#if run}
				{#each run.errors as error (error.msg)}
					<p class="notice" role="alert"><Icon name="alert" size={16} /><span>{error.msg}</span></p>
				{/each}
				{#if run.upstream_url}<CopyField label="Request sent" value={run.upstream_url} />{/if}
				{#if raw !== null}
					<div class="lists">
						<span class="field-label">Where are the results?</span>
						<div class="chips">
							{#each lists as list (list.path)}
								<button
									type="button"
									class="chip"
									aria-pressed={list.path === itemsPath}
									onclick={() => setItemsPath(list.path)}
								>
									<span class="mono">{list.label}</span>
									<span class="tag">{list.count}</span>
								</button>
							{/each}
						</div>
						<label class="items-path">
							<span class="visually-hidden">Path to the list of results</span>
							<input
								class="input mono"
								placeholder="(the response itself)"
								value={itemsPath}
								oninput={(e) => setItemsPath(e.currentTarget.value.trim())}
							/>
							<span class="caption {extracted.error ? 'error' : 'tertiary'}">
								{extracted.error ?? `${plural(items.length, 'result')} at this path`}
							</span>
						</label>
					</div>
				{/if}
			{/if}
		</section>

		<section class="step panel fields-step" aria-labelledby="mapper-fields">
			<div class="step-head">
				<span class="num">3</span>
				<h3 id="mapper-fields" class="step-title">Fields</h3>
				<span class="pill {requiredDone === required.length ? 'pill-success' : 'pill-warning'}">
					{requiredDone}/{required.length} needed
				</span>
				<button
					type="button"
					class="btn btn-sm auto"
					disabled={items.length === 0}
					onclick={autoMap}
					title="Fill empty fields with confident suggestions"
				>
					<Icon name="check" size={16} /> Auto-map
				</button>
			</div>

			<div class="workspace">
				<div class="explorer">
					<div class="explorer-head">
						<span class="field-label">Result</span>
						<div class="expand">
							<button type="button" class="link-button" onclick={() => expandTree(99)}
								>Expand all</button
							>
							<button type="button" class="link-button" onclick={() => expandTree(1)}
								>Collapse</button
							>
						</div>
						<div class="pager">
							<button
								type="button"
								class="btn btn-plain btn-icon btn-sm"
								disabled={index <= 0}
								onclick={() => (index -= 1)}
							>
								<Icon name="chevronLeft" size={16} label="Previous result" />
							</button>
							<span class="mono caption" aria-live="polite"
								>{items.length ? `${index + 1} / ${items.length}` : '–'}</span
							>
							<button
								type="button"
								class="btn btn-plain btn-icon btn-sm"
								disabled={index >= items.length - 1}
								onclick={() => (index += 1)}
							>
								<Icon name="chevronRight" size={16} label="Next result" />
							</button>
						</div>
					</div>
					<p class="hint" class:on={!!active}>
						{#if !items.length}
							Fetch a sample to see a result here.
						{:else if active}
							Click a value to use it for <strong>{label(active)}</strong>.
						{:else}
							Select a field on the right, or click a value to choose a field for it.
						{/if}
					</p>
					{#if picked}
						<div class="picked">
							<span class="mono">{picked.path}</span>
							<span class="tertiary">“{preview(picked.value, 40)}”</span>
							<select class="input" aria-label="Use this value for" bind:value={pickTarget}>
								<option value="">Use for…</option>
								{#each FIELDS as f (f.name)}<option value={f.name}>{f.label}</option>{/each}
							</select>
							<button
								type="button"
								class="btn btn-primary btn-sm"
								disabled={!pickTarget}
								onclick={() => picked && assign(pickTarget, picked.path, picked.value)}>Use</button
							>
						</div>
					{/if}
					<div class="tree-scroll">
						{#if item !== undefined}
							{#key treeVersion}
								<JsonTree
									value={item}
									{openDepth}
									{usage}
									pickVerb={active ? `Use for ${label(active)}` : 'Choose a field for'}
									onpick={pick}
								/>
							{/key}
						{/if}
					</div>
				</div>

				<div class="field-groups">
					{#each groups as group (group)}
						{@const defs = FIELDS.filter((f) => f.group === group)}
						{#if group === 'more'}
							<details class="more" open={moreInUse}>
								<summary class="group-title">{GROUP_LABELS[group]}</summary>
								<ul class="field-list">
									{#each defs as def (def.name)}
										<MapperField
											{def}
											fm={fields[def.name]}
											{items}
											{index}
											suggestions={suggestions[def.name] ?? []}
											active={active === def.name}
											onactivate={() => (active = active === def.name ? null : def.name)}
											onchange={(fm) => change(def.name, fm)}
										/>
									{/each}
								</ul>
							</details>
						{:else}
							<h4 class="group-title">{GROUP_LABELS[group]}</h4>
							<ul class="field-list">
								{#each defs as def (def.name)}
									<MapperField
										{def}
										fm={fields[def.name]}
										{items}
										{index}
										suggestions={suggestions[def.name] ?? []}
										active={active === def.name}
										licence={def.name === 'rights' ? currentLicence : null}
										onactivate={() => (active = active === def.name ? null : def.name)}
										onchange={(fm) => change(def.name, fm)}
									/>
								{/each}
							</ul>
						{/if}
					{/each}
				</div>
			</div>
			<p class="visually-hidden" role="status">{announcement}</p>
		</section>

		<section class="step panel" aria-labelledby="mapper-preview">
			<div class="step-head">
				<span class="num">4</span>
				<h3 id="mapper-preview" class="step-title">Preview</h3>
				<span class="caption tertiary">What the web app will show, from this sample</span>
			</div>
			{#if results.length}
				<MapperPreview
					{results}
					{licences}
					filter={data.filter ?? {}}
					onfilter={(f) =>
						onedit((doc) => {
							setValue(
								doc,
								['filter', 'drop_if_missing'],
								f.drop_if_missing.length ? f.drop_if_missing : undefined
							);
							setValue(
								doc,
								['filter', 'allowed_content_types'],
								f.allowed_content_types.length ? f.allowed_content_types : undefined
							);
						})}
					onshow={(i) => {
						index = i;
						document
							.querySelector('.explorer')
							?.scrollIntoView({ behavior: 'smooth', block: 'start' });
					}}
				/>
			{:else}
				<p class="footnote tertiary">The preview appears once the sample has results.</p>
			{/if}
		</section>

		<details class="step panel" bind:open={lookupOpen}>
			<summary>
				<span class="num">5</span>
				<span class="step-title">Single-asset lookup</span>
				<span class="pill {lookupOn ? 'pill-success' : 'pill-warning'}"
					>{lookupOn ? 'Set up' : 'Not set up'}</span
				>
			</summary>
			<div class="body"><MapperLookup {data} {text} ids={sampleIds} {lossyIds} {onedit} /></div>
		</details>
	</div>
{/if}

<style>
	.mapper {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.step {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding: 18px 20px;
	}

	details.step:not([open]) {
		gap: 0;
	}

	summary,
	.step-head {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	summary {
		cursor: pointer;
		list-style: none;
	}

	summary::-webkit-details-marker {
		display: none;
	}

	summary::after {
		content: '';
		width: 8px;
		height: 8px;
		margin-left: auto;
		border-right: 2px solid var(--text-3);
		border-bottom: 2px solid var(--text-3);
		transform: rotate(45deg);
		transition: transform 0.15s ease;
	}

	details[open] > summary::after {
		transform: rotate(-135deg);
	}

	.num {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		background: var(--accent-soft);
		color: var(--accent-text);
		font-size: 13px;
		font-weight: 700;
	}

	.step-title {
		font-size: 16px;
		font-weight: 600;
	}

	.step-meta {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--text-3);
		font-size: 12.5px;
	}

	.body {
		padding-top: 14px;
	}

	.sample-form {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	.sample-form .input {
		flex: 1 1 260px;
		min-height: 38px;
		padding: 7px 12px;
		font-size: 14px;
	}

	.sample-form .count {
		flex: 0 0 140px;
	}

	.lists {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 5px 6px 5px 12px;
		border: 1px solid var(--separator-strong);
		border-radius: var(--radius-pill);
		background: transparent;
		color: var(--text);
		font-size: 13px;
	}

	.chip[aria-pressed='true'] {
		border-color: var(--action);
		background: var(--accent-soft);
	}

	.tag {
		padding: 1px 8px;
		border-radius: var(--radius-pill);
		background: var(--control);
		color: var(--text-2);
		font-size: 12px;
	}

	.items-path {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.items-path .input {
		flex: 1 1 280px;
		min-height: 36px;
		padding: 6px 12px;
		font-size: 13px;
	}

	.error {
		color: var(--danger-text);
	}

	.auto {
		margin-left: auto;
	}

	.workspace {
		display: grid;
		grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
		gap: 20px;
		align-items: start;
	}

	.explorer {
		position: sticky;
		top: 76px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px;
		border-radius: var(--radius);
		background: var(--bg);
		border: 1px solid var(--separator);
	}

	.explorer-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.expand {
		display: flex;
		gap: 12px;
		margin-left: auto;
		margin-right: 12px;
	}

	.link-button {
		padding: 0;
		border: 0;
		background: none;
		color: var(--link);
		font-size: 12.5px;
	}

	.pager {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.hint {
		padding: 8px 10px;
		border-radius: 9px;
		background: var(--control);
		color: var(--text-2);
		font-size: 12.5px;
	}

	.hint.on {
		background: var(--accent-soft);
		color: var(--accent-text);
	}

	.hint strong {
		color: var(--text);
	}

	.picked {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		font-size: 12.5px;
	}

	.picked .input {
		flex: 1 1 140px;
		min-height: 34px;
		padding: 4px 8px;
		font-size: 13px;
	}

	.tree-scroll {
		max-height: min(68vh, 720px);
		overflow: auto;
		padding-right: 4px;
	}

	.field-groups {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.group-title {
		margin: 6px 0 2px;
		color: var(--text-2);
		font-size: 13px;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	details.more > summary {
		cursor: pointer;
	}

	.field-list {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
		padding: 0;
		list-style: none;
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

	.notice.info {
		background: var(--surface);
		color: var(--text-2);
		border: 1px solid var(--separator);
	}

	@media (max-width: 1100px) {
		.workspace {
			grid-template-columns: minmax(0, 1fr);
		}
		.explorer {
			position: static;
		}
	}
</style>
