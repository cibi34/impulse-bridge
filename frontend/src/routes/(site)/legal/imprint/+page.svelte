<script lang="ts">
	import { resolve } from '$app/paths';
	import Email from '#lib/components/Email.svelte';
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { known, legalDraft, provider } from '#lib/legal.js';

	// Lines whose facts are still missing from legal.ts are left out rather
	// than shown as blanks; the page notice says what is still to come.
	const address = known(provider.street) && known(provider.city);
	const contact = known(provider.email) || known(provider.phone);
	const register = known(provider.registerCourt) && known(provider.registerNumber);
</script>

<LegalPage title="Imprint" updated={provider.updated} draft={legalDraft}>
	<p>Information according to § 5 DDG (German Digital Services Act).</p>

	<h2>Provider</h2>
	<address>
		{provider.name}<br />
		{#if address}
			{provider.street}<br />
			{provider.city}<br />
		{/if}
		{provider.country}
	</address>

	{#if known(provider.representedBy)}
		<h2>Represented by</h2>
		<p>{provider.representedBy}</p>
	{/if}

	<h2>Contact</h2>
	<p>
		{#if known(provider.email)}Email: <Email address={provider.email} /><br />{/if}
		{#if known(provider.phone)}Phone: {provider.phone}<br />{/if}
		Website:
		<a href={provider.website} rel="noopener noreferrer" target="_blank">{provider.website}</a>
	</p>

	{#if register}
		<h2>Register entry</h2>
		<p>{provider.registerCourt}, {provider.registerNumber}</p>
	{/if}

	{#if known(provider.vatId)}
		<h2>VAT identification number</h2>
		<p>{provider.vatId}</p>
	{/if}

	{#if known(provider.representedBy)}
		<h2>Responsible for the content of this website</h2>
		<p>{provider.representedBy}, address as above.</p>
	{/if}

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

	{#if contact}
		<h2>Point of contact under the Digital Services Act</h2>
		<p>
			For authorities and users (Art. 11 and 12 DSA):
			{#if known(provider.email)}<Email address={provider.email} />{:else}{provider.phone}{/if}.
			Languages: German and English.
		</p>
	{/if}

	<h2>Consumer dispute resolution</h2>
	<p>
		We are neither willing nor obliged to take part in dispute resolution proceedings before a
		consumer arbitration board.
	</p>
</LegalPage>
