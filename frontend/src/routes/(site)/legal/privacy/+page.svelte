<script lang="ts">
	import { resolve } from '$app/paths';
	import Email from '#lib/components/Email.svelte';
	import LegalPage from '#lib/components/LegalPage.svelte';
	import { known, legalDraft, provider } from '#lib/legal.js';

	const address = known(provider.street) && known(provider.city);
</script>

<LegalPage title="Privacy" updated={provider.updated} draft={legalDraft}>
	<p>
		This notice explains what happens to personal data when you use IMPULSE Curator at
		{provider.siteUrl}. In short: no tracking, no advertising, no cookies you have to consent to.
		The site processes what it needs to show you search results from the archives and to keep the
		collections you create.
	</p>

	<h2>1. Controller</h2>
	<address>
		{provider.name}<br />
		{#if address}{provider.street}, {provider.city}, {provider.country}<br />{/if}
		{#if known(provider.email)}
			Email: <Email address={provider.email} />
		{:else}
			Contact: see the <a href={resolve('legal/imprint')}>imprint</a>
		{/if}
	</address>

	<h2>2. Hosting and server logs</h2>
	<p>
		The Curator runs on a virtual server provided by {provider.hosting.provider}, located in
		{provider.hosting.location}. The hosting provider processes data on our behalf (Art. 28 GDPR).
	</p>
	<p>
		Whenever your browser requests a page, a search or a file from our server, the server records
		your IP address, the time, the requested address, the response status and your browser's
		identification. We use these logs to run the service securely and to find errors. Legal basis:
		our legitimate interest in a secure, working service (Art. 6 (1) (f) GDPR). The logs are kept in
		a rotating buffer of at most 30 MB per service; the oldest entries are overwritten as new ones
		arrive, typically within days.
	</p>

	<h2>3. Searching the archives</h2>
	<p>
		When you search, our server sends your search terms to the archives' interfaces (Europeana,
		Wikimedia Commons, Heidelberg University Library and any archive added later) and passes the
		results on to you. The archives see our server, not your IP address, for these searches.
	</p>
	<p>
		Preview images and the full-size files, however, load directly from the archives' servers into
		your browser. The archive then receives your IP address and your browser's identification, but
		no cookies and no information about the page you came from (we load images with
		<code>crossorigin="anonymous"</code> and <code>referrerpolicy="no-referrer"</code>). This
		happens only for results that are actually shown to you.
	</p>
	<ul>
		<li>Europeana Foundation, The Hague, Netherlands (api.europeana.eu)</li>
		<li>Heidelberg University Library, Germany (digi.ub.uni-heidelberg.de)</li>
		<li>Statens Museum for Kunst, Copenhagen, Denmark (iip.smk.dk)</li>
		<li>
			Wikimedia Foundation, San Francisco, USA (upload.wikimedia.org, thumb.wikimedia.org) — a
			transfer to a country for which the EU has not issued an adequacy decision covering this
			recipient. It happens only when a Wikimedia Commons result is shown to you; you can avoid it
			by choosing another archive in the source list.
		</li>
	</ul>
	<p>
		Legal basis: our legitimate interest in showing you the results you asked for (Art. 6 (1) (f)
		GDPR). The archives are responsible for the works, descriptions and rights statements they
		provide; the Curator links to them.
	</p>

	<h2>4. Collections you create</h2>
	<p>
		A collection consists of the name and description you write, the assets you selected (with a
		copy of their descriptions from the archive) and the times it was created and changed. It is
		public at its own address: anyone who has the link can view it, and IMPULSE's software loads it
		from there. Only someone with the edit link can change it. We keep a collection until you delete
		it or an administrator removes it. Legal basis: providing the service you asked for (Art. 6 (1)
		(b) GDPR).
	</p>
	<p>
		You can give an email address with a collection. It is optional, never shown publicly, and used
		only for the sign-in and edit-link emails described below.
	</p>

	<h2>5. Email and sign-in</h2>
	<p>
		If you enter your email address, we send you sign-in links (valid for 15 minutes, usable once)
		the edit link of a collection you create (and again on request). These emails are delivered
		through
		{known(provider.emailProvider) ? provider.emailProvider : 'our email service provider'}, which
		processes them on our behalf (Art. 28 GDPR).
	</p>
	<p>
		After you sign in, a session cookie keeps you signed in on that device for 30 days. The cookie
		holds only a random identifier (<code>HttpOnly</code>); the session itself is stored on our
		server together with your email address and deleted when it expires or you sign out. This cookie
		is strictly necessary for the sign-in you requested, so no consent is needed (§ 25 (2) No. 2
		TDDDG). Legal basis: Art. 6 (1) (b) GDPR.
	</p>

	<h2>6. Storage in your browser</h2>
	<p>
		The site keeps a few things in your browser's local storage: the assets you have currently
		selected, the list of collections you created or opened on this device together with their edit
		keys, and your appearance setting (light, dark or system). All of this is written only as a
		result of your own actions and read only by this site to show you your own things; nothing is
		used for analytics or tracking. You can delete it at any time through your browser's settings.
		Strictly necessary under § 25 (2) No. 2 TDDDG — no consent required.
	</p>

	<h2>7. Submitting a collection to IMPULSE</h2>
	<p>
		"Submit to IMPULSE" opens your own email program with a pre-filled message to the IMPULSE team.
		The Curator does not send that email and does not record it.
	</p>

	<h2>8. Reports</h2>
	<p>
		If you <a href={resolve('report')}>report a collection</a>, we process your report and the
		contact details you give to handle it and to tell you the outcome. Legal basis: our legal
		obligations under the Digital Services Act (Art. 6 (1) (c) GDPR).
	</p>

	<h2>9. What we don't do</h2>
	<p>
		No analytics, no tracking, no advertising, no third-party scripts, fonts or embeds. The fonts
		are served from this site, and the site's content security policy allows scripts and connections
		only to this site itself.
	</p>

	<h2>10. Your rights</h2>
	<p>
		You have the right to access the personal data we hold about you, to have it corrected or
		erased, to restrict its processing, to receive it in a portable format and to object to
		processing based on our legitimate interests (Art. 15–21 GDPR). To exercise these rights,
		{#if known(provider.email)}
			write to <Email address={provider.email} />.
		{:else}
			contact us through the <a href={resolve('legal/imprint')}>imprint</a>.
		{/if}
		You also have the right to lodge a complaint with a data protection supervisory authority, for example
		the one at your place of residence.
	</p>

	<h2>11. Changes</h2>
	<p>
		We update this notice when the service changes, for example when an archive is added. The date
		at the top shows the current version.
	</p>

	<p>
		See also the <a href={resolve('legal/terms')}>terms of use</a> and the
		<a href={resolve('legal/imprint')}>imprint</a>.
	</p>
</LegalPage>
