<script lang="ts">
	import { resolve } from '$app/paths';
	import LegalPage from '#lib/components/LegalPage.svelte';
</script>

<LegalPage title="Privacy">
	<p>
		Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut
		labore et dolore magna aliqua.
	</p>

	<h2>1. Controller</h2>
	<address>
		Lorem Ipsum gGmbH<br />Dolor Street 1, 12345 Sit Amet<br />Email: lorem@example.org
	</address>

	<h2>2. Visiting the website</h2>
	<p>
		Lorem ipsum dolor sit amet, consectetur adipiscing elit. Ut enim ad minim veniam, quis nostrud
		exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
	</p>

	<h2>3. Images from the archives</h2>
	<p>
		Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
		pariatur. Excepteur sint occaecat cupidatat non proident.
	</p>

	<h2>4. Collections you create</h2>
	<p>
		Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque
		laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis.
	</p>

	<h2>5. Email and sign-in</h2>
	<p>
		Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia
		consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt.
	</p>

	<h2>6. Storage in your browser</h2>
	<p>
		Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit,
		sed quia non numquam eius modi tempora incidunt.
	</p>

	<h2>7. Submitting collections</h2>
	<p>
		Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi
		ut aliquid ex ea commodi consequatur.
	</p>

	<h2>8. Your rights</h2>
	<p>
		Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae
		consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur.
	</p>

	<p>
		See also the <a href={resolve('legal/terms')}>terms of use</a> and the
		<a href={resolve('legal/imprint')}>imprint</a>.
	</p>
</LegalPage>
