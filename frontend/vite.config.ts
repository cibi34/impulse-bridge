import { defineConfig } from 'vitest/config';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';

// During `npm run dev`, API calls go to a locally running bridge (uvicorn).
const backend = process.env.CURATOR_BACKEND ?? 'http://127.0.0.1:8080';
const proxied = ['/api', '/collections', '/sources', '/admin/api', '/health'];

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			// Static build served by FastAPI: pages that can be prerendered are,
			// everything else is a single-page app behind the 200.html fallback.
			adapter: adapter({ fallback: '200.html' }),
			csp: {
				mode: 'hash',
				directives: {
					'default-src': ['self'],
					// wasm-unsafe-eval: the 3D viewer's mesh decoders are WebAssembly
					// (it allows WebAssembly only, not eval()).
					'script-src': ['self', 'wasm-unsafe-eval'],
					'style-src': ['self', 'unsafe-inline'],
					// Thumbnails and media are loaded directly from the archives.
					'img-src': ['self', 'https:', 'data:', 'blob:'],
					'media-src': ['self', 'https:'],
					'font-src': ['self'],
					// The 3D viewer fetches a model file from its archive on request,
					// and reads the textures packed into it as blob: URLs.
					'connect-src': ['self', 'https:', 'blob:', 'data:'],
					'worker-src': ['self', 'blob:'],
					'object-src': ['none'],
					'base-uri': ['self'],
					'form-action': ['self']
				}
			}
		})
	],
	server: {
		proxy: Object.fromEntries(proxied.map((path) => [path, { target: backend }]))
	},
	test: {
		expect: { requireAssertions: true },
		projects: [
			{
				extends: './vite.config.ts',
				test: {
					name: 'unit',
					environment: 'node',
					include: ['src/**/*.{test,spec}.{js,ts}'],
					exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
				}
			}
		]
	}
});
