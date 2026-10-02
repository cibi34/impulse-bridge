/**
 * Human-readable names for rights statements. Archives publish rights either
 * as a short name ("CC BY-SA 4.0", Wikimedia) or as a URI (Europeana uses
 * Creative Commons and rightsstatements.org URIs). The value itself is kept
 * as is for IMPULSE; this is only for display.
 */

const RIGHTS_STATEMENTS: Record<string, string> = {
	InC: 'In copyright',
	'InC-EDU': 'In copyright – educational use permitted',
	'InC-NC': 'In copyright – non-commercial use permitted',
	'InC-OW-EU': 'In copyright – EU orphan work',
	'NoC-NC': 'No copyright – non-commercial use only',
	'NoC-OKLR': 'No copyright – other known legal restrictions',
	'NoC-US': 'No copyright – United States',
	CNE: 'Copyright not evaluated',
	UND: 'Copyright undetermined',
	NKC: 'No known copyright'
};

export function rightsLabel(value: string | undefined | null): string | null {
	if (!value) return null;
	const text = value.trim();
	let url: URL;
	try {
		url = new URL(text);
	} catch {
		return text; // already a name
	}
	const parts = url.pathname.split('/').filter(Boolean);
	if (url.hostname.endsWith('creativecommons.org')) {
		if (parts[0] === 'publicdomain') return parts[1] === 'zero' ? 'CC0' : 'Public domain';
		if (parts[0] === 'licenses' && parts[1]) {
			const version = parts[2] ? ` ${parts[2]}` : '';
			return `CC ${parts[1].toUpperCase()}${version}`;
		}
	}
	if (url.hostname.endsWith('rightsstatements.org') && parts[0] === 'vocab' && parts[1]) {
		return RIGHTS_STATEMENTS[parts[1]] ?? parts[1];
	}
	return text;
}

/** The URI of a rights statement, when the value is one. */
export function rightsUrl(value: string | undefined | null): string | null {
	if (!value) return null;
	return /^https?:\/\//i.test(value.trim()) ? value.trim() : null;
}
