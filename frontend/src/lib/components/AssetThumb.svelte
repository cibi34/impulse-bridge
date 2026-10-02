<script lang="ts">
	import { isModel } from '#lib/format.js';
	import { previewSrc } from '#lib/images.js';
	import Icon from './Icon.svelte';

	let {
		src,
		contentType,
		alt = '',
		eager = false
	}: { src?: string | null; contentType?: string; alt?: string; eager?: boolean } = $props();

	let failed = $state(false);
	const url = $derived(previewSrc(src));
	const model = $derived(isModel(contentType));

	$effect(() => {
		// A new image gets a new chance to load.
		void url;
		failed = false;
	});
</script>

{#if url && !failed}
	<img
		src={url}
		{alt}
		loading={eager ? 'eager' : 'lazy'}
		decoding="async"
		crossorigin="anonymous"
		referrerpolicy="no-referrer"
		onerror={() => (failed = true)}
	/>
{:else}
	<span class="placeholder" role={alt ? 'img' : undefined} aria-label={alt || undefined}>
		<Icon name={model ? 'cube' : 'image'} size={40} strokeWidth={1.4} />
		<span class="caption"
			>{model ? 'glTF model' : failed ? 'Preview unavailable' : 'No preview'}</span
		>
	</span>
{/if}

<style>
	img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		background: var(--control);
	}

	.placeholder {
		width: 100%;
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 10px;
		background: radial-gradient(circle at 50% 40%, var(--control-hover), var(--surface));
		color: var(--link);
	}

	.caption {
		color: var(--text-2);
	}
</style>
