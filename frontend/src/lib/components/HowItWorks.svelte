<script lang="ts">
	import { asset } from '$app/paths';
	import { homeImages } from '#lib/home-images.js';
	import Icon from './Icon.svelte';

	const steps = [
		{
			id: 'find',
			title: 'Find',
			text: 'Search open archives such as Europeana and Wikimedia Commons, one at a time or all at once.'
		},
		{
			id: 'select',
			title: 'Select',
			text: 'Tap the works you want. Your selection stays while you keep searching other archives.'
		},
		{
			id: 'create',
			title: 'Create',
			text: 'Give your collection a name and a short description. You get a private link to edit it later.'
		},
		{
			id: 'submit',
			title: 'Submit',
			text: 'Send the collection to the IMPULSE team. Once it is added, Unity clients load it from its URL.'
		}
	] as const;

	let current = $state(0);
	const id = $props.id();
	const tabs: HTMLButtonElement[] = $state([]);

	// Tabs pattern (WAI-ARIA APG): arrows move between steps, Home/End jump.
	function onkeydown(event: KeyboardEvent) {
		const count = steps.length;
		let next: number;
		switch (event.key) {
			case 'ArrowDown':
			case 'ArrowRight':
				next = (current + 1) % count;
				break;
			case 'ArrowUp':
			case 'ArrowLeft':
				next = (current - 1 + count) % count;
				break;
			case 'Home':
				next = 0;
				break;
			case 'End':
				next = count - 1;
				break;
			default:
				return;
		}
		event.preventDefault();
		current = next;
		tabs[next]?.focus();
	}
</script>

