/**
 * The mapper edits the source's YAML in place: it changes only the values
 * it is asked to, and keeps comments, key order and quoting everywhere else.
 * New field mappings are written in the one-line form the bundled configs
 * use: `title: { expr: "dcTitle[0]" }`.
 */

import { Document, isMap, isScalar, parseDocument, Scalar, YAMLMap, YAMLSeq } from 'yaml';
import type { FieldMapping, FilterConfig, MappingConfig } from './evaluate';

export type YamlPath = (string | number)[];

export interface SourceYaml {
	collection?: { id?: string; name?: string };
	adapter?: {
		kind?: string;
		base_url?: string;
		auth?: { type?: string; name?: string; value?: string };
		default_query?: Record<string, unknown>;
	};
	search?: {
		path?: string;
		pagination?: Record<string, unknown>;
		query?: { pattern_param?: string; pattern_when_empty?: string; pattern_template?: string };
	};
	mapping?: MappingConfig;
	filter?: FilterConfig;
	asset_detail?: {
		enabled?: boolean;
		path?: string;
		query?: Record<string, unknown>;
		mapping?: { items_path?: string } | null;
	};
}

export interface ParsedConfig {
	doc: Document | null;
	data: SourceYaml;
	error: string | null;
}

export function parseConfig(text: string): ParsedConfig {
	const doc = parseDocument(text);
	if (doc.errors.length > 0) return { doc: null, data: {}, error: doc.errors[0].message };
	const js = doc.toJS();
	const data = js && typeof js === 'object' && !Array.isArray(js) ? (js as SourceYaml) : {};
	return { doc, data, error: null };
}

export function toText(doc: Document): string {
	return doc.toString({ lineWidth: 0 });
}

/** A value as a YAML node: strings double-quoted, collections on one line. */
function toNode(value: unknown): unknown {
	if (typeof value === 'string') {
		const scalar = new Scalar(value);
		scalar.type = Scalar.QUOTE_DOUBLE;
		return scalar;
	}
	if (Array.isArray(value)) {
		const seq = new YAMLSeq();
		seq.flow = true;
		for (const item of value) seq.items.push(toNode(item));
		return seq;
	}
	if (value && typeof value === 'object') {
		const map = new YAMLMap();
		map.flow = true;
		for (const [k, v] of Object.entries(value)) map.set(k, toNode(v));
		return map;
	}
	return value;
}

const blank = (value: unknown) =>
	value === undefined ||
	value === null ||
	value === '' ||
	(typeof value === 'object' && !Array.isArray(value) && Object.keys(value as object).length === 0);

/** Set a value (or remove it, for empty values), keeping an existing
 * scalar's quoting and comments. */
export function setValue(doc: Document, path: YamlPath, value: unknown): void {
	if (blank(value)) {
		if (doc.hasIn(path)) doc.deleteIn(path);
		return;
	}
	const existing = doc.getIn(path, true);
	if (isScalar(existing) && typeof value !== 'object') {
		existing.value = value;
		return;
	}
	doc.setIn(path, toNode(value));
}

const FIELD_KEYS: (keyof FieldMapping)[] = ['expr', 'literal', 'default', 'transform', 'map'];

/** Write one field mapping; null removes the field. */
export function setField(doc: Document, name: string, fm: FieldMapping | null): void {
	const path = ['mapping', 'fields', name];
	const clean: Record<string, unknown> = {};
	for (const key of FIELD_KEYS) if (fm && !blank(fm[key])) clean[key] = fm[key];
	if (Object.keys(clean).length === 0) {
		if (doc.hasIn(path)) doc.deleteIn(path);
		return;
	}
	const existing = doc.getIn(path, true);
	if (isMap(existing)) {
		for (const key of FIELD_KEYS) setValue(doc, [...path, key], clean[key]);
		return;
	}
	doc.setIn(path, toNode(clean));
}

/** Replace a string map (e.g. `default_query`) key by key, so the keys that
 * stay keep their comments. */
export function setStringMap(doc: Document, path: YamlPath, entries: [string, string][]): void {
	const wanted = new Map(entries.filter(([k]) => k.trim() !== '').map(([k, v]) => [k.trim(), v]));
	const existing = doc.getIn(path, true);
	if (isMap(existing)) {
		for (const pair of [...existing.items]) {
			const key = isScalar(pair.key) ? String(pair.key.value) : String(pair.key);
			if (!wanted.has(key)) existing.delete(key);
		}
	}
	if (wanted.size === 0) {
		if (!isMap(existing)) return;
		doc.setIn(path, toNode({}));
		return;
	}
	for (const [key, value] of wanted) setValue(doc, [...path, key], value);
}

/** Replace the `mapping.details` map (label → expression), keeping the
 * transform and comments of labels that stay. */
export function setDetails(doc: Document, entries: [string, string][]): void {
	const path: YamlPath = ['mapping', 'details'];
	const wanted = new Map(
		entries
			.map(([label, expr]) => [label.trim(), expr.trim()] as [string, string])
			.filter(([label, expr]) => label !== '' && expr !== '')
	);
	const existing = doc.getIn(path, true);
	if (isMap(existing)) {
		for (const pair of [...existing.items]) {
			const key = isScalar(pair.key) ? String(pair.key.value) : String(pair.key);
			if (!wanted.has(key)) existing.delete(key);
		}
	}
	if (wanted.size === 0) {
		if (doc.hasIn(path)) doc.deleteIn(path);
		return;
	}
	for (const [label, expr] of wanted) {
		const node = doc.getIn([...path, label], true);
		if (isMap(node)) setValue(doc, [...path, label, 'expr'], expr);
		else doc.setIn([...path, label], toNode({ expr }));
	}
}

/** Apply edits to `text` and return the new text. */
export function edit(text: string, change: (doc: Document) => void): string {
	const { doc } = parseConfig(text);
	if (!doc) return text;
	change(doc);
	return toText(doc);
}
