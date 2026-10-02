<script lang="ts">
	import { resolve } from '$app/paths';
	import LegalPage from '#lib/components/LegalPage.svelte';
</script>

<LegalPage title="Terms of use">
	<h2>1. The service</h2>
	<p>
		Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut
		labore et dolore magna aliqua.
	</p>

	<h2>2. Your collections</h2>
	<ul>
		<li>Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.</li>
		<li>Nisi ut aliquip ex ea commodo consequat.</li>
		<li>Duis aute irure dolor in reprehenderit in voluptate velit esse.</li>
	</ul>

	<h2>3. Rights in the assets</h2>
	<p>
		Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim
		id est laborum.
	</p>

	<h2>4. Moderation</h2>
	<p>
		Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque
		laudantium, totam rem aperiam.
	</p>

	<h2>5. Reporting content</h2>
	<p>
		Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit:
		<a href={resolve('report')}>Report content</a>.
	</p>

	<h2>6. Liability</h2>
	<p>
		Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit.
	</p>

	<h2>7. Changes and applicable law</h2>
	<p>
		Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae
		consequatur.
	</p>
</LegalPage>
