const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
	['year', 365 * 24 * 3600],
	['month', 30 * 24 * 3600],
	['week', 7 * 24 * 3600],
	['day', 24 * 3600],
	['hour', 3600],
	['minute', 60]
];

/** "just now", "5 minutes ago", "yesterday", … */
export function timeAgo(iso: string, now: Date = new Date()): string {
	const seconds = (new Date(iso).getTime() - now.getTime()) / 1000;
	for (const [unit, size] of UNITS) {
		if (Math.abs(seconds) >= size) return relative.format(Math.round(seconds / size), unit);
	}
	return 'just now';
}

const dateFormat = new Intl.DateTimeFormat('en', { dateStyle: 'medium' });

export function formatDate(iso: string): string {
	return dateFormat.format(new Date(iso));
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
	return `${count} ${count === 1 ? singular : pluralForm}`;
}

/** "Image", "3D model", … for an asset's MIME type. */
export function kindLabel(contentType: string | undefined): string {
	if (!contentType) return 'Asset';
	if (contentType.startsWith('model/')) return '3D model';
	if (contentType.startsWith('image/')) return 'Image';
	if (contentType.startsWith('video/')) return 'Video';
	if (contentType.startsWith('audio/')) return 'Audio';
	return 'Asset';
}

const count = (value: unknown): number | null => {
	const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN;
	return Number.isFinite(n) && n > 0 ? Math.floor(n) : null;
};

/** 8770678 → "8.8 MB" — decimal units, like file managers (and the server). */
export function fileSizeLabel(bytes: unknown): string | null {
	const size = count(bytes);
	if (!size) return null;
	for (const [unit, factor] of [
		['GB', 1e9],
		['MB', 1e6],
		['KB', 1e3]
	] as const) {
		if (size >= factor) return `${(size / factor).toFixed(1).replace(/\.0$/, '')} ${unit}`;
	}
	return `${size} bytes`;
}

/** "3606 × 2894" for pixel sizes, or null. */
export function dimensionsLabel(width: unknown, height: unknown): string | null {
	const w = count(width);
	const h = count(height);
	return w && h ? `${w} × ${h}` : null;
}

/** "10.4 MP" for pixel sizes of a megapixel or more, or null. */
export function megapixelsLabel(width: unknown, height: unknown): string | null {
	const w = count(width);
	const h = count(height);
	if (!w || !h || w * h < 1e6) return null;
	return `${((w * h) / 1e6).toFixed(1).replace(/\.0$/, '')} MP`;
}

export function isModel(contentType: string | undefined): boolean {
	return !!contentType?.startsWith('model/');
}

/** A file-name-safe slug: "Masters of Light" → "masters-of-light". */
export function slugify(text: string): string {
	return text
		.normalize('NFKD')
		.replace(/\p{M}/gu, '')
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		.slice(0, 60);
}
