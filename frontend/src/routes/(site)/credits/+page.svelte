<script lang="ts">
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { homeImages } from '#lib/home-images.js';
</script>

<LegalPage title="Credits & sources" draft={false}>
	<p>
		IMPULSE Curator searches open archives and links to their assets. The assets stay with the
		institutions that hold them, under the licence shown with each asset. Naming these archives does
		not imply their endorsement.
	</p>

	<h2>Archives</h2>
	<ul>
		<li>
			<strong>Europeana</strong> — Europe's digital cultural heritage, aggregated from many
			institutions. Metadata is published under CC0; every record names its data provider, and each
			asset carries its own rights statement.
			<a href="https://www.europeana.eu" rel="noopener noreferrer" target="_blank">europeana.eu</a>
		</li>
		<li>
			<strong>Wikimedia Commons</strong> — freely licensed media. Licences and required attribution
			differ per file and are shown with each asset.
			<a href="https://commons.wikimedia.org" rel="noopener noreferrer" target="_blank"
				>commons.wikimedia.org</a
			>
		</li>
		<li>
			<strong>Smithsonian Open Access</strong> — collection data and media released under CC0.
			<a href="https://www.si.edu/openaccess" rel="noopener noreferrer" target="_blank"
				>si.edu/openaccess</a
			>
		</li>
		<li>
			<strong>Wellcome Collection</strong> — digitised works via the IIIF standard; licences differ
			per item.
			<a href="https://wellcomecollection.org" rel="noopener noreferrer" target="_blank"
				>wellcomecollection.org</a
			>
		</li>
	</ul>

	<h2>Images on the home page</h2>
	<p>All are public-domain works, served from this website.</p>
	<ul>
		{#each Object.values(homeImages) as image (image.file)}
			<li>
				{image.title}, {image.artist} — public domain, via
				<a href={image.commons} rel="noopener noreferrer" target="_blank">Wikimedia Commons</a>
			</li>
		{/each}
	</ul>

	<h2>Design</h2>
	<ul>
		<li>IMPULSE wordmark — © the IMPULSE consortium.</li>
		<li>EU emblem — European Commission, used according to the EU visibility rules.</li>
		<li>Typefaces Geist and Geist Mono by Vercel, under the SIL Open Font License 1.1.</li>
	</ul>
</LegalPage>
