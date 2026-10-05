<script lang="ts">
	import Email from '#lib/components/Email.svelte';
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { known, legalDraft, provider } from '#lib/legal.js';

	// Notice-and-action mechanism (Art. 16 DSA).
	const template = `Collection URL:
[paste the address of the collection, or of the asset within it]

What is wrong, and why it is unlawful or breaks the terms of use:
[your explanation]

Your name and email address:
[optional for reports of child sexual abuse material]

I believe in good faith that the information in this report is accurate and complete.`;
</script>

<LegalPage title="Report content" updated={provider.updated} draft={legalDraft}>
	<p>
		Collections on IMPULSE Curator are created by visitors; the assets in them come from the
		archives. If a collection is unlawful or breaks the terms of use, tell us. Reports are handled
		by {provider.name}.
	</p>

	<h2>How to report</h2>
	{#if known(provider.reportEmail)}
		<p>Send an email to <Email address={provider.reportEmail} /> with:</p>
	{:else}
		<p>
			The report address will be published here before the public launch. Until then, reach the team
			through
			<a href={provider.website} rel="noopener noreferrer" target="_blank">{provider.website}</a>
			with:
		</p>
	{/if}
	<ul>
		<li>the address (URL) of the collection,</li>
		<li>an explanation of why you consider it unlawful or in breach of the terms,</li>
		<li>your name and email address (not required for reports of child sexual abuse material),</li>
		<li>a statement that you believe the report is accurate and complete.</li>
	</ul>

	<h3>Template</h3>
	<pre class="template">{template}</pre>

	<h2>What happens next</h2>
	<p>
		We confirm that we received your report and review it, usually within a few days. If it is
		justified, we hide the collection from the public list, lock it or delete it, and we tell you
		the outcome. Where we can reach the collection's creator, we tell them what we did and why.
		Reports that are manifestly unfounded, or repeated in bad faith, may be left unanswered.
	</p>

	<p>
		Problems with an asset itself — its licence, metadata or image — are best reported to the
		archive that holds it; its source is linked from the asset's details.
	</p>
</LegalPage>

<style>
	.template {
		margin: 10px 0 20px;
		padding: 16px;
		border-radius: 12px;
		background: var(--surface);
		border: 1px solid var(--separator);
		font-family: var(--font-mono);
		font-size: 13px;
		white-space: pre-wrap;
		color: var(--text-2);
	}
</style>
