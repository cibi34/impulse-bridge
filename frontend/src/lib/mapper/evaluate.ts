/**
 * The mapping engine of app/transform/engine.py, in the browser, so the
 * mapper can show results instantly. Keep the two in step: same JMESPath,
 * same transforms (app/transform/helpers.py), same order of default → map →
 * transform, same filter rules.
 */

import jmespath from 'jmespath';

export interface FieldMapping {
	expr?: string | null;
	literal?: unknown;
	default?: unknown;
	transform?: string | null;
	map?: Record<string, unknown> | null;
}

export interface MappingConfig {
	items_path?: string | null;
	fields?: Record<string, FieldMapping | null> | null;
}

export interface FilterConfig {
	allowed_content_types?: string[] | null;
	drop_if_missing?: string[] | null;
}

/** The JMESPath syntax error of an expression, or null. */
export function syntaxError(expr: string): string | null {
	try {
		jmespath.compile(expr);
		return null;
	} catch (e) {
		return e instanceof Error ? e.message : String(e);
	}
}

export function search(expr: string, data: unknown): unknown {
	return jmespath.search(data, expr);
}

// ---- transforms (app/transform/helpers.py) ----

export function slugify(value: string): string {
	if (!value) return 'untitled';
	const slug = value
		.toLowerCase()
		.trim()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '');
	return slug || 'untitled';
}

const BASE32 = 'abcdefghijklmnopqrstuvwxyz234567';

export function base32(value: string): string {
	if (!value) return 'untitled';
	let bits = 0;
	let buffer = 0;
	let out = '';
	for (const byte of new TextEncoder().encode(value)) {
		buffer = (buffer << 8) | byte;
		bits += 8;
		while (bits >= 5) {
			out += BASE32[(buffer >>> (bits - 5)) & 31];
			bits -= 5;
		}
	}
	if (bits > 0) out += BASE32[(buffer << (5 - bits)) & 31];
	return out;
}

export function stripHtml(value: string): string {
	return value ? value.replace(/<[^>]+>/g, '').trim() : value;
}

const FILE_PREFIX = /^(file|image|datei):\s*/i;
const FILE_EXTENSION =
	/\.(jpe?g|png|gif|tiff?|webp|svg|bmp|jp2|pdf|djvu|glb|gltf|obj|stl|ply|fbx|usdz|ogg|ogv|oga|webm|mp3|mp4|wav|flac|midi?)$/i;

export function fileTitle(value: string): string {
	if (!value) return value;
	const title = value
		.trim()
		.replace(FILE_PREFIX, '')
		.replace(FILE_EXTENSION, '')
		.replaceAll('_', ' ');
	return title.split(/\s+/).filter(Boolean).join(' ') || value;
}

const TRANSFORM_FNS: Record<string, (value: string) => string> = {
	slugify,
	base32,
	strip_html: stripHtml,
	file_title: fileTitle,
	lower: (s) => s.toLowerCase(),
	upper: (s) => s.toUpperCase()
};

// ---- evaluation (app/transform/engine.py) ----

function isEmpty(value: unknown): boolean {
	if (value === null || value === undefined || value === '') return true;
	if (Array.isArray(value)) return value.length === 0;
	return typeof value === 'object' && Object.keys(value as object).length === 0;
}

/** Python truthiness, as `if not asset.get(field)` sees it. */
export function pyFalsy(value: unknown): boolean {
	return isEmpty(value) || value === 0 || value === false;
}

/** One field's value for one raw item. Throws on a JMESPath error. */
export function evaluateField(item: unknown, fm: FieldMapping): unknown {
	let value: unknown = null;
	if (fm.literal !== null && fm.literal !== undefined) value = fm.literal;
	else if (fm.expr) value = search(fm.expr, item);
	if (value === undefined) value = null;
	if (isEmpty(value) && fm.default !== null && fm.default !== undefined) value = fm.default;
	if (fm.map && typeof value === 'string' && Object.hasOwn(fm.map, value)) value = fm.map[value];
	if (fm.transform && typeof value === 'string') {
		const fn = TRANSFORM_FNS[fm.transform];
		if (fn) value = fn(value);
	}
	return value;
}

/** The raw items `items_path` points at, as extract_items() resolves them. */
export function extractItems(raw: unknown, itemsPath: string | null | undefined): unknown[] {
	if (!itemsPath) return Array.isArray(raw) ? raw : [raw];
	const result = search(itemsPath, raw);
	if (result === null || result === undefined) return [];
	if (Array.isArray(result))
		return result.filter((r) => r && typeof r === 'object' && !Array.isArray(r));
	if (typeof result === 'object') return [result];
	return [];
}

export interface Mapped {
	asset: Record<string, unknown>;
	/** Why the filter drops it, or null. */
	dropped: string | null;
	/** Fields whose expression failed (the server drops such items). */
	errors: Record<string, string>;
}

export function mapItem(raw: unknown, mapping: MappingConfig, filter: FilterConfig = {}): Mapped {
	const asset: Record<string, unknown> = {};
	const errors: Record<string, string> = {};
	for (const [name, fm] of Object.entries(mapping.fields ?? {})) {
		if (!fm) continue;
		try {
			const value = evaluateField(raw, fm);
			if (value !== null && value !== undefined) asset[name] = value;
		} catch (e) {
			errors[name] = e instanceof Error ? e.message : String(e);
		}
	}
	let dropped: string | null = null;
	if (Object.keys(errors).length > 0) dropped = 'A field expression fails';
	for (const required of filter.drop_if_missing ?? []) {
		if (!dropped && pyFalsy(asset[required])) dropped = `No ${required}`;
	}
	const allowed = filter.allowed_content_types ?? [];
	if (!dropped && allowed.length > 0 && !allowed.includes(asset.contentType as string)) {
		dropped = `Content type ${String(asset.contentType ?? 'missing')} is not allowed`;
	}
	return { asset, dropped, errors };
}
