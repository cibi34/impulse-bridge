<script lang="ts">
	import { resolve } from '$app/paths';
	import Email from '#lib/components/Email.svelte';
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { known, legalDraft, provider } from '#lib/legal.js';
</script>

<LegalPage title="Accessibility" updated={provider.updated} draft={legalDraft}>
	<p>
		This statement applies to IMPULSE Curator at {provider.siteUrl}. {provider.name} is not a public-sector
		body; we publish this statement voluntarily because the Curator is built for everyone who works with
		cultural heritage.
	</p>

	<h2>Status</h2>
	<p>
		We aim for conformance with WCAG 2.2 at level AA. Automated checks (axe-core) find no violations
		on any page or dialog, in light and in dark appearance. A manual audit by accessibility experts
		has not been done yet.
	</p>

	<h2>What works</h2>
	<ul>
		<li>
			Everything can be done with the keyboard, including reordering assets with the arrow keys.
		</li>
		<li>Focus is always visible; reduced-motion settings are respected.</li>
		<li>Text scales with your browser's settings; the layout works on phones.</li>
		<li>Light, dark and system appearance, with sufficient contrast in each.</li>
	</ul>

	<h2>Known limitations</h2>
	<ul>
		<li>
			Images and their descriptions come from the archives. Most images have no text alternative
			beyond their title and creator, which the Curator uses instead.
		</li>
		<li>3D models are shown through a preview image; the model itself is loaded by IMPULSE.</li>
		<li>The quality of the archives' metadata varies, and some of it is not in English.</li>
	</ul>

	<h2>Feedback</h2>
	<p>
		If something is hard to use, tell us
		{#if known(provider.email)}
			at <Email address={provider.email} />.
		{:else}
			through the contact in the <a href={resolve('legal/imprint')}>imprint</a>.
		{/if}
		We aim to reply within two weeks.
	</p>
</LegalPage>
