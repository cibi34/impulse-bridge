<script lang="ts">
	import LegalPage from '#lib/components/LegalPage.svelte';
</script>

<LegalPage title="Accessibility">
	<p>
		We want IMPULSE Curator to be usable by everyone. It is designed and built to meet the Web
		Content Accessibility Guidelines (WCAG) 2.2 at level AA. This statement applies to [website
		address].
	</p>

	<h2>What we do</h2>
	<ul>
		<li>
			All functions work with the keyboard, with visible focus, including reordering assets (arrow
			keys on the handle).
		</li>
		<li>
			Text meets a contrast of at least 4.5:1 in dark and light appearance; the layout adapts to
			zoom and small screens.
		</li>
		<li>
			Pages use landmarks, headings and labelled controls, and announce changes such as search
			results and saved edits to screen readers.
		</li>
		<li>Animations are reduced when your system asks for reduced motion.</li>
	</ul>

	<h2>Status and known limitations</h2>
	<p>[Conformance status after testing: fully / partially / not compliant.]</p>
	<ul>
		<li>
			Images and metadata come from third-party archives. Many images have no text description; we
			show their titles and creators instead.
		</li>
		<li>[Further limitations found in testing.]</li>
	</ul>

	<h2>Feedback</h2>
	<p>
		If you find a barrier, please tell us: [contact email address]. We will get back to you within
		[number] weeks.
	</p>

	<h2>Enforcement</h2>
	<p>[Enforcement procedure / arbitration body, depending on the applicable law.]</p>

	<p class="footnote">This statement was prepared on [date].</p>
</LegalPage>
