import type { ImpulseCollection } from '#lib/api/index.js';

/** Mail clients and browsers cut long mailto: URLs (some at ~2000 characters). */
export const MAILTO_LIMIT = 1800;

export interface Submission {
	to: string;
	subject: string;
	body: string;
	/** A mailto: link; null when the text is too long to fit into one. */
	mailto: string | null;
}

/**
 * The email that hands collections to the IMPULSE team. It carries each
 * collection's entry exactly as the platform's collection list expects it
 * (id, uri, name, description, organization, owner_id, published), and the
 * licences of its assets by collection id ("12 × Public domain, …").
 */
export function buildSubmission(
	to: string,
	collections: ImpulseCollection[],
	note = '',
	licences: Record<string, string> = {}
): Submission {
	const names = collections.map((c) => c.name);
	const subject =
		collections.length === 1
			? `New collection for IMPULSE: ${names[0]}`
			: `${collections.length} new collections for IMPULSE`;
	const lines = [
		'Hello IMPULSE team,',
		'',
		collections.length === 1
			? 'please add this collection to the IMPULSE platform:'
			: 'please add these collections to the IMPULSE platform:',
		'',
		...collections.map(
			(c) => `• ${c.name}\n  ${c.uri}` + (licences[c.id] ? `\n  Licences: ${licences[c.id]}` : '')
		),
		''
	];
	if (note.trim()) lines.push(note.trim(), '');
	lines.push(
		'Collection entries:',
		JSON.stringify(collections.length === 1 ? collections[0] : collections, null, 2),
		'',
		'Sent with IMPULSE Curator'
	);
	const body = lines.join('\n');
	const mailto = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
	return { to, subject, body, mailto: mailto.length <= MAILTO_LIMIT ? mailto : null };
}

/** A short mailto: for long submissions; the full text goes to the clipboard. */
export function shortMailto(submission: Submission): string {
	const body = 'The collection details are in my clipboard — pasting them below:\n\n';
	return `mailto:${encodeURIComponent(submission.to)}?subject=${encodeURIComponent(submission.subject)}&body=${encodeURIComponent(body)}`;
}