<div class="how">
	<div class="tabs" role="tablist" aria-label="How it works" aria-orientation="vertical">
		{#each steps as step, i (step.id)}
			<button
				bind:this={tabs[i]}
				type="button"
				role="tab"
				id="{id}-tab-{step.id}"
				aria-selected={current === i}
				aria-controls="{id}-panel"
				tabindex={current === i ? 0 : -1}
				class="tab"
				onclick={() => (current = i)}
				{onkeydown}
			>
				<span class="number" aria-hidden="true">{i + 1}</span>
				<span class="tab-text">
					<span class="headline">{step.title}</span>
					<span class="tab-description">{step.text}</span>
				</span>
			</button>
		{/each}
	</div>

	<div
		class="panel"
		role="tabpanel"
		id="{id}-panel"
		aria-labelledby="{id}-tab-{steps[current].id}"
		tabindex="0"
	>
		{#if steps[current].id === 'find'}
			<div class="demo">
				<div class="fake-search" aria-hidden="true">
					<Icon name="search" size={18} strokeWidth={2} /> japanese woodblock
				</div>
				<div class="grid three">
					{#each [homeImages.hokusai, homeImages.monet, homeImages.vangogh] as image (image.file)}
						<img src={asset(image.file)} alt="{image.title}, {image.artist}" loading="lazy" />
					{/each}
				</div>
				<p class="footnote tertiary">Filter by images or 3D models, and by archive.</p>
			</div>
		{:else if steps[current].id === 'select'}
			<div class="demo">
				<div class="grid three tall">
					{#each [homeImages.vermeer, homeImages.klimt, homeImages.durer] as image, i (image.file)}
						<span class="pick" class:on={i !== 1}>
							<img src={asset(image.file)} alt="{image.title}, {image.artist}" loading="lazy" />
							<span class="check" aria-hidden="true">
								{#if i !== 1}<Icon name="check" size={12} strokeWidth={3} />{/if}
							</span>
						</span>
					{/each}
				</div>
				<div class="fake-bar" aria-hidden="true">
					<span>2 assets selected</span>
					<span class="fake-button">Create collection</span>
				</div>
			</div>
		{:else if steps[current].id === 'create'}
			<dl class="demo card">
				<dt>Name</dt>
				<dd class="title">Masters of light</dd>
				<dt>Description</dt>
				<dd>Portraits and landscapes for the gallery scene.</dd>
				<dt>Edit link</dt>
				<dd class="mono">…/c/masters-of-light-k3m9x2/edit#key=•••••</dd>
			</dl>
		{:else}
			<div class="demo">
				<span class="footnote tertiary">Collection URL for IMPULSE</span>
				<code class="url">…/collections/masters-of-light-k3m9x2</code>
				<span class="fake-button big" aria-hidden="true"
					><Icon name="mail" /> Submit to IMPULSE</span
				>
				<p class="footnote tertiary">
					Changes you make later reach IMPULSE automatically — the URL stays the same.
				</p>
			</div>
		{/if}
	</div>
</div>

<style>
	.how {
		display: grid;
		grid-template-columns: minmax(0, 380px) minmax(0, 1fr);
		gap: 40px;
	}

	.tabs {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.tab {
		display: flex;
		gap: 16px;
		width: 100%;
		padding: 18px 20px;
		border: 1px solid transparent;
		border-radius: 16px;
		background: transparent;
		color: var(--text-2);
		text-align: left;
		transition: background-color 0.15s ease;
	}

	.tab:hover {
		background: var(--surface);
	}

	.tab[aria-selected='true'] {
		border-color: rgb(236 0 140 / 0.45);
		background: var(--surface);
		color: var(--text);
	}

	.number {
		flex-shrink: 0;
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		border-radius: 50%;
		background: var(--control);
		font-size: 14px;
		font-weight: 600;
	}

	.tab[aria-selected='true'] .number {
		background: var(--action);
		color: var(--text-on-action);
	}

	.tab-text {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.tab-description {
		display: none;
		font-size: 14px;
		color: var(--text-2);
	}

	.tab[aria-selected='true'] .tab-description {
		display: block;
	}

	.panel {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 420px;
		padding: 40px;
		border-radius: 24px;
		background: var(--bg-elevated);
		border: 1px solid var(--separator);
	}

	.demo {
		width: 100%;
		max-width: 520px;
		display: flex;
		flex-direction: column;
		gap: 16px;
		animation: fade 0.25s ease-out;
	}

	@keyframes fade {
		from {
			opacity: 0;
			transform: translateY(6px);
		}
	}

	.fake-search {
		display: flex;
		align-items: center;
		gap: 10px;
		height: 46px;
		padding: 0 16px;
		border-radius: 12px;
		background: var(--control);
		color: var(--text);
	}

	.fake-search :global(svg) {
		color: var(--text-3);
	}

	.grid {
		display: grid;
		gap: 12px;
	}

	.three {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}

	.grid img {
		width: 100%;
		aspect-ratio: 1;
		object-fit: cover;
		border-radius: 12px;
	}

	.tall img {
		aspect-ratio: 4 / 5;
	}

	.pick {
		position: relative;
		display: block;
	}

	.pick.on img {
		box-shadow: 0 0 0 3px var(--magenta);
	}

	.check {
		position: absolute;
		top: 8px;
		right: 8px;
		display: grid;
		place-items: center;
		width: 24px;
		height: 24px;
		border-radius: 50%;
		border: 2px solid rgb(255 255 255 / 0.9);
		background: rgb(18 18 20 / 0.35);
		color: #fff;
	}

	.pick.on .check {
		background: var(--magenta);
		border-color: #fff;
	}

	.fake-bar {
		align-self: center;
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 8px 8px 16px;
		border-radius: 999px;
		background: var(--control);
		font-size: 14px;
	}

	.fake-button {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		height: 34px;
		padding: 0 16px;
		border-radius: 999px;
		background: var(--action);
		color: var(--text-on-action);
		font-size: 14px;
		font-weight: 600;
	}

	.fake-button.big {
		align-self: flex-start;
		height: 44px;
		padding: 0 20px;
		font-size: 15px;
	}

	.card {
		margin: 0;
		max-width: 440px;
		padding: 24px;
		border-radius: 18px;
		background: var(--control);
		gap: 6px;
	}

	dt {
		font-size: 13px;
		color: var(--text-3);
		margin-top: 6px;
	}

	dd {
		margin: 0;
		color: var(--text-2);
	}

	dd.title {
		color: var(--text);
		font-size: 20px;
		font-weight: 600;
	}

	.url {
		display: block;
		padding: 12px 14px;
		border-radius: 12px;
		background: var(--control);
		font-family: var(--font-mono);
		font-size: 13px;
		overflow-wrap: anywhere;
	}

	@media (max-width: 900px) {
		.how {
			grid-template-columns: minmax(0, 1fr);
			gap: 20px;
		}
		.panel {
			min-height: 0;
			padding: 24px;
		}
	}
</style>
