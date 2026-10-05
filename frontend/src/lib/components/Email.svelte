<script lang="ts">
	import { isPlaceholder } from '#lib/legal.js';

	// An email address as a mailto link — or as plain text while it is still
	// a [placeholder], so nothing links to a made-up address.
	let { address }: { address: string } = $props();
</script>

{#if isPlaceholder(address)}
	{address}
{:else}
	<a href="mailto:{address}">{address}</a>
{/if}
