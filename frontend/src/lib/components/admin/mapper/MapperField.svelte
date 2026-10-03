<script lang="ts">
	import type { Licence } from '#lib/api/index.js';
	import { evaluateField, syntaxError, type FieldMapping } from '#lib/mapper/evaluate.js';
	import { TRANSFORMS, type FieldDef } from '#lib/mapper/fields.js';
	import { isImageUrl, isModelUrl, isUrl, preview } from '#lib/mapper/json.js';
	import type { Suggestion } from '#lib/mapper/suggest.js';
	import Icon from '../../Icon.svelte';
	import KeyValueEditor from './KeyValueEditor.svelte';

	let {
		def,
		fm,
		items,
		index,
		suggestions,
		active,
		licence = null,
		onactivate,
		onchange
	}: {
		def: FieldDef;
		fm: FieldMapping | null | undefined;
		items: unknown[];
		/** The result shown in the explorer. */
		index: number;
		suggestions: Suggestion[];
		active: boolean;
		/** For `rights`: how the current result's value is read. */
		licence?: Licence | null;
		onactivate: () => void;
		onchange: (fm: FieldMapping | null) => void;
	} = $props();

	const id = $props.id();
	const MIME_CHOICES = ['image/jpeg', 'image/png', 'model/gltf-binary'];

	const mapped = $derived(!!fm && (!!fm.expr || (fm.literal !== null && fm.literal !== undefined)));
	// An editor opened for an empty field: nothing is written until there is a value.
	let editing = $state(false);
	let localMode = $state<'path' | 'fixed'>('path');
	const showEditor = $derived(mapped || editing);
	const fixed = $derived(
		mapped ? fm!.literal !== null && fm!.literal !== undefined : localMode === 'fixed'
	);
	const exprError = $derived(fm?.expr ? syntaxError(fm.expr) : null);

	function valueFor(item: unknown): { value: unknown; error: string | null } {
		if (!fm || !mapped || exprError) return { value: null, error: exprError };
		try {
			return { value: evaluateField(item, fm), error: null };
		} catch (e) {
			return { value: null, error: e instanceof Error ? e.message : String(e) };
		}
	}

	const filled = (v: unknown) =>
		v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && !v.length);
	const current = $derived(
		items.length ? valueFor(items[index]) : { value: null, error: exprError }
	);
	const values = $derived(mapped && !exprError ? items.map((item) => valueFor(item).value) : []);
	const coverage = $derived(values.filter(filled).length);

	const warnings = $derived.by((): string[] => {
		if (!mapped || exprError || items.length === 0) return [];
		const out: string[] = [];
		const present = values.filter(filled);
		const v = current.value;
		switch (def.kind) {
			case 'id': {
				if (present.some((x) => typeof x !== 'string'))
					out.push('IDs must be text: wrap the path in to_string( … ).');
				if (new Set(present.map((x) => JSON.stringify(x))).size < present.length)
					out.push('Not unique: several results have the same ID.');
				if (present.some((x) => typeof x === 'string' && !/^[a-z0-9][a-z0-9-]*$/.test(x)))
					out.push(
						'Contains characters other than a–z, 0–9 and “-”: the collection derives its own ids, but a lookup needs the exact value — consider the slug or base32 option.'
					);
				break;
			}
			case 'media':
				if (filled(v) && !isUrl(v)) out.push('Not a URL.');
				else if (filled(v) && !isImageUrl(v) && !isModelUrl(v))
					out.push(
						'Does not look like a direct image or model file — check that it is not a web page.'
					);
				break;
			case 'preview':
			case 'page':
				if (filled(v) && !isUrl(v)) out.push('Not a URL.');
				break;
			case 'mime':
				if (filled(v) && !/^(image|model|video|audio)\/[\w.+-]+$/.test(String(v)))
					out.push('Not a MIME type — translate it with a value map, or use a fixed value.');
				break;
			case 'title':
			case 'text':
			case 'person':
				if (typeof v === 'string' && /<[a-z][^>]*>/i.test(v))
					out.push('Contains HTML — use “Remove HTML”.');
				break;
		}
		if (Array.isArray(v) || (v !== null && typeof v === 'object'))
			out.push('This is a list or object, not text — pick a value inside it.');
		return out;
	});

	/** Mapped, but no result of the sample has a value: almost certainly the wrong path. */
	const dead = $derived(mapped && !exprError && items.length > 0 && coverage === 0);
	const unreadLicence = $derived(def.kind === 'licence' && licence?.code === 'other');

	const status = $derived(
		exprError || current.error || dead
			? 'error'
			: !mapped
				? def.group === 'required'
					? 'missing'
					: 'empty'
				: unreadLicence || (items.length && coverage < items.length)
					? 'partial'
					: 'ok'
	);

	let showOptions = $state(false);
	const hasOptions = $derived(!!fm && (!!fm.transform || fm.default != null || !!fm.map));

	function set(changes: Partial<FieldMapping>) {
		onchange({ ...(fm ?? {}), ...changes });
	}

	function setMode(mode: 'path' | 'fixed') {
		localMode = mode;
		editing = true;
		onchange(mode === 'fixed' && def.literal ? { literal: def.literal } : null);
	}

	function open(mode: 'path' | 'fixed') {
		localMode = mode;
		editing = true;
		onactivate();
	}

	function clear() {
		editing = false;
		onchange(null);
	}
