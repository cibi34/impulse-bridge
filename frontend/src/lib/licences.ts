/**
 * Licences and credits. The server reads every asset's rights statement
 * (app/licensing.py); this module turns that reading into text: what a
 * licence asks of the user, a summary per collection, and the credits list
 * (title, author, source, licence) that attribution licences require.
 */

import type { Asset, CollectionItem, Licence, LicenceCondition } from '#lib/api/index.js';

/** What each condition asks of whoever uses the work. */
export const CONDITION_TEXT: Record<LicenceCondition, string> = {
	by: 'Credit the creator and the licence',
	sa: 'Share adaptations under the same licence',
	nc: 'Non-commercial use only',
	nd: 'No adaptations'
};

export function conditionsText(licence: Licence | null | undefined): string {
	if (!licence) return '';
	if (licence.code === 'other') return 'Rights unclear or not openly licensed';
	if (licence.conditions.length === 0) return 'No conditions — free to use';
	return licence.conditions.map((c) => CONDITION_TEXT[c]).join(' · ');
}

/** The licence to show: the server's reading, else the raw rights value. */
export function licenceLabel(asset: Pick<Asset, 'rights' | 'licence'>): string | null {
	if (asset.licence) return asset.licence.label;
	return typeof asset.rights === 'string' && asset.rights.trim() ? asset.rights.trim() : null;
}

export interface LicenceCount {
	label: string;
	url: string | null;
	conditions: LicenceCondition[];
	count: number;
}

/** How many assets carry each licence, most frequent first. */
export function summarize(licences: Licence[]): LicenceCount[] {
	const counts: Record<string, LicenceCount> = {};
	for (const licence of licences) {
		counts[licence.label] ??= {
			label: licence.label,
			url: licence.url,
			conditions: licence.conditions,
			count: 0
		};
		counts[licence.label].count += 1;
	}
	return Object.values(counts).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

/** "12 × Public domain, 3 × CC BY 4.0" */
export function summaryLine(licences: Licence[]): string {
	return summarize(licences)
		.map((s) => `${s.count} × ${s.label}`)
		.join(', ');
}

const text = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');
const isUrl = (value: string): boolean => /^https?:\/\//i.test(value);

/** One credit in the TASL form: Title, Author, Source, Licence. */
export function creditLine(item: CollectionItem, archive: string): string {
	const asset = item.asset;
	const title = text(asset.title) || 'Untitled';
	const parts = [`“${title}”`];
	if (text(asset.creator)) parts[0] += ` by ${text(asset.creator)}`;
	const institution = text(asset.contributor);
	// "Wikimedia Commons, via Wikimedia Commons Images" says the same twice.
	const via =
		institution && archive.toLowerCase().includes(institution.toLowerCase()) ? '' : archive;
	const origin = [institution, via].filter(Boolean).join(', via ');
	if (origin) parts.push(origin);
	const link = text(asset.identifier);
	if (isUrl(link)) parts.push(link);
	const licence = item.licence.url
		? `${item.licence.label} (${item.licence.url})`
		: item.licence.label;
	parts.push(`Licence: ${licence}`);
	return parts.join(' — ');
}

export function creditsText(
	name: string,
	items: CollectionItem[],
	archiveName: (source: string) => string
): string {
	const lines = items.map((item) => creditLine(item, archiveName(item.source)));
	return [`Credits for “${name}”`, '', ...lines].join('\n');
}

const CSV_COLUMNS = [
	'Title',
	'Creator',
	'Institution',
	'Date',
	'Archive',
	'Link',
	'Licence',
	'Licence URL',
	'Conditions'
];

function csvField(value: string): string {
	return /[",\r\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
}

/** RFC 4180 CSV of the credits, one row per asset. */
export function creditsCsv(
	items: CollectionItem[],
	archiveName: (source: string) => string
): string {
	const rows = items.map((item) => [
		text(item.asset.title) || 'Untitled',
		text(item.asset.creator),
		text(item.asset.contributor),
		text(item.asset.date),
		archiveName(item.source),
		isUrl(text(item.asset.identifier)) ? text(item.asset.identifier) : '',
		item.licence.label,
		item.licence.url ?? '',
		conditionsText(item.licence)
	]);
	return [CSV_COLUMNS, ...rows].map((row) => row.map(csvField).join(',')).join('\r\n') + '\r\n';
}
