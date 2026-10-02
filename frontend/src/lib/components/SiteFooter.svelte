<script lang="ts">
	import { resolve } from '$app/paths';
	import EuFunding from './EuFunding.svelte';
	import ThemeSwitcher from './ThemeSwitcher.svelte';

	let { compact = false }: { compact?: boolean } = $props();
</script>

<footer class="footer" class:compact>
	<div class="funding">
		<EuFunding height={compact ? 30 : 40} />
		{#if !compact}
			<p class="caption tertiary">
				Views and opinions expressed are however those of the author(s) only and do not necessarily
				reflect those of the European Union or the European Research Executive Agency (REA). Neither
				the European Union nor the granting authority can be held responsible for them. IMPULSE —
				grant agreement No 101132704.
			</p>
		{/if}
	</div>
	<div class="bottom">
		<nav aria-label="Legal">
			<a href={resolve('legal/imprint')}>Imprint</a>
			<a href={resolve('legal/privacy')}>Privacy</a>
			<a href={resolve('legal/terms')}>Terms</a>
			{#if !compact}
				<a href={resolve('legal/accessibility')}>Accessibility</a>
				<a href={resolve('credits')}>Credits &amp; sources</a>
				<a href={resolve('report')}>Report content</a>
			{/if}
		</nav>
		{#if !compact}<ThemeSwitcher />{/if}
	</div>
</footer>

<style>
	.footer {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.funding {
		display: flex;
		align-items: flex-start;
		gap: 20px;
		flex-wrap: wrap;
	}

	.funding p {
		flex: 1;
		min-width: 260px;
		max-width: 720px;
	}

	.bottom {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
	}

	nav {
		display: flex;
		gap: 4px 18px;
		flex-wrap: wrap;
		font-size: 13px;
	}

	nav a {
		color: var(--text-2);
		text-decoration: none;
		padding: 4px 0;
	}

	nav a:hover {
		color: var(--text);
		text-decoration: underline;
	}

	.compact {
		gap: 12px;
	}

	.compact nav {
		gap: 4px 12px;
		font-size: 12px;
	}
</style>
