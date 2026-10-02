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

export function isModel(contentType: string | undefined): boolean {
	return !!contentType?.startsWith('model/');
}
