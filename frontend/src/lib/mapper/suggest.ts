/**
 * Mapping suggestions: which value of a result fits which Impulse field.
 * Scores a field's name (also through generic wrappers like MediaWiki's
 * `Artist.value`), the value's shape (URL, image, licence, date …) and how
 * many results have it.
 */

import { search } from './evaluate';
import type { FieldDef, FieldKind } from './fields';
import { childPath, isImageUrl, isModelUrl, isUrl, jmesKey, jsonType } from './json';

export interface Leaf {
	path: string;
	/** The key that says what the value is (skipping wrappers like `value`). */
	key: string;
	value: unknown;
	/** An array of strings or numbers (joined for list fields). */
	list: boolean;
	depth: number;
}

/** Keys of list entries that take their meaning from the list (`tags[].name`). */
const ITEM_KEYS = new Set(['name', 'label', 'value', 'term', 'title', 'text', 'preflabel']);

/** Keys that wrap a value without describing it. */
const WRAPPERS = new Set([
	'value',
	'@value',
	'#text',
	'text',
	'def',
	'content',
	'$',
	'und',
	'en',
	'de',
	'fr',
	'it',
	'nl',
	'es',
	'pl',
	'sv'
]);

export function leaves(item: unknown, maxDepth = 5): Leaf[] {
	const out: Leaf[] = [];
	const walk = (value: unknown, path: string, key: string, depth: number) => {
		if (depth > maxDepth) return;
		const type = jsonType(value);
		if (type === 'object') {
			for (const [k, child] of Object.entries(value as object)) {
				walk(child, childPath(path, k), WRAPPERS.has(k.toLowerCase()) && key ? key : k, depth + 1);
			}
		} else if (type === 'array') {
			const values = value as unknown[];
			if (values.length === 0) return;
			if (values.every((v) => ['string', 'number'].includes(jsonType(v)))) {
				out.push({ path, key, value: values, list: true, depth });
			} else if (jsonType(values[0]) === 'object') {
				// [{name: "sea"}, {name: "tower"}] → the list tags[].name
				for (const [k, v] of Object.entries(values[0] as object)) {
					if (!['string', 'number'].includes(jsonType(v))) continue;
					const all = values
						.map((o) => (o as Record<string, unknown>)?.[k])
						.filter((x) => x != null);
					const listKey = ITEM_KEYS.has(k.toLowerCase()) && key ? key : k;
					out.push({
						path: `${path}[].${jmesKey(k)}`,
						key: listKey,
						value: all,
						list: true,
						depth
					});
				}
			}
			walk(values[0], childPath(path, 0), key, depth + 1);
		} else if (type !== 'null' && path) {
			out.push({ path, key, value, list: false, depth });
		}
	};
	walk(item, '', '', 0);
	return out;
}

