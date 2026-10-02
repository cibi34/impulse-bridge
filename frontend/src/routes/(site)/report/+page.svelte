<script lang="ts">
	import LegalPage from '#lib/components/LegalPage.svelte';

	// Notice-and-action mechanism (Art. 16 DSA). The address is still a
	// placeholder, like the rest of the legal content.
	const REPORT_ADDRESS = '[report email address]';
	const template = `Collection URL:
[paste the address of the collection, or of the asset within it]

What is wrong, and why it is unlawful or breaks the terms of use:
[your explanation]

Your name and email address:
[optional for reports of child sexual abuse material]

I believe in good faith that the information in this report is accurate and complete.`;
</script>

<LegalPage title="Report content">
	<p>
		If you think a collection or its description is unlawful or breaks our terms of use, tell us. We
		review every report and act on it without undue delay.
	</p>

	<h2>How to report</h2>
	<p>Send an email to <strong>{REPORT_ADDRESS}</strong> with:</p>
	<ul>
		<li>the address (URL) of the collection,</li>
		<li>an explanation of why you consider it unlawful or in breach of the terms,</li>
		<li>your name and email address (not required for reports of child sexual abuse material),</li>
		<li>a statement that you believe the report is accurate and complete.</li>
	</ul>

	<h3>Template</h3>
	<pre class="template">{template}</pre>

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
