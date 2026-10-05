<script lang="ts">
	import { onMount } from 'svelte';
	import AssetThumb from './AssetThumb.svelte';

	// Google's <model-viewer> (three.js underneath): orbit, zoom and a poster
	// while the glTF loads. Its code is fetched only when a viewer is shown.
	let {
		src,
		poster = null,
		alt = ''
	}: { src: string; poster?: string | null; alt?: string } = $props();

	let phase = $state<'loading' | 'ready' | 'failed'>('loading');
	let progress = $state(0);
	let loaded = $state(false);
	let element = $state<HTMLElement | null>(null);
	const percent = $derived(Math.round(progress * 100));

	onMount(async () => {
		try {
			await import('@google/model-viewer');
			phase = 'ready';
		} catch {
			phase = 'failed';
		}
	});

	/** Show the model on the whole screen (Esc leaves). */
	export function fullscreen() {
		element?.requestFullscreen?.();
	}
</script>

<div class="viewer">
	{#if phase !== 'ready'}
		<div class="backdrop"><AssetThumb src={poster} {alt} eager /></div>
	{:else}
		<model-viewer
			bind:this={element}
			{src}
			poster={poster ?? undefined}
			{alt}
			camera-controls
			auto-rotate
			shadow-intensity="1"
			touch-action="pan-y"
			loading="eager"
			onprogress={(e: Event) => (progress = (e as CustomEvent).detail?.totalProgress ?? 0)}
			onload={() => (loaded = true)}
			onerror={() => (phase = 'failed')}
		>
			<!-- An empty slot replaces model-viewer's own, barely visible bar. -->
			<div slot="progress-bar"></div>
		</model-viewer>
	{/if}
	{#if phase === 'failed'}
		<p class="status" role="alert">The model could not be loaded.</p>
	{:else if !loaded}
		<div class="loading" role="status" aria-live="polite">
			<span class="label"
				>{phase === 'ready' ? `Loading model … ${percent} %` : 'Loading the 3D viewer …'}</span
			>
			<span class="track"
				><span class="bar" style="width: {phase === 'ready' ? percent : 4}%"></span></span
			>
		</div>
	{/if}
</div>

<style>
	.viewer {
		position: relative;
		width: 100%;
		height: 100%;
		background: var(--surface-sunken);
	}

	.backdrop {
		position: absolute;
		inset: 0;
		opacity: 0.6;
	}

	model-viewer {
		display: block;
		width: 100%;
		height: 100%;
		background: var(--surface-sunken);
		--poster-color: transparent;
	}

	.loading {
		position: absolute;
		left: 16px;
		right: 16px;
		bottom: 16px;
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 12px 14px;
		border-radius: 12px;
		background: color-mix(in srgb, var(--surface) 88%, transparent);
		box-shadow: 0 4px 16px rgb(0 0 0 / 0.18);
		font-size: 14px;
		font-weight: 500;
		color: var(--text);
	}

	.track {
		display: block;
		height: 6px;
		border-radius: 999px;
		background: var(--control);
		overflow: hidden;
	}

	.bar {
		display: block;
		height: 100%;
		border-radius: 999px;
		background: var(--action);
		transition: width 0.2s ease-out;
	}

	.status {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0;
		color: var(--text-2);
		font-size: 14px;
	}
</style>
