/**
 * Working with an archive's JSON: JMESPath paths for keys, short previews,
 * and finding where the list of results is.
 */

export type JsonType = 'object' | 'array' | 'string' | 'number' | 'boolean' | 'null';

export function jsonType(value: unknown): JsonType {
	if (value === null || value === undefined) return 'null';
	if (Array.isArray(value)) return 'array';
	return typeof value === 'object' ? 'object' : (typeof value as JsonType);
}

/** A key as JMESPath needs it: bare when it is an identifier, else quoted. */
export function jmesKey(key: string): string {
	return /^[A-Za-z_][A-Za-z0-9_]*$/.test(key) ? key : JSON.stringify(key);
}

export function childPath(parent: string, key: string | number): string {
	if (typeof key === 'number') return `${parent}[${key}]`;
	return parent ? `${parent}.${jmesKey(key)}` : jmesKey(key);
}

export function isObject(value: unknown): value is Record<string, unknown> {
	return jsonType(value) === 'object';
}

export const isUrl = (value: unknown): value is string =>
	typeof value === 'string' && /^https?:\/\/\S+$/i.test(value.trim());

export const isImageUrl = (value: unknown): boolean =>
	isUrl(value) &&
	!/\/wiki\//i.test(value) && // a MediaWiki page about a file, not the file
	(/\.(jpe?g|png|gif|webp|avif|tiff?|bmp|jp2)(\?|#|$)/i.test(value) ||
		/\/(thumb(nail)?s?|images?|iiif)\//i.test(value) ||
		/\/full\/[^/]+\/\d+\/(default|color|gray)\.(jpg|png|webp)/i.test(value) ||
		/[?&](w|width|size)=\d+/i.test(value));

export const isModelUrl = (value: unknown): boolean =>
	isUrl(value) && /\.(glb|gltf|obj|fbx|stl|ply|usdz)(\?|#|$)/i.test(value);

/** A one-line preview of any JSON value. */
export function preview(value: unknown, max = 120): string {
	switch (jsonType(value)) {
		case 'null':
			return 'null';
		case 'array': {
			const n = (value as unknown[]).length;
			return `[${n} ${n === 1 ? 'item' : 'items'}]`;
		}
		case 'object': {
			const n = Object.keys(value as object).length;
			return `{${n} ${n === 1 ? 'field' : 'fields'}}`;
		}
		case 'string': {
			const text = (value as string).replace(/\s+/g, ' ').trim();
			return text.length > max ? `${text.slice(0, max - 1)}…` : text;
		}
		default:
			return String(value);
	}
}

export interface ListCandidate {
	/** The `items_path` to use. */
	path: string;
	/** Where it is, for display. */
	label: string;
	count: number;
	kind: 'array' | 'map';
}

function similarKeys(objects: Record<string, unknown>[]): boolean {
	const [first, ...rest] = objects;
	const keys = new Set(Object.keys(first));
	if (keys.size === 0) return false;
	return rest.every((o) => {
		const shared = Object.keys(o).filter((k) => keys.has(k)).length;
		return shared / Math.max(keys.size, Object.keys(o).length) >= 0.5;
	});
}

/**
 * Places in a response that look like the list of results: arrays of
 * objects, and objects whose values are objects of one shape (MediaWiki's
 * `query.pages`, keyed by id). Biggest first.
 */
export function findLists(raw: unknown, maxDepth = 6): ListCandidate[] {
	const found: (ListCandidate & { depth: number })[] = [];
	const walk = (value: unknown, path: string, depth: number) => {
		if (depth > maxDepth) return;
		if (Array.isArray(value)) {
			const objects = value.filter(isObject);
			if (objects.length > 0 && objects.length >= value.length / 2) {
				found.push({
					path,
					label: path || 'the response itself',
					count: objects.length,
					kind: 'array',
					depth
				});
			}
			return; // lists inside a result are its fields, not results
		}
		if (!isObject(value)) return;
		const values = Object.values(value);
		if (path && values.length >= 2 && values.every(isObject) && similarKeys(values)) {
			found.push({
				path: `values(${path} || \`{}\`)`,
				label: `${path} (one entry per key)`,
				count: values.length,
				kind: 'map',
				depth
			});
			return;
		}
		for (const [key, child] of Object.entries(value)) walk(child, childPath(path, key), depth + 1);
	};
	walk(raw, '', 0);
	return found
		.sort((a, b) => b.count - a.count || a.depth - b.depth)
		.map(({ path, label, count, kind }) => ({ path, label, count, kind }));
}
