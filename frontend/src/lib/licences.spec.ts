import { describe, expect, it } from 'vitest';
import type { CollectionItem, Licence } from '#lib/api/index.js';
import { conditionsText, creditLine, creditsCsv, licenceLabel, summaryLine } from './licences';

const licence = (label: string, conditions: Licence['conditions'] = [], code = 'by'): Licence => ({
	code,
	label,
	url: conditions.length ? `https://creativecommons.org/licenses/${code}/4.0/` : null,
	conditions,
	allowed: true
});

const item = (title: string, l: Licence, extra: Record<string, string> = {}): CollectionItem => ({
	asset_id: title.toLowerCase(),
	source: 'wikimedia',
	source_asset_id: '1',
	published: true,
	licence: l,
	asset: { assetID: title.toLowerCase(), title, ...extra },
	added_at: '',
	refreshed_at: ''
});

describe('conditionsText', () => {
	it('says what a licence asks for', () => {
		expect(conditionsText(licence('Public domain', [], 'pd'))).toBe('No conditions — free to use');
		expect(conditionsText(licence('CC BY-SA 4.0', ['by', 'sa'], 'by-sa'))).toBe(
			'Credit the creator and the licence · Share adaptations under the same licence'
		);
		expect(conditionsText(licence('In copyright', [], 'other'))).toBe(
			'Rights unclear or not openly licensed'
		);
	});
});

describe('licenceLabel', () => {
	it("prefers the server's reading and falls back to the raw value", () => {
		expect(licenceLabel({ rights: 'http://x', licence: licence('CC BY 4.0', ['by']) })).toBe(
			'CC BY 4.0'
		);
		expect(licenceLabel({ rights: ' CC0 ' })).toBe('CC0');
		expect(licenceLabel({})).toBeNull();
	});
});

describe('summaryLine', () => {
	it('counts licences, most frequent first', () => {
		const pd = licence('Public domain', [], 'pd');
		const by = licence('CC BY 4.0', ['by']);
		expect(summaryLine([by, pd, pd])).toBe('2 × Public domain, 1 × CC BY 4.0');
	});
});

describe('credits', () => {
	const hare = item('Young Hare', licence('CC BY 4.0', ['by']), {
		creator: 'Albrecht Dürer',
		contributor: 'Albertina',
		identifier: 'https://commons.wikimedia.org/wiki/File:Hare.jpg'
	});

	it('writes title, author, source and licence', () => {
		expect(creditLine(hare, 'Wikimedia Commons')).toBe(
			'“Young Hare” by Albrecht Dürer — Albertina, via Wikimedia Commons — ' +
				'https://commons.wikimedia.org/wiki/File:Hare.jpg — ' +
				'Licence: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)'
		);
	});

	it('names the archive only when it adds something', () => {
		const commons = item('Lighthouse', licence('CC0 1.0', [], 'cc0'), {
			contributor: 'Wikimedia Commons'
		});
		expect(creditLine(commons, 'Wikimedia Commons Images')).toBe(
			'“Lighthouse” — Wikimedia Commons — Licence: CC0 1.0'
		);
	});

	it('exports CSV with quoting', () => {
		const tricky = item('Map, "old"', licence('Public domain', [], 'pd'));
		const csv = creditsCsv([hare, tricky], () => 'Wikimedia Commons');
		const lines = csv.split('\r\n');
		expect(lines[0]).toBe(
			'Title,Creator,Institution,Date,Archive,Link,Licence,Licence URL,Conditions'
		);
		expect(lines[2]).toBe(
			'"Map, ""old""",,,,Wikimedia Commons,,Public domain,,No conditions — free to use'
		);
		expect(lines).toHaveLength(4); // header, two rows, trailing newline
	});
});
