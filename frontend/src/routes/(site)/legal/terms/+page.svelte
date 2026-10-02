<script lang="ts">
	import { resolve } from '$app/paths';
	import LegalPage from '#lib/components/LegalPage.svelte';
</script>

<LegalPage title="Terms of use">
	<h2>1. The service</h2>
	<p>
		IMPULSE Curator lets you search open cultural-heritage archives and save a selection of their
		assets as a collection, which the IMPULSE platform and its Unity clients can load. The service
		is provided by [provider, see imprint] free of charge. There is no claim to a particular
		availability.
	</p>

	<h2>2. Your collections</h2>
	<ul>
		<li>
			Collections and their assets are public at their URL. Don't put personal data of others into
			names or descriptions.
		</li>
		<li>
			Names and descriptions must not be unlawful, discriminatory, misleading or offensive, and must
			not infringe the rights of others.
		</li>
		<li>Keep your edit link private: anyone who has it can change or delete the collection.</li>
		<li>
			[Licence for texts you write, e.g. you grant the provider a non-exclusive right to publish
			them as part of the collection.]
		</li>
	</ul>

	<h2>3. Rights in the assets</h2>
	<p>
		The assets remain with the institutions that hold them and are subject to the licences and
		rights statements shown with each asset. A collection points to them; it does not change their
		rights. Please respect the licence of every asset when you use it.
	</p>

	<h2>4. Moderation</h2>
	<p>
		We may hide, lock or delete collections that break these terms or the law, in particular after a
		report. We will inform you of the reasons where we can reach you. [Procedure and statement of
		reasons according to Art. 17 DSA, contact for complaints.]
	</p>

	<h2>5. Reporting content</h2>
	<p>
		You can report collections you consider unlawful or in breach of these terms:
		<a href={resolve('report')}>Report content</a>. Our point of contact for authorities and users
		under Art. 11 and 12 DSA is [contact address]; communication in English or German.
	</p>

	<h2>6. Liability</h2>
	<p>[Liability clause to be provided.]</p>

	<h2>7. Changes and applicable law</h2>
	<p>[Changes to these terms; applicable law and place of jurisdiction.]</p>
</LegalPage>
