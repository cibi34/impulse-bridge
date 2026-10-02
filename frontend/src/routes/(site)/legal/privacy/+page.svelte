<script lang="ts">
	import { resolve } from '$app/paths';
	import LegalPage from '#lib/components/LegalPage.svelte';
</script>

<LegalPage title="Privacy">
	<p>
		This page explains which personal data IMPULSE Curator processes, why, and what your rights are.
		We do not use analytics, tracking or advertising, and we do not set cookies for those purposes.
	</p>

	<h2>1. Controller</h2>
	<address>
		[Organisation name and legal form]<br />[Address]<br />Email: [privacy contact address]
	</address>
	<p>Data protection officer: [name and contact, if appointed]</p>

	<h2>2. Visiting the website (server logs)</h2>
	<p>
		When you open a page, our server records the request: IP address, date and time, the requested
		address, the HTTP status, the referring page and the browser's user agent. We need this to
		deliver the website and to detect and fix errors and attacks.
	</p>
	<p>
		Legal basis: Art. 6 (1) (f) GDPR (secure and reliable operation). Retention: [number] days, then
		deleted. Hosting: [hosting provider, location], processing on our behalf under Art. 28 GDPR.
	</p>

	<h2>3. Images from the archives</h2>
	<p>
		Previews and media are loaded by your browser directly from the archives that hold them, not
		from our server. To do so, your browser connects to their servers and transmits your IP address
		and browser details to them:
	</p>
	<ul>
		<li>
			Europeana Foundation and the institutions it aggregates (European Union) — [privacy link]
		</li>
		<li>Wikimedia Foundation, Inc. (United States) — [privacy link]</li>
		<li>Smithsonian Institution (United States) — [privacy link]</li>
		<li>Wellcome Collection (United Kingdom) — [privacy link]</li>
	</ul>
	<p>
		Legal basis: [to be confirmed, e.g. Art. 6 (1) (f) GDPR]. Transfers to third countries: [to be
		confirmed, e.g. adequacy decision / EU–US Data Privacy Framework / standard contractual
		clauses]. We send no referrer information with these requests.
	</p>

	<h2>4. Collections you create</h2>
	<p>
		We store each collection's name, description, the selected assets (as published by the archives)
		and, if you enter it, your email address. Collections and their assets are public at their URL
		so that IMPULSE and Unity clients can load them; your email address is never published.
	</p>
	<p>
		Legal basis: Art. 6 (1) (b) GDPR (providing the service you requested). Retention: until you
		delete the collection, or [retention period / deletion policy].
	</p>

	<h2>5. Email and sign-in</h2>
	<p>
		If you add your email address to a collection, we use it to send you sign-in links and, on
		request, the collection's edit link. Sign-in links expire after 15 minutes and work once; a
		sign-in keeps you signed in on that device for 30 days. Emails are sent through [email
		provider], which processes them on our behalf under Art. 28 GDPR.
	</p>
	<p>Legal basis: Art. 6 (1) (b) GDPR.</p>

	<h2>6. Storage in your browser</h2>
	<p>
		Only once you use the respective feature, we store in your browser: your current selection of
		assets, the collections you created or opened on this device (including their edit keys), your
		appearance setting and, after you sign in, a session cookie. Nothing else is stored, and nothing
		is used for tracking. This storage is strictly necessary for the services you requested (§ 25
		(2) No. 2 TDDDG); you can delete it at any time in your browser settings.
	</p>

	<h2>7. Submitting collections</h2>
	<p>
		“Submit to IMPULSE” opens a pre-filled email in your own email program. We do not send that
		email; it is sent by you, from your email account, to the IMPULSE team at [submission address].
	</p>

	<h2>8. Your rights</h2>
	<p>
		You have the right to access (Art. 15), rectification (Art. 16), erasure (Art. 17), restriction
		of processing (Art. 18), data portability (Art. 20) and to object to processing based on Art. 6
		(1) (f) (Art. 21). Contact us at [privacy contact address]. You can also lodge a complaint with
		a supervisory authority, for example [competent authority, e.g. Unabhängiges Datenschutzzentrum
		Saarland].
	</p>

	<p>
		See also the <a href={resolve('legal/terms')}>terms of use</a> and the
		<a href={resolve('legal/imprint')}>imprint</a>.
	</p>
</LegalPage>
