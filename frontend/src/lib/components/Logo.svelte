<script lang="ts">
	import { asset, resolve } from '$app/paths';

	let { height = 18 }: { height?: number } = $props();
</script>

<a href={resolve('')} class="logo" aria-label="IMPULSE Curator, home">
	<img
		src={asset('brand/impulse-wordmark-gradient.webp')}
		alt=""
		width={Math.round((height * 555) / 96)}
		{height}
	/>
	<span class="name" style:font-size="{Math.round(height * 0.84)}px">Curator</span>
</a>

<style>
	.logo {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		color: var(--text);
		text-decoration: none;
		border-radius: 8px;
	}

	img {
		width: auto;
	}

	.name {
		font-weight: 600;
		letter-spacing: -0.01em;
		line-height: 1;
	}
</style>
