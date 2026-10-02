<script lang="ts">
	import { asset, resolve } from '$app/paths';
	import HowItWorks from '#lib/components/HowItWorks.svelte';
	import { homeImages } from '#lib/home-images.js';

	const faq = [
		{
			q: 'Do I need an account?',
			a: 'No. When you create a collection, you get a private edit link. Add your email if you want to sign in and edit your collections on other devices.'
		},
		{
			q: 'Who owns the assets?',
			a: 'The institutions that hold them. Every asset shows its licence and source, and your collection keeps that information for IMPULSE.'
		},
		{
			q: 'Can I change a collection after submitting it?',
			a: 'Yes. Its URL stays the same, so your changes reach IMPULSE without submitting again.'
		},
		{
			q: 'Where do the assets come from?',
			a: 'From open archives: Europeana, Wikimedia Commons, the Smithsonian and IIIF collections such as Wellcome Collection. The files stay with them; a collection points to them.'
		}
	];
</script>

<svelte:head>
	<title>IMPULSE Curator — collections from open cultural heritage</title>
</svelte:head>

<section class="hero container" aria-labelledby="hero-title">
	<div class="copy">
		<img
			class="lockup"
			src={asset('brand/impulse-lockup-gradient.webp')}
			alt="IMPULSE — Immersive digitisation: upcycling cultural heritage towards new reviving strategies"
			width="420"
			height="120"
		/>
		<h1 id="hero-title">Curate cultural heritage for immersive worlds.</h1>
		<p class="lead">
			Search Europeana, Wikimedia Commons, the Smithsonian and Wellcome Collection, pick the works
			you need, and hand IMPULSE a ready-made collection.
		</p>
		<div class="actions">
			<a class="btn btn-primary btn-lg" href={resolve('explore')}>Start exploring</a>
			<a class="btn btn-lg" href="#how">How it works</a>
		</div>
		<p class="footnote tertiary">
			No account needed. You get a private link to edit your collection later.
		</p>
	</div>
	<div class="art" aria-hidden="true">
		<img src={asset(homeImages.vermeer.file)} alt="" width="500" height="592" class="a" />
		<div class="stack">
			<img src={asset(homeImages.hokusai.file)} alt="" width="500" height="342" class="b" />
			<img src={asset(homeImages.durer.file)} alt="" width="500" height="569" class="c" />
		</div>
	</div>
</section>

<section class="sources" aria-label="Archives">
	<div class="container row">
		<span class="tertiary">Search across</span>
		<span>Europeana</span>
		<span>Wikimedia Commons</span>
		<span>Smithsonian Open Access</span>
		<span>Wellcome Collection</span>
	</div>
</section>

<section id="how" class="container block" aria-labelledby="how-title">
	<div class="section-heading">
		<p class="eyebrow">How it works</p>
		<h2 id="how-title" class="large-title">From archive to Unity in four steps.</h2>
	</div>
	<HowItWorks />
</section>

<section class="container block faq" aria-labelledby="faq-title">
	<h2 id="faq-title" class="title">Questions</h2>
	<div class="faq-list">
		{#each faq as item (item.q)}
			<details>
				<summary>{item.q}</summary>
				<p class="secondary">{item.a}</p>
			</details>
		{/each}
	</div>
</section>

<style>
	.hero {
		display: grid;
		grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
		gap: 64px;
		align-items: center;
		padding-block: clamp(48px, 9vw, 96px) 72px;
	}

	.copy {
		display: flex;
		flex-direction: column;
		gap: 26px;
	}

	.lockup {
		width: 100%;
		max-width: 420px;
		height: auto;
	}

	h1 {
		font-size: clamp(40px, 6vw, 60px);
		line-height: 1.04;
		font-weight: 700;
		letter-spacing: -0.035em;
	}

	.lead {
		max-width: 540px;
		font-size: 19px;
		color: var(--text-2);
	}

	.actions {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
	}

	.art {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
	}

	.art img {
		width: 100%;
		height: auto;
		object-fit: cover;
		border-radius: 20px;
	}

	.art .a {
		aspect-ratio: 4 / 5;
	}

	.stack {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding-top: 48px;
	}

	.art .b {
		aspect-ratio: 1;
	}

	.art .c {
		aspect-ratio: 4 / 3;
	}

	.sources {
		border-block: 1px solid var(--separator);
	}

	.sources .row {
		display: flex;
		align-items: center;
		gap: 12px 28px;
		flex-wrap: wrap;
		padding-block: 22px;
		font-size: 14px;
		font-weight: 500;
	}

	.block {
		padding-block: 88px 24px;
	}

	.section-heading {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 36px;
	}

	.faq {
		max-width: 860px;
		padding-bottom: 96px;
	}

	.faq-list {
		margin-top: 20px;
		border-top: 1px solid var(--separator);
	}

	details {
		padding: 18px 0;
		border-bottom: 1px solid var(--separator);
	}

	summary {
		display: flex;
		justify-content: space-between;
		gap: 16px;
		font-size: 17px;
		font-weight: 500;
		cursor: pointer;
		list-style: none;
	}

	summary::-webkit-details-marker {
		display: none;
	}

	summary::after {
		content: '+';
		color: var(--text-3);
		font-size: 22px;
		line-height: 1;
	}

	details[open] summary::after {
		content: '–';
	}

	details p {
		margin-top: 10px;
		max-width: 680px;
	}

	@media (max-width: 900px) {
		.hero {
			grid-template-columns: minmax(0, 1fr);
			gap: 40px;
		}
		.art {
			display: none;
		}
	}
</style>
