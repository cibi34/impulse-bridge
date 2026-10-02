<script lang="ts">
	import { asset } from '$app/paths';

	// The official "Funded by the European Union" emblem (EC logo download
	// centre), unmodified: the negative version on dark, positive on light.
	let { height = 40 }: { height?: number } = $props();
	const width = $derived(Math.round((height * 674) / 144));
</script>

<span class="eu">
	<img
		class="neg"
		src={asset('brand/eu-funded-neg.png')}
		alt="Funded by the European Union"
		{width}
		{height}
	/>
	<!-- Only the visible variant is exposed to assistive technology. -->
	<img
		class="pos"
		src={asset('brand/eu-funded-pos.png')}
		alt="Funded by the European Union"
		{width}
		{height}
	/>
</span>

<style>
	.eu {
		display: inline-block;
		flex-shrink: 0;
	}

	.pos {
		display: none;
	}

	:global(:root[data-theme='light']) .neg {
		display: none;
	}

	:global(:root[data-theme='light']) .pos {
		display: block;
	}

	@media (prefers-color-scheme: light) {
		:global(:root[data-theme='system']) .neg {
			display: none;
		}
		:global(:root[data-theme='system']) .pos {
			display: block;
		}
	}
</style>
