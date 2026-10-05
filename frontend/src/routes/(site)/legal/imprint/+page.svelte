<script lang="ts">
	import { resolve } from '$app/paths';
	import Email from '#lib/components/Email.svelte';
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { legalDraft, provider } from '#lib/legal.js';
</script>

<LegalPage title="Imprint" updated={provider.updated} draft={legalDraft}>
	<p>Information according to § 5 DDG (German Digital Services Act).</p>

	<h2>Provider</h2>
	<address>
		{provider.name}<br />
		{provider.street}<br />
		{provider.city}<br />
		{provider.country}
	</address>

	<h2>Represented by</h2>
	<p>{provider.representedBy}</p>

	<h2>Contact</h2>
	<p>
		Email: <Email address={provider.email} /><br />
		Phone: {provider.phone}<br />
		Website:
		<a href={provider.website} rel="noopener noreferrer" target="_blank">{provider.website}</a>
	</p>

	<h2>Register entry</h2>
	<p>{provider.registerCourt}, {provider.registerNumber}</p>

	{#if provider.vatId}
		<h2>VAT identification number</h2>
		<p>{provider.vatId}</p>
	{/if}

	<h2>Responsible for the content of this website</h2>
	<p>{provider.representedBy}, address as above.</p>

	<h2>Project</h2>
	<p>
		IMPULSE Curator is developed and operated by {provider.name} ({provider.short}) as a partner in
		the research project
		<a href={provider.impulse.url} rel="noopener noreferrer" target="_blank"
			>{provider.impulse.name}</a
		>. IMPULSE has received funding from the European Union's Horizon Europe research and innovation
		programme under grant agreement No {provider.impulse.grant}.
	</p>
	<p>
		Views and opinions expressed are those of the author(s) only and do not necessarily reflect
		those of the European Union or the European Research Executive Agency (REA). Neither the
		European Union nor the granting authority can be held responsible for them.
	</p>

	<h2>Content from the archives</h2>
	<p>
		The images, 3D models and descriptions shown in the Curator come from the archives named with
		each asset — Europeana, Wikimedia Commons, Heidelberg University Library and others. The works
		stay on the archives' servers; the Curator links to them and keeps a copy of their descriptions.
		The archives are responsible for these works, their descriptions and their rights statements.
		Collections are created by visitors, who are responsible for the names and descriptions they
		write. Something wrong?
		<a href={resolve('report')}>Report content</a>.
	</p>

	<h2>Point of contact under the Digital Services Act</h2>
	<p>
		For authorities and users (Art. 11 and 12 DSA): <Email address={provider.email} />. Languages:
		German and English.
	</p>

	<h2>Consumer dispute resolution</h2>
	<p>
		We are neither willing nor obliged to take part in dispute resolution proceedings before a
		consumer arbitration board.
	</p>
</LegalPage>