const NAMES: Record<FieldKind, string[]> = {
	id: [
		'id',
		'identifier',
		'uuid',
		'pageid',
		'key',
		'objectid',
		'objectnumber',
		'guid',
		'recordid',
		'europeanaid',
		'pid'
	],
	title: [
		'title',
		'name',
		'label',
		'caption',
		'heading',
		'dctitle',
		'objecttitle',
		'titlelangaware'
	],
	text: [
		'description',
		'desc',
		'summary',
		'abstract',
		'imagedescription',
		'dcdescription',
		'note',
		'notes',
		'physicaldescription'
	],
	person: [
		'creator',
		'artist',
		'author',
		'maker',
		'photographer',
		'principalmaker',
		'dccreator',
		'agent',
		'artistdisplayname',
		'painter',
		'agentlabel',
		'edmagentlabel'
	],
	date: [
		'date',
		'year',
		'created',
		'datecreated',
		'datetimeoriginal',
		'issued',
		'period',
		'timespan',
		'begin',
		'production',
		'datetime',
		'objectdate'
	],
	institution: [
		'provider',
		'dataprovider',
		'institution',
		'museum',
		'owner',
		'holder',
		'repository',
		'creditline',
		'credit',
		'publisher',
		'department'
	],
	page: [
		'landing',
		'page',
		'link',
		'descriptionurl',
		'isshownat',
		'edmisshownat',
		'permalink',
		'foreignlandingurl',
		'weburl',
		'html',
		'detailurl',
		'objecturl',
		'guid',
		'url'
	],
	media: [
		'url',
		'image',
		'media',
		'file',
		'original',
		'isshownby',
		'edmisshownby',
		'download',
		'full',
		'content',
		'primaryimage',
		'large',
		'fullsize',
		'hires',
		'src',
		'iiifurl'
	],
	preview: [
		'thumb',
		'thumbnail',
		'thumburl',
		'preview',
		'small',
		'edmpreview',
		'icon',
		'webimage',
		'smallimage',
		'primaryimagesmall',
		'previewurl'
	],
	licence: [
		'license',
		'licence',
		'rights',
		'usage',
		'copyright',
		'licenseurl',
		'licenseshortname',
		'rightsstatement',
		'accessrights',
		'usageterms'
	],
	mime: ['mime', 'mimetype', 'mediatype', 'contenttype', 'format', 'encodingformat'],
	list: [
		'subject',
		'subjects',
		'tags',
		'tag',
		'keywords',
		'keyword',
		'topic',
		'topics',
		'concept',
		'concepts',
		'category',
		'categories'
	],
	genre: [
		'type',
		'types',
		'objecttype',
		'objectname',
		'classification',
		'genre',
		'worktype',
		'medium',
		'dctype'
	],
	code: ['language', 'lang', 'locale'],
	scale: ['scale'],
	width: ['width', 'imagewidth', 'pixelwidth', 'w'],
	height: ['height', 'imageheight', 'pixelheight', 'h'],
	bytes: ['size', 'filesize', 'bytes', 'bytesize', 'contentlength', 'length'],
	place: [
		'country',
		'place',
		'location',
		'spatial',
		'coverage',
		'city',
		'region',
		'placelabel',
		'edmplacelabel'
	],
	extent: [
		'format',
		'extent',
		'dimensions',
		'measurements',
		'dctermsextent',
		'dcformat',
		'medium',
		'technique'
	]
};

const squash = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '');
const tokens = (s: string) =>
	s
		.replace(/([a-z0-9])([A-Z])/g, '$1 $2')
		.toLowerCase()
		.split(/[^a-z0-9]+/)
		.filter(Boolean);

function nameScore(kind: FieldKind, key: string): number {
	const names = NAMES[kind];
	const whole = squash(key);
	if (names.includes(whole)) return 6;
	if (tokens(key).some((t) => names.includes(t))) return 4;
	if (names.some((n) => n.length >= 5 && whole.includes(n))) return 2;
	return 0;
}

const LICENCE_LIKE =
	/creativecommons\.org|rightsstatements\.org|^cc[\s-]?(0|by|zero)|public\s*domain|^pd(m)?$/i;
const HTML = /<[a-z][^>]*>/i;

