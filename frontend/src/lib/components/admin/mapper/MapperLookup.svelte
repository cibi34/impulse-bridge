<script lang="ts">
	import type { Document } from 'yaml';
	import { admin, type LookupRun } from '#lib/api/admin.js';
	import { errorMessage } from '#lib/api/index.js';
	import { setStringMap, setValue, type SourceYaml, type YamlPath } from '#lib/mapper/config.js';
	import { preview } from '#lib/mapper/json.js';
	import CopyField from '../../CopyField.svelte';
	import Icon from '../../Icon.svelte';
	import Switch from '../../Switch.svelte';
	import KeyValueEditor from './KeyValueEditor.svelte';

	let {
		data,
		text,
		ids,
		lossyIds = false,
		onedit
	}: {
		data: SourceYaml;
		/** The YAML as it is now (what the test runs). */
		text: string;
		/** assetIDs of the sample, to test with. */
		ids: string[];
		/** The assetID's slug transform changes the archive's ids (so they
		 * cannot be looked up exactly). */
		lossyIds?: boolean;
		onedit: (change: (doc: Document) => void) => void;
	} = $props();

	const set = (path: YamlPath, value: unknown) => onedit((doc) => setValue(doc, path, value));
	const detail = $derived(data.asset_detail ?? {});
	const enabled = $derived(!!detail.enabled);
	const params = $derived(
		Object.entries(detail.query ?? {}).map(([k, v]) => [k, String(v ?? '')] as [string, string])
	);
	const idTransform = $derived(data.mapping?.fields?.assetID?.transform ?? null);
	// The archive's own id: given back verbatim, decoded from base32, or — for
	// ids that slugify changed — only findable by a pattern in a Solr search.
	const exact = $derived(idTransform === 'base32' ? '{asset_id_from_base32}' : '{asset_id}');
	const placeholder = $derived(lossyIds ? '{asset_id_regex}' : exact);

	function presetSearch() {
		onedit((doc) => {
			setValue(doc, ['asset_detail', 'enabled'], true);
			setValue(doc, ['asset_detail', 'path'], data.search?.path ?? '');
			const base = Object.entries(data.adapter?.default_query ?? {}).map(
				([k, v]) => [k, String(v)] as [string, string]
			);
			const param = data.search?.query?.pattern_param || 'q';
			const filter = lossyIds ? `id:/${placeholder}/` : `id:"${placeholder}"`;
			setStringMap(doc, ['asset_detail', 'query'], [...base, [param, filter]]);
		});
	}

	function presetItem() {
		onedit((doc) => {
			setValue(doc, ['asset_detail', 'enabled'], true);
			const path = data.search?.path ?? '';
			const trailing = path.endsWith('/') ? '/' : '';
			setValue(doc, ['asset_detail', 'path'], `${path.replace(/\/$/, '')}/${exact}${trailing}`);
			setStringMap(doc, ['asset_detail', 'query'], []);
			setValue(doc, ['asset_detail', 'mapping', 'items_path'], '@');
		});
	}

	function setItemsPath(value: string) {
		const others = Object.keys(detail.mapping ?? {}).filter((k) => k !== 'items_path');
		// An empty `mapping:` block would mean "the whole response is the item"
		// on the server; without a value the search's list is meant.
		if (!value && others.length === 0) set(['asset_detail', 'mapping'], undefined);
		else set(['asset_detail', 'mapping', 'items_path'], value);
	}

	let testId = $state('');
	let running = $state(false);
	let result = $state<LookupRun | null>(null);
	let failure = $state<string | null>(null);
	const effectiveId = $derived(testId.trim() || ids[0] || '');

	async function test(event: SubmitEvent) {
		event.preventDefault();
		running = true;
		failure = null;
		try {
			result = await admin.testLookup(text, effectiveId);
		} catch (e) {
			result = null;
			failure = errorMessage(e);
		} finally {
			running = false;
		}
	}
</script>

