/**
 * The one place that decides where preview images are loaded from.
 *
 * Previews come straight from the archives (Europeana, Wikimedia, …), as
 * decided for the MVP. Should a thumbnail proxy ever be needed (e.g. for
 * privacy reasons), it only has to be wired in here.
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
