<script lang="ts">
	import { onMount } from 'svelte';

	// Google's <model-viewer> (three.js underneath): orbit, zoom and a poster
	// while the glTF loads. Its code is fetched only when a viewer is shown.
	let {
		src,
		poster = null,
		alt = ''
	}: { src: string; poster?: string | null; alt?: string } = $props();

	let state = $state<'loading' | 'ready' | 'failed'>('loading');

	onMount(async () => {
		try {
			await import('@google/model-viewer');
			state = 'ready';
		} catch {
			state = 'failed';
		}
	});
</script>

{#if state === 'ready'}
	<model-viewer
		{src}
		poster={poster ?? undefined}
		{alt}
		camera-controls
		auto-rotate
		shadow-intensity="1"
		touch-action="pan-y"
		loading="eager"
		onerror={() => (state = 'failed')}
	></model-viewer>
{:else}
	<p class="status">
		{state === 'failed' ? 'The model could not be loaded.' : 'Loading the 3D viewer…'}
	</p>
{/if}

<style>
	model-viewer {
		display: block;
		width: 100%;
		height: 100%;
		background: var(--surface-sunken);
		--poster-color: var(--surface-sunken);
	}

	.status {
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-2);
		font-size: 14px;
	}
</style>