</script>

<li class="field" class:active data-status={status}>
	<div class="head">
		<button
			type="button"
			class="select"
			aria-pressed={active}
			aria-describedby="{id}-help"
			onclick={onactivate}
		>
			<span class="state" aria-hidden="true">
				{#if status === 'ok'}<Icon
						name="check"
						size={14}
						strokeWidth={2.6}
					/>{:else if status === 'error' || status === 'missing'}<Icon
						name="alert"
						size={14}
					/>{:else if status === 'partial'}<span class="half"></span>{/if}
			</span>
			<span class="label">{def.label}</span>
			<span class="name mono">{def.name}</span>
			<span class="visually-hidden">
				{status === 'missing' ? '(needed, not mapped)' : status === 'error' ? '(has an error)' : ''}
				{active ? '(selected — click a value in the result to use it)' : ''}
			</span>
		</button>
		{#if mapped && items.length}
			<span class="coverage" class:full={coverage === items.length}>{coverage}/{items.length}</span>
		{/if}
		{#if showEditor}
			<button type="button" class="btn btn-plain btn-icon btn-sm" onclick={clear}>
				<Icon name="close" size={16} label="Clear {def.label}" />
			</button>
		{/if}
	</div>
	<p id="{id}-help" class="help">{def.help}</p>

	{#if showEditor}
		<div class="editor">
			<div class="mode" role="group" aria-label="{def.label}: source of the value">
				<button type="button" aria-pressed={!fixed} onclick={() => fixed && setMode('path')}
					>Path</button
				>
				<button type="button" aria-pressed={fixed} onclick={() => !fixed && setMode('fixed')}
					>Fixed</button
				>
			</div>
			{#if fixed}
				<input
					class="input"
					aria-label="{def.label}: fixed value"
					value={String(fm?.literal ?? '')}
					oninput={(e) => set({ literal: e.currentTarget.value, expr: undefined })}
				/>
			{:else}
				<input
					class="input mono"
					aria-label="{def.label}: JMESPath expression"
					aria-invalid={!!exprError}
					spellcheck="false"
					autocomplete="off"
					value={fm?.expr ?? ''}
					oninput={(e) => set({ expr: e.currentTarget.value, literal: undefined })}
				/>
			{/if}
		</div>
		<div class="result" aria-live="polite">
			{#if exprError}
				<span class="error">Expression error: {exprError}</span>
			{:else if current.error}
				<span class="error">{current.error}</span>
			{:else if items.length}
				<span class="arrow" aria-hidden="true">→</span>
				{#if filled(current.value)}
					<span class="value">{preview(current.value, 160)}</span>
				{:else}
					<span class="empty">empty for this result</span>
				{/if}
			{/if}
		</div>
		{#if dead}
			<p class="error">No result in the sample has a value here — pick another path.</p>
		{/if}
		{#if licence && def.kind === 'licence' && !exprError}
			<p class="licence" class:bad={!licence.allowed}>
				<Icon name={licence.allowed ? 'check' : 'alert'} size={14} />
				{licence.code === 'other'
					? `Not recognised as an open licence (“${licence.label}”) — such assets stay hidden.`
					: `Read as ${licence.label}${licence.allowed ? ' — accepted' : ' — not accepted by IMPULSE'}`}
			</p>
		{/if}
		{#each warnings as warning (warning)}<p class="warning">{warning}</p>{/each}

		<button
			type="button"
			class="options-toggle"
			aria-expanded={showOptions || hasOptions}
			onclick={() => (showOptions = !showOptions)}
		>
			Options{hasOptions ? ' (in use)' : ''}
		</button>
		{#if showOptions || hasOptions}
			<div class="options">
				<label class="option">
					<span class="field-label">Transform</span>
					<select
						class="input"
						value={fm?.transform ?? ''}
						onchange={(e) => set({ transform: e.currentTarget.value || undefined })}
					>
						<option value="">None</option>
						{#each TRANSFORMS as t (t.value)}<option value={t.value}>{t.label}</option>{/each}
					</select>
				</label>
				{#if !fixed}
					<label class="option">
						<span class="field-label">Default when empty</span>
						<input
							class="input"
							value={fm?.default == null ? '' : String(fm.default)}
							oninput={(e) => set({ default: e.currentTarget.value || undefined })}
						/>
					</label>
					<div class="option wide">
						<span class="field-label">Value map — translate values, e.g. IMAGE → image/jpeg</span>
						<KeyValueEditor
							label="{def.label}: value map"
							keyPlaceholder="archive value"
							valuePlaceholder="becomes"
							entries={Object.entries(fm?.map ?? {}).map(([k, v]) => [k, String(v)])}
							onchange={(entries) =>
								set({ map: entries.length ? Object.fromEntries(entries) : undefined })}
						/>
					</div>
				{/if}
			</div>
		{/if}
	{:else}
		<div class="actions">
			<button type="button" class="btn btn-sm" onclick={() => open('path')}>Enter a path</button>
			{#if def.literal}
				<button
					type="button"
					class="btn btn-sm btn-plain"
					onclick={() => onchange({ literal: def.literal })}>Fixed “{def.literal}”</button
				>
			{/if}
			{#if def.kind === 'mime'}
				{#each MIME_CHOICES.filter((m) => m !== def.literal) as mime (mime)}
					<button
						type="button"
						class="btn btn-sm btn-plain"
						onclick={() => onchange({ literal: mime })}>Fixed “{mime}”</button
					>
				{/each}
			{/if}
		</div>
	{/if}

	{#if suggestions.length && (!mapped || active || dead || unreadLicence)}
		<div class="suggestions">
			<span class="caption tertiary">{mapped ? 'Other suggestions' : 'Suggestions'}</span>
			{#each suggestions.filter((s) => s.expr !== fm?.expr) as s (s.expr)}
				<button
					type="button"
					class="suggestion"
					onclick={() => onchange({ expr: s.expr, transform: s.transform })}
				>
					<span class="mono">{s.expr}</span>
					<span class="sample">{preview(s.sample, 60)}</span>
					{#if s.transform}<span class="tag"
							>{TRANSFORMS.find((t) => t.value === s.transform)?.label}</span
						>{/if}
					<span class="tag">{Math.round(s.coverage * 100)}%</span>
				</button>
			{/each}
		</div>
	{/if}
</li>

<style>
	.field {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 14px 16px;
		border: 1px solid var(--separator);
		border-radius: var(--radius);
		background: var(--surface);
		transition:
			border-color 0.15s ease,
			box-shadow 0.15s ease;
	}

	.field.active {
		border-color: var(--action);
		box-shadow: 0 0 0 3px var(--accent-soft);
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.select {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 10px;
		min-width: 0;
		padding: 2px 0;
		border: 0;
		background: transparent;
		color: var(--text);
		text-align: left;
	}

	.state {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--control);
		color: var(--text-3);
	}

	[data-status='ok'] .state {
		background: var(--success-soft);
		color: var(--success-text);
	}

	[data-status='missing'] .state,
	[data-status='error'] .state {
		background: var(--danger-soft);
		color: var(--danger-text);
	}

	[data-status='partial'] .state {
		background: var(--warning-soft);
		color: var(--warning-text);
	}

	.half {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: linear-gradient(90deg, currentColor 50%, transparent 50%);
		border: 1.5px solid currentColor;
	}

	.label {
		font-weight: 600;
		font-size: 14.5px;
	}

	.name {
		color: var(--text-3);
		font-size: 12px;
	}

	.coverage {
		padding: 2px 8px;
		border-radius: var(--radius-pill);
		background: var(--warning-soft);
		color: var(--warning-text);
		font-size: 12px;
		font-variant-numeric: tabular-nums;
	}

	.coverage.full {
		background: var(--success-soft);
		color: var(--success-text);
	}

	.help {
		margin-left: 32px;
		color: var(--text-3);
		font-size: 12.5px;
	}

	.editor,
	.result,
	.actions,
	.licence,
	.warning,
	.options-toggle,
	.options,
	.suggestions {
		margin-left: 32px;
	}

	.editor {
		display: flex;
		gap: 8px;
	}

	.editor .input {
		flex: 1;
		min-height: 38px;
		padding: 7px 12px;
		font-size: 13px;
	}

	.mode {
		display: inline-flex;
		flex-shrink: 0;
		padding: 2px;
		border-radius: 9px;
		background: var(--control);
	}

	.mode button {
		padding: 0 10px;
		border: 0;
		border-radius: 7px;
		background: transparent;
		color: var(--text-2);
		font-size: 12.5px;
		font-weight: 500;
	}

	.mode button[aria-pressed='true'] {
		background: var(--raised);
		color: var(--text);
		box-shadow: var(--shadow-sm);
	}

	.result {
		display: flex;
		gap: 8px;
		min-width: 0;
		font-size: 13px;
	}

	.arrow {
		color: var(--text-3);
	}

	.value {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.empty {
		color: var(--text-3);
		font-style: italic;
	}

	.error,
	.warning {
		color: var(--danger-text);
		font-size: 12.5px;
	}

	.warning {
		color: var(--warning-text);
	}

	.licence {
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--success-text);
		font-size: 12.5px;
	}

	.licence.bad {
		color: var(--warning-text);
	}

	.options-toggle {
		align-self: flex-start;
		padding: 0;
		border: 0;
		background: none;
		color: var(--link);
		font-size: 12.5px;
	}

	.options {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px 12px;
		padding: 12px;
		border-radius: 10px;
		background: var(--surface-sunken);
	}

	.option {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.option .input {
		min-height: 36px;
		padding: 6px 10px;
		font-size: 13px;
	}

	.option.wide {
		grid-column: 1 / -1;
	}

	.actions {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.suggestions {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.suggestion {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		padding: 6px 10px;
		border: 1px dashed var(--separator-strong);
		border-radius: 9px;
		background: transparent;
		color: var(--text);
		font-size: 12.5px;
		text-align: left;
	}

	.suggestion:hover {
		border-style: solid;
		background: var(--accent-soft);
	}

	.suggestion .mono {
		flex-shrink: 0;
		max-width: 50%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--link);
	}

	.sample {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--text-2);
	}

	.tag {
		flex-shrink: 0;
		padding: 1px 6px;
		border-radius: var(--radius-pill);
		background: var(--control);
		color: var(--text-2);
		font-size: 11px;
	}
</style>
