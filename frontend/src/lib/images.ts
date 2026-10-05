/**
 * The one place that decides where preview images are loaded from.
 *
 * Previews come straight from the archives (Europeana, Wikimedia, …), as
 * decided for the MVP. Should a thumbnail proxy ever be needed (e.g. for
 * privacy reasons), it only has to be wired in here.
 *
 * Every <img> that shows such a URL first tries crossorigin="anonymous":
 * the browser then sends no cookies to the archive and ignores the cookies
 * it sets (Wikimedia sets an identifier cookie on every image), so the site
 * needs no cookie consent. Most archives allow this (Access-Control-Allow-
 * Origin: *). An image server without CORS headers (Cleveland, the Met)
 * refuses anonymous requests, and AssetThumb retries plainly — the privacy
 * notice says so.
 */
export function previewSrc(url: string | null | undefined): string | null {
	if (!url) return null;
	try {
		const parsed = new URL(url, globalThis.location?.origin ?? 'http://localhost');
		return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null;
	} catch {
		return null;
	}
}
