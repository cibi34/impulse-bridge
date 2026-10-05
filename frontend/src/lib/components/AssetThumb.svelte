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

	// First try: anonymous, so no cookies travel to the archive. An image
	// server without CORS headers refuses that, so the second try is a plain
	// request; only then is the preview given up.
	let anonymous = $state(true);
	let failed = $state(false);
	const url = $derived(previewSrc(src));
	const model = $derived(isModel(contentType));

	$effect(() => {
		// A new image gets a new chance to load.
		void url;
		anonymous = true;
		failed = false;
	});

	function onerror() {
		if (anonymous) anonymous = false;
		else failed = true;
	}
</script>

{#if url && !failed}
	{#key anonymous}
		<img
			src={url}
			{alt}
			loading={eager ? 'eager' : 'lazy'}
			decoding="async"
			crossorigin={anonymous ? 'anonymous' : undefined}
			referrerpolicy="no-referrer"
			{onerror}
		/>
	{/key}
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