<div class="lookup">
	<p class="footnote secondary">
		Adding an asset to a collection fetches it again by its ID. Without a lookup that only works for
		assets from recent searches — set one up so it always works.
	</p>

	<Switch
		checked={enabled}
		label="Single-asset lookup"
		visibleLabel="Look assets up by ID"
		onchange={(on) => set(['asset_detail', 'enabled'], on ? true : undefined)}
	/>

	{#if enabled}
		<div class="presets">
			<span class="caption tertiary">Start from</span>
			<button type="button" class="btn btn-sm" onclick={presetSearch}
				>The search, filtered by ID</button
			>
			<button type="button" class="btn btn-sm" onclick={presetItem}>An item endpoint (…/ID)</button>
		</div>

		<label class="field">
			<span class="field-label">Path</span>
			<input
				class="input mono"
				placeholder="/items/{placeholder}"
				value={detail.path ?? ''}
				oninput={(e) => set(['asset_detail', 'path'], e.currentTarget.value.trim())}
			/>
		</label>
		<div class="field">
			<span class="field-label">Parameters</span>
			<KeyValueEditor
				label="Lookup parameters"
				entries={params}
				onchange={(entries) =>
					onedit((doc) => setStringMap(doc, ['asset_detail', 'query'], entries))}
			/>
			<span class="field-hint">
				The complete query of the lookup (search parameters are not added; the API key is). Use
				<span class="mono">{placeholder}</span> where the ID goes{idTransform === 'base32'
					? ' — your IDs are base32, this gives back the archive’s original ID'
					: ''}.
			</span>
			{#if lossyIds}
				<p class="warning">
					Slugify changes this archive's IDs, so an exact endpoint cannot find them. Either look
					them up with a Solr-style search (<span class="mono"
						>field:/&#123;asset_id_regex&#125;/</span
					>), or switch the Asset ID to “Base32 (reversible id)” and use
					<span class="mono">&#123;asset_id_from_base32&#125;</span>.
				</p>
			{/if}
		</div>
		<label class="field">
			<span class="field-label">Where the result is in the response</span>
			<input
				class="input mono"
				placeholder={data.mapping?.items_path || '(the whole response)'}
				value={detail.mapping?.items_path ?? ''}
				oninput={(e) => setItemsPath(e.currentTarget.value.trim())}
			/>
			<span class="field-hint"
				>Leave empty to use the search's list; “@” means the response is the item itself.</span
			>
		</label>

		<form class="test" onsubmit={test}>
			<label class="visually-hidden" for="lookup-id">Asset ID to look up</label>
			<input
				id="lookup-id"
				class="input mono"
				placeholder={ids[0] ?? 'an asset ID from the sample'}
				bind:value={testId}
			/>
			<button type="submit" class="btn btn-primary btn-sm" disabled={running || !effectiveId}>
				{running ? 'Looking up…' : 'Test lookup'}
			</button>
		</form>
		{#if failure}<p class="field-error" role="alert">{failure}</p>{/if}
		{#if result}
			<div class="outcome" class:ok={result.found} role="status">
				<Icon name={result.found ? 'check' : 'alert'} size={16} />
				{#if result.found && result.asset}
					<span>
						Found <strong>{preview(result.asset.title ?? result.asset.assetID, 80)}</strong>
						{#if result.licence}· {result.licence.label}{/if}
					</span>
				{:else}
					<span>{result.error ?? 'Not found'}</span>
				{/if}
			</div>
			{#if result.upstream_url}<CopyField label="Lookup request" value={result.upstream_url} />{/if}
		{/if}
	{/if}
</div>

<style>
	.lookup {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.presets,
	.test {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	.test .input {
		flex: 1 1 260px;
		min-height: 36px;
		padding: 6px 12px;
		font-size: 13px;
	}

	.field .input {
		min-height: 38px;
		padding: 7px 12px;
		font-size: 13.5px;
	}

	.warning {
		margin-top: 6px;
		padding: 10px 12px;
		border-radius: 10px;
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 13px;
	}

	.outcome {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 10px 14px;
		border-radius: 10px;
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 13.5px;
	}

	.outcome.ok {
		background: var(--success-soft);
		color: var(--success-text);
	}

	.outcome strong {
		color: var(--text);
	}
</style>