/** How well a value's shape fits a kind; -Infinity rules it out. */
function valueScore(kind: FieldKind, value: unknown, list: boolean): number {
	const text = typeof value === 'string' ? value.trim() : '';
	const url = isUrl(value);
	switch (kind) {
		case 'id':
			if (list) return -Infinity;
			if (typeof value === 'number') return 2;
			return text && text.length <= 200 && !/\s/.test(text) ? 2 : -Infinity;
		case 'title':
			if (list || url) return -Infinity;
			return text.length >= 2 && text.length <= 300 ? 2 : -Infinity;
		case 'text':
			if (list || url) return -Infinity;
			return text.length > 40 ? 3 : text ? 0 : -Infinity;
		case 'person':
		case 'institution':
			if (url && !list) return -Infinity;
			return text || list ? 1 : -Infinity;
		case 'date':
			return /\d{3,4}/.test(list ? String((value as unknown[])[0]) : String(value)) ? 2 : -Infinity;
		case 'page':
			if (!url) return -Infinity;
			return isImageUrl(value) || isModelUrl(value) ? -4 : 3;
		case 'media':
			if (!url) return -Infinity;
			return isModelUrl(value) || isImageUrl(value) ? 4 : 0;
		case 'preview':
			if (!url) return -Infinity;
			return isImageUrl(value)
				? 3 +
						(/thumb|small|preview|\/\d{2,3}px-|[?&](w|width)=\d{2,3}\b|!?\d{2,3},/i.test(text)
							? 2
							: 0)
				: -1;
		case 'licence':
			return LICENCE_LIKE.test(text) ? 5 : text && text.length < 120 ? 0 : -Infinity;
		case 'mime':
			return /^(image|model|video|audio)\/[\w.+-]+$/.test(text) ? 5 : -Infinity;
		case 'list':
			return list ? 2 : text && !url ? 1 : -Infinity;
		case 'genre':
			if (url) return -Infinity;
			return list ? 1 : text && text.length <= 80 ? 1 : -Infinity;
		case 'code':
			return /^[a-z]{2,3}(-[A-Za-z]{2,4})?$/.test(text) ? 3 : -Infinity;
		case 'scale':
			return -Infinity;
		case 'width':
		case 'height':
		case 'bytes': {
			const n = typeof value === 'number' ? value : Number(text);
			return !list && Number.isFinite(n) && n > 0 ? 3 : -Infinity;
		}
		case 'place':
		case 'extent':
			return text && !url && !list ? 1 : list ? 0 : -Infinity;
	}
}

export interface Suggestion {
	expr: string;
	transform?: 'strip_html' | 'file_title';
	sample: unknown;
	score: number;
	/** Share of results with a value at this path (0..1). */
	coverage: number;
}

function coverage(expr: string, items: unknown[]): number {
	if (items.length === 0) return 0;
	let hits = 0;
	for (const item of items) {
		try {
			const v = search(expr, item);
			if (v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0))
				hits++;
		} catch {
			return 0;
		}
	}
	return hits / items.length;
}

function unique(expr: string, items: unknown[]): boolean {
	const seen = new Set<string>();
	for (const item of items) {
		const v = search(expr, item);
		if (v === null || v === undefined) continue;
		const key = JSON.stringify(v);
		if (seen.has(key)) return false;
		seen.add(key);
	}
	return true;
}

/** The best few ways to fill one field from these results. */
export function suggest(field: FieldDef, items: unknown[], limit = 3): Suggestion[] {
	if (items.length === 0 || field.kind === 'scale') return [];
	const sample = items.slice(0, 25);
	const candidates = new Map<string, Suggestion>();
	for (const leaf of leaves(sample[0])) {
		const byName = nameScore(field.kind, leaf.key);
		const byValue = valueScore(field.kind, leaf.value, leaf.list);
		if (byValue === -Infinity) continue;
		if (byName === 0 && byValue < 3) continue;
		let expr = leaf.path;
		let shown = leaf.value;
		if (leaf.list) {
			if (field.kind !== 'list' && field.kind !== 'genre') continue;
			expr = `join(', ', ${leaf.path}[].to_string(@))`;
			shown = (leaf.value as unknown[]).join(', ');
		} else if (field.kind === 'id' && typeof leaf.value === 'number') {
			expr = `to_string(${leaf.path})`;
			shown = String(leaf.value);
		}
		const cover = coverage(expr, sample);
		if (cover === 0) continue;
		let score = byName + byValue + 2 * cover - 0.25 * leaf.depth;
		if (field.kind === 'id') score += unique(expr, sample) ? 3 : -6;
		const suggestion: Suggestion = { expr, sample: shown, score, coverage: cover };
		if (typeof leaf.value === 'string' && HTML.test(leaf.value))
			suggestion.transform = 'strip_html';
		if (
			field.kind === 'title' &&
			typeof leaf.value === 'string' &&
			/^(file|image):/i.test(leaf.value)
		) {
			suggestion.transform = 'file_title';
		}
		const known = candidates.get(expr);
		if (!known || known.score < score) candidates.set(expr, suggestion);
	}
	return [...candidates.values()]
		.filter((s) => s.score >= 4)
		.sort((a, b) => b.score - a.score)
		.slice(0, limit);
}

/** Confident enough to fill in without asking. */
export const AUTO_SCORE = 7;
