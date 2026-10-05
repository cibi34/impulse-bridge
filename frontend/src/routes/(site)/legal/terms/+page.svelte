<script lang="ts">
	import { resolve } from '$app/paths';
	import Email from '#lib/components/Email.svelte';
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { known, legalDraft, provider } from '#lib/legal.js';
</script>

<LegalPage title="Terms of use" updated={provider.updated} draft={legalDraft}>
	<h2>1. The service</h2>
	<p>
		IMPULSE Curator is a free tool provided by {provider.name} ({provider.short}) within the
		research project IMPULSE. It searches open cultural heritage archives and lets you compile
		collections that IMPULSE's software can load. It is a research prototype: we do not guarantee
		that it is available at all times, and we may change or discontinue it.
	</p>

	<h2>2. Your collections</h2>
	<ul>
		<li>
			You can create collections without an account. Every collection is public at its own address;
			anyone with the link can view it.
		</li>
		<li>
			The name and description of a collection are yours. Don't write anything unlawful, offensive
			or that infringes other people's rights, and don't include personal data of others.
		</li>
		<li>
			The edit link lets anyone who has it change or delete the collection. Keep it private. If it
			leaks, create a new one in the editor.
		</li>
		<li>
			Collections are meant for IMPULSE and for cultural, educational and research use. Don't use
			the service to harvest archives or to overload them.
		</li>
	</ul>

	<h2>3. The assets and their rights</h2>
	<p>
		The images, 3D models and descriptions in a collection come from the archives named with each
		asset. The rights in these works stay with their holders; each asset shows its licence and a
		link to its source. The Curator only offers works whose licence IMPULSE accepts, and every
		collection lists its licences and the credits they require.
	</p>
	<p>
		You are responsible for complying with those licences wherever you use the works — crediting the
		creators, and sharing adaptations under the same licence where it says so. The Curator gives you
		the credits for copying and as a CSV file.
	</p>
	<p>
		We do not check the works, descriptions or rights statements the archives provide and are not
		responsible for them. Problems with an asset are best reported to the archive that holds it; its
		source is linked from the asset's details.
	</p>

	<h2>4. Moderation</h2>
	<p>
		We may hide a collection from the public list, lock it against changes, or delete it when it
		breaks these terms or the law, or when an archive asks us to. Where we know the creator's email
		address, we tell them what we did and why. Collections that IMPULSE no longer needs may be
		removed after the project ends.
	</p>

	<h2>5. Reporting content</h2>
	<p>
		If you think a collection is unlawful or breaks these terms, tell us:
		<a href={resolve('report')}>Report content</a>.
		{#if known(provider.email)}
			Point of contact under the Digital Services Act: <Email address={provider.email} />.
		{/if}
	</p>

	<h2>6. Liability</h2>
	<p>
		The service is provided free of charge and as it is. We are liable without limit for intent and
		gross negligence and for injury to life, body or health. For slight negligence we are liable
		only for the breach of obligations that are essential to the service, and only for the damage
		that was foreseeable when the service was used. We are not liable for the content and
		availability of the archives.
	</p>

	<h2>7. Changes and applicable law</h2>
	<p>
		We may change these terms when the service changes; the date at the top shows the current
		version. German law applies. Mandatory consumer protections of the country you live in are not
		affected.
	</p>

	<p>
		See also the <a href={resolve('legal/privacy')}>privacy notice</a> and the
		<a href={resolve('legal/imprint')}>imprint</a>.
	</p>
</LegalPage>
