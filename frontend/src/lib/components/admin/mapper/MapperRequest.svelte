<script lang="ts">
	import type { Document } from 'yaml';
	import { setStringMap, setValue, type SourceYaml, type YamlPath } from '#lib/mapper/config.js';
	import KeyValueEditor from './KeyValueEditor.svelte';

	let {
		data,
		onedit
	}: {
		data: SourceYaml;
		onedit: (change: (doc: Document) => void) => void;
	} = $props();

	const id = $props.id();
	const set = (path: YamlPath, value: unknown) => onedit((doc) => setValue(doc, path, value));

	const auth = $derived(data.adapter?.auth ?? {});
	const paging = $derived((data.search?.pagination ?? {}) as Record<string, unknown>);
	const style = $derived(String(paging.style ?? 'none'));
	const query = $derived(data.search?.query ?? {});
	const fixedParams = $derived(
		Object.entries(data.adapter?.default_query ?? {}).map(
			([k, v]) => [k, String(v ?? '')] as [string, string]
		)
	);

	const PRESETS: Record<string, Record<string, unknown>> = {
		offset_limit: { offset_param: 'offset', limit_param: 'limit', offset_base: 0 },
		start_rows: { offset_param: 'start', limit_param: 'rows', offset_base: 0 },
		page_size: { page_param: 'page', size_param: 'per_page', page_base: 1 }
	};

	function setStyle(next: string) {
		onedit((doc) => {
			const preset = next === 'start_rows' ? PRESETS.start_rows : PRESETS[next];
			setValue(
				doc,
				['search', 'pagination', 'style'],
				next === 'start_rows' ? 'offset_limit' : next
			);
			// A new style starts from its usual parameter names; adjust them after.
			for (const [key, value] of Object.entries(preset ?? {})) {
				setValue(doc, ['search', 'pagination', key], value);
			}
			if (paging.max_size === undefined && next !== 'none')
				setValue(doc, ['search', 'pagination', 'max_size'], 50);
		});
	}

	const num = (v: string) => (v.trim() === '' ? undefined : Number(v));
</script>

