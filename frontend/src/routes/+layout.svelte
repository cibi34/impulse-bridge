<script lang="ts">
	import '@fontsource-variable/geist';
	import '@fontsource-variable/geist-mono';
	import '../app.css';
	import { onMount } from 'svelte';
	import Toasts from '#lib/components/Toasts.svelte';
	import { app } from '#lib/stores/app.svelte.js';

	let { children } = $props();

	onMount(() => {
		app.load();
	});
</script>

{@render children()}
<Toasts />
