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
			<strong>Heidelberg University Library</strong> — the Codex Manesse (Cod. Pal. germ. 848),
			digitised and served via the IIIF standard under the Public Domain Mark.
			<a
				href="https://digi.ub.uni-heidelberg.de/diglit/cpg848"
				rel="noopener noreferrer"
				target="_blank">digi.ub.uni-heidelberg.de</a
			>
		</li>
		<li>
			<strong>Statens Museum for Kunst</strong> — the Danish National Gallery's SMK Open: works in
			the public domain, released under the Public Domain Mark.
			<a href="https://open.smk.dk" rel="noopener noreferrer" target="_blank">open.smk.dk</a>
		</li>
		<li>
			<strong>Zenodo</strong> — the open research repository run by CERN for OpenAIRE; 3D models
			published there by their authors, each record under the licence its authors chose.
			<a href="https://zenodo.org" rel="noopener noreferrer" target="_blank">zenodo.org</a>
		</li>
		<li>
			<strong>Wellcome Collection</strong> — London; images released under CC BY, CC0 or the Public
			Domain Mark, served via IIIF.
			<a href="https://wellcomecollection.org" rel="noopener noreferrer" target="_blank"
				>wellcomecollection.org</a
			>
		</li>
		<li>
			<strong>The Cleveland Museum of Art</strong> — Open Access: works and images released as CC0.
			<a href="https://www.clevelandart.org/open-access" rel="noopener noreferrer" target="_blank"
				>clevelandart.org/open-access</a
			>
		</li>
		<li>
			<strong>The Metropolitan Museum of Art</strong> — New York; Open Access images of
			public-domain works released as CC0.
			<a
				href="https://www.metmuseum.org/about-the-met/policies-and-documents/open-access"
				rel="noopener noreferrer"
				target="_blank">metmuseum.org/open-access</a
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

	<h2>Design and development</h2>
	<ul>
		<li>
			IMPULSE Curator was designed and developed by Institut für Strategische Ästhetik gGmbH (K8).
		</li>
		<li>IMPULSE wordmark — © the IMPULSE consortium.</li>
		<li>EU emblem — European Commission, used according to the EU visibility rules.</li>
		<li>Typefaces Geist and Geist Mono by Vercel, under the SIL Open Font License 1.1.</li>
		<li>
			3D viewer: <code>&lt;model-viewer&gt;</code> by Google (Apache License 2.0), built on three.js (MIT
			License); served from this site.
		</li>
	</ul>
</LegalPage>
