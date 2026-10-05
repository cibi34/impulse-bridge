<script lang="ts">
	import { asset } from '$app/paths';

	// Who built the Curator: the institute's logo, light on dark and dark on
	// light, like the EU emblem next to it.
	let { height = 32 }: { height?: number } = $props();
	const width = $derived(Math.round((height * 1050) / 290));
	const alt = 'Developed by Institut für Strategische Ästhetik gGmbH';
</script>

<span class="credit">
	<span class="label tertiary">Developed by</span>
	<img class="neg" src={asset('brand/k8-neg.png')} {alt} {width} {height} />
	<!-- Only the visible variant is exposed to assistive technology. -->
	<img class="pos" src={asset('brand/k8-pos.png')} {alt} {width} {height} />
</span>

<style>
	.credit {
		display: inline-flex;
		flex-direction: column;
		gap: 4px;
		flex-shrink: 0;
	}

	.label {
		font-size: 11px;
		line-height: 1;
	}

	img {
		display: block;
		opacity: 0.85;
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