<div class="form">
	<label class="field wide">
		<span class="field-label">Base URL</span>
		<input
			class="input mono"
			type="url"
			placeholder="https://api.example.org"
			value={data.adapter?.base_url ?? ''}
			oninput={(e) => set(['adapter', 'base_url'], e.currentTarget.value.trim())}
		/>
	</label>
	<label class="field">
		<span class="field-label">Search path</span>
		<input
			class="input mono"
			placeholder="/search"
			value={data.search?.path ?? ''}
			oninput={(e) => set(['search', 'path'], e.currentTarget.value.trim())}
		/>
	</label>
	<label class="field">
		<span class="field-label">Search parameter</span>
		<input
			class="input mono"
			placeholder="q"
			value={query.pattern_param ?? ''}
			oninput={(e) => set(['search', 'query', 'pattern_param'], e.currentTarget.value.trim())}
		/>
		<span class="field-hint">Receives what visitors type.</span>
	</label>
	<label class="field wide">
		<span class="field-label">Query for an empty search</span>
		<input
			class="input mono"
			placeholder="*"
			value={query.pattern_when_empty ?? ''}
			oninput={(e) => set(['search', 'query', 'pattern_when_empty'], e.currentTarget.value)}
		/>
		<span class="field-hint"
			>The web app opens an archive with an empty search; it should still return results.</span
		>
	</label>

	<div class="field wide">
		<span class="field-label" id="{id}-fixed">Fixed parameters</span>
		<KeyValueEditor
			label="Fixed parameters"
			entries={fixedParams}
			onchange={(entries) =>
				onedit((doc) => setStringMap(doc, ['adapter', 'default_query'], entries))}
		/>
		<span class="field-hint"
			>Sent with every search, e.g. <span class="mono">format = json</span> or filters for open licences.</span
		>
	</div>

	<fieldset class="group wide">
		<legend class="field-label">API key</legend>
		<div class="row">
			<select
				class="input"
				aria-label="How the API key is sent"
				value={auth.type ?? 'none'}
				onchange={(e) => set(['adapter', 'auth', 'type'], e.currentTarget.value)}
			>
				<option value="none">No key</option>
				<option value="query_param">As a URL parameter</option>
				<option value="header">As a header</option>
			</select>
			{#if auth.type && auth.type !== 'none'}
				<input
					class="input mono"
					aria-label="Parameter or header name"
					placeholder={auth.type === 'header' ? 'X-Api-Key' : 'api_key'}
					value={auth.name ?? ''}
					oninput={(e) => set(['adapter', 'auth', 'name'], e.currentTarget.value.trim())}
				/>
				<input
					class="input mono"
					aria-label="Key"
					placeholder="$&#123;MY_API_KEY&#125;"
					value={auth.value ?? ''}
					oninput={(e) => set(['adapter', 'auth', 'value'], e.currentTarget.value.trim())}
				/>
			{/if}
		</div>
		{#if auth.type && auth.type !== 'none'}
			<span class="field-hint">
				Write the key as <span class="mono">$&#123;NAME&#125;</span> and put
				<span class="mono">NAME=…</span>
				into the server's <span class="mono">.env</span> — keys don't belong in this file.
			</span>
		{/if}
	</fieldset>

	<fieldset class="group wide">
		<legend class="field-label">Paging</legend>
		<div class="row">
			<select
				class="input"
				aria-label="Paging style"
				value={style === 'offset_limit' && paging.offset_param === 'start' ? 'start_rows' : style}
				onchange={(e) => setStyle(e.currentTarget.value)}
			>
				<option value="none">One page only</option>
				<option value="offset_limit">Offset and limit</option>
				<option value="start_rows">Start and rows (Solr)</option>
				<option value="page_size">Page number and size</option>
			</select>
			{#if style === 'offset_limit'}
				<input
					class="input mono"
					aria-label="Offset parameter"
					placeholder="offset"
					value={String(paging.offset_param ?? '')}
					oninput={(e) =>
						set(['search', 'pagination', 'offset_param'], e.currentTarget.value.trim())}
				/>
				<input
					class="input mono"
					aria-label="Limit parameter"
					placeholder="limit"
					value={String(paging.limit_param ?? '')}
					oninput={(e) =>
						set(['search', 'pagination', 'limit_param'], e.currentTarget.value.trim())}
				/>
				<select
					class="input"
					aria-label="First result is"
					value={String(paging.offset_base ?? 0)}
					onchange={(e) =>
						set(['search', 'pagination', 'offset_base'], Number(e.currentTarget.value))}
				>
					<option value="0">first = 0</option>
					<option value="1">first = 1</option>
				</select>
			{:else if style === 'page_size'}
				<input
					class="input mono"
					aria-label="Page parameter"
					placeholder="page"
					value={String(paging.page_param ?? '')}
					oninput={(e) => set(['search', 'pagination', 'page_param'], e.currentTarget.value.trim())}
				/>
				<input
					class="input mono"
					aria-label="Page size parameter"
					placeholder="per_page"
					value={String(paging.size_param ?? '')}
					oninput={(e) => set(['search', 'pagination', 'size_param'], e.currentTarget.value.trim())}
				/>
				<select
					class="input"
					aria-label="First page is"
					value={String(paging.page_base ?? 0)}
					onchange={(e) =>
						set(['search', 'pagination', 'page_base'], Number(e.currentTarget.value))}
				>
					<option value="0">first = 0</option>
					<option value="1">first = 1</option>
				</select>
			{/if}
			{#if style !== 'none'}
				<input
					class="input narrow"
					type="number"
					min="1"
					max="500"
					aria-label="Largest page the archive allows"
					title="Largest page the archive allows"
					value={String(paging.max_size ?? '')}
					oninput={(e) => set(['search', 'pagination', 'max_size'], num(e.currentTarget.value))}
				/>
			{/if}
		</div>
		<span class="field-hint">
			Check the archive's documentation: a parameter called “start” usually counts results, not
			pages, and some APIs count from 1.
		</span>
	</fieldset>
</div>

<style>
	.form {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 14px 16px;
	}

	.wide {
		grid-column: 1 / -1;
	}

	.form .input {
		min-height: 38px;
		padding: 7px 12px;
		font-size: 13.5px;
	}

	.group {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding: 0;
		border: 0;
	}

	.row {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	.row .input {
		flex: 1 1 140px;
	}

	.row select.input {
		flex: 0 1 220px;
	}

	.row .narrow {
		flex: 0 0 92px;
	}

	@media (max-width: 760px) {
		.form {
			grid-template-columns: minmax(0, 1fr);
		}
	}
</style>
