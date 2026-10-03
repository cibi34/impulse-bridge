<script lang="ts">
	import { admin, type TestRun } from '#lib/api/admin.js';
	import { errorMessage } from '#lib/api/index.js';
	import { kindLabel, plural } from '#lib/format.js';
	import AssetThumb from '../AssetThumb.svelte';
	import CopyField from '../CopyField.svelte';
	import Icon from '../Icon.svelte';

	let { yaml }: { yaml: string } = $props();

	const id = $props.id();
	let query = $state('');
	let count = $state(6);
	let running = $state(false);
	let result = $state<TestRun | null>(null);
	let failure = $state<string | null>(null);

	async function run(event: SubmitEvent) {
		event.preventDefault();
		running = true;
		failure = null;
		try {
			result = await admin.test(yaml, query.trim(), Math.min(50, Math.max(1, count || 6)));
		} catch (e) {
			result = null;
			failure = errorMessage(e);
		} finally {
			running = false;
		}
	}

	const errors = $derived(result?.errors ?? []);
</script>

<section class="panel test" aria-labelledby="{id}-title">
	<div class="head">
		<div>
			<h2 id="{id}-title" class="headline">Test run</h2>
			<p class="footnote secondary">
				Runs the editor's current text against the real archive. Nothing is saved.
			</p>
		</div>
		<form class="controls" onsubmit={run}>
			<label class="visually-hidden" for="{id}-query">Search pattern</label>
			<input
				id="{id}-query"
				class="input"
				placeholder="Search pattern (empty: default)"
				bind:value={query}
			/>
			<label class="visually-hidden" for="{id}-count">Number of results</label>
			<input
				id="{id}-count"
				class="input count"
				type="number"
				min="1"
				max="50"
				bind:value={count}
			/>
			<button type="submit" class="btn btn-primary btn-sm" disabled={running}>
				{running ? 'Running…' : 'Run test'}
			</button>
		</form>
	</div>

	<div class="body" aria-live="polite" aria-busy={running}>
		{#if failure}
			<p class="field-error" role="alert">{failure}</p>
		{:else if result}
			{#if errors.length > 0}
				<ul class="errors" role="alert">
					{#each errors as e, i (i)}
						<li>
							<Icon name="alert" size={16} />
							<span><span class="mono">{e.loc.join('.') || 'config'}</span> — {e.msg}</span>
						</li>
					{/each}
				</ul>
			{/if}
			{#if result.upstream_url}
				<CopyField label="Upstream request" value={result.upstream_url} />
			{/if}
			<p class="footnote secondary">
				{plural(result.transformed.length, 'asset')} after mapping and filters
			</p>
			{#if result.transformed.length > 0}
				<ul class="assets">
					{#each result.transformed as asset, i (i)}
						<li>
							<span class="thumb"
								><AssetThumb src={asset.previewURI} contentType={asset.contentType} /></span
							>
							<span class="name">{asset.title || asset.assetID || 'Untitled'}</span>
							<span class="caption tertiary">
								{[
									kindLabel(asset.contentType),
									result.licences[i]
										? `${result.licences[i].label}${result.licences[i].allowed ? '' : ' (not accepted)'}`
										: null
								]
									.filter(Boolean)
									.join(' · ')}
							</span>
						</li>
					{/each}
				</ul>
			{/if}
			<details>
				<summary>Mapped assets (JSON)</summary>
				<pre>{JSON.stringify(result.transformed, null, 2)}</pre>
			</details>
			<details>
				<summary>Raw upstream response</summary>
				<pre>{result.raw_upstream == null
						? 'No response captured.'
						: JSON.stringify(result.raw_upstream, null, 2).slice(0, 60000)}</pre>
			</details>
		{:else}
			<p class="footnote tertiary">No test run yet.</p>
		{/if}
	</div>
</section>

<style>
	.test {
		overflow: hidden;
	}

	.head {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
		padding: 16px 20px;
		border-bottom: 1px solid var(--separator);
	}

	.controls {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.controls .input {
		min-height: 36px;
		padding: 6px 12px;
	}

	.count {
		width: 76px;
	}

	.body {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding: 16px 20px 20px;
	}

	.errors {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 6px;
		color: var(--danger-text);
		font-size: 14px;
	}

	.errors li {
		display: flex;
		gap: 8px;
		align-items: flex-start;
	}

	.assets {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
		gap: 14px;
	}

	.assets li {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}

	.thumb {
		display: block;
		aspect-ratio: 1;
		border-radius: 10px;
		overflow: hidden;
	}

	.thumb :global(.caption) {
		display: none;
	}

	.name {
		font-size: 13px;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	details {
		border-top: 1px solid var(--separator);
		padding-top: 10px;
	}

	summary {
		cursor: pointer;
		font-size: 14px;
		font-weight: 500;
		color: var(--text-2);
	}

	pre {
		margin: 10px 0 0;
		max-height: 420px;
		overflow: auto;
		padding: 12px;
		border-radius: 10px;
		background: var(--surface-sunken);
		font-family: var(--font-mono);
		font-size: 12px;
		line-height: 1.5;
	}
</style>
