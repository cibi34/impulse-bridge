import { describe, expect, it } from 'vitest';
import { edit, parseConfig, setField, setStringMap, setValue } from './config';
import {
	base32,
	evaluateField,
	extractItems,
	fileTitle,
	mapItem,
	slugify,
	syntaxError
} from './evaluate';
import { FIELDS } from './fields';
import { childPath, findLists, jmesKey } from './json';
import { leaves, suggest } from './suggest';

const field = (name: string) => FIELDS.find((f) => f.name === name)!;

// Shapes as the archives send them (shortened).
const WIKIMEDIA = {
	batchcomplete: '',
	continue: { gsroffset: 2 },
	query: {
		pages: {
			'101': {
				pageid: 101,
				title: 'File:Flottsund lighthouse.jpg',
				imageinfo: [
					{
						thumburl: 'https://upload.wikimedia.org/thumb/a/ab/Flottsund.jpg/1024px-Flottsund.jpg',
						thumbwidth: 1024,
						url: 'https://upload.wikimedia.org/a/ab/Flottsund.jpg',
						width: 3606,
						height: 2894,
						size: 8770678,
						descriptionurl: 'https://commons.wikimedia.org/wiki/File:Flottsund_lighthouse.jpg',
						mime: 'image/jpeg',
						extmetadata: {
							Artist: { value: '<a href="//x">Jane Doe</a>' },
							LicenseShortName: { value: 'CC BY-SA 4.0' },
							DateTimeOriginal: { value: '2015-08-28' }
						}
					}
				]
			},
			'102': {
				pageid: 102,
				title: 'File:Kõpu tuletorn.jpg',
				imageinfo: [
					{
						thumburl: 'https://upload.wikimedia.org/thumb/c/cd/Kopu.jpg/1024px-Kopu.jpg',
						thumbwidth: 1024,
						url: 'https://upload.wikimedia.org/c/cd/Kopu.jpg',
						width: 4000,
						height: 3000,
						size: 5120000,
						descriptionurl: 'https://commons.wikimedia.org/wiki/File:K%C3%B5pu_tuletorn.jpg',
						mime: 'image/jpeg',
						extmetadata: {
							Artist: { value: 'Ivar Leidus' },
							LicenseShortName: { value: 'CC0' },
							DateTimeOriginal: { value: '2019' }
						}
					}
				]
			}
		}
	}
};

const OPENVERSE = {
	result_count: 2,
	results: [
		{
			id: '4bc43a04-ef46-4544-a0c1-63c63f56e276',
			title: 'Lighthouse at dusk',
			creator: 'Ann Smith',
			license: 'by',
			license_url: 'https://creativecommons.org/licenses/by/2.0/',
			url: 'https://live.staticflickr.com/1/abc_b.jpg',
			thumbnail: 'https://api.openverse.org/v1/images/4bc4/thumb/',
			foreign_landing_url: 'https://www.flickr.com/photos/x/1',
			tags: [{ name: 'lighthouse' }, { name: 'sea' }]
		},
		{
			id: '9ad2c5c1-8f1a-4c4b-9a8e-1c2b3d4e5f60',
			title: 'Old lighthouse',
			creator: 'Bo Li',
			license: 'cc0',
			license_url: 'https://creativecommons.org/publicdomain/zero/1.0/',
			url: 'https://live.staticflickr.com/2/def_b.jpg',
			thumbnail: 'https://api.openverse.org/v1/images/9ad2/thumb/',
			foreign_landing_url: 'https://www.flickr.com/photos/x/2',
			tags: [{ name: 'tower' }]
		}
	]
};

describe('paths and lists', () => {
	it('quotes keys that are not identifiers', () => {
		expect(jmesKey('title')).toBe('title');
		expect(jmesKey('@id')).toBe('"@id"');
		expect(childPath(childPath('', 'query'), 'pages')).toBe('query.pages');
		expect(childPath('items', 0)).toBe('items[0]');
	});

	it('finds the results list, also when it is an object keyed by id', () => {
		expect(findLists(OPENVERSE)[0]).toMatchObject({ path: 'results', count: 2, kind: 'array' });
		expect(findLists(WIKIMEDIA)[0]).toMatchObject({
			path: 'values(query.pages || `{}`)',
			count: 2,
			kind: 'map'
		});
		expect(extractItems(WIKIMEDIA, findLists(WIKIMEDIA)[0].path)).toHaveLength(2);
		expect(extractItems({ query: {} }, 'values(query.pages || `{}`)')).toEqual([]);
	});
});

describe('evaluation mirrors the server', () => {
	it('applies default, map and transform in that order', () => {
		const item = { kind: 'IMAGE', name: 'File:Old_map.png', html: '<b>Hi</b> there ' };
		expect(evaluateField(item, { expr: 'kind', map: { IMAGE: 'image/jpeg' } })).toBe('image/jpeg');
		expect(evaluateField(item, { expr: 'missing', default: 'Untitled' })).toBe('Untitled');
		expect(evaluateField(item, { expr: 'name', transform: 'file_title' })).toBe('Old map');
		expect(evaluateField(item, { expr: 'html', transform: 'strip_html' })).toBe('Hi there');
		const iiif = { info: 'https://iiif.example.org/image/V1/info.json' };
		expect(evaluateField(iiif, { expr: 'info', transform: 'iiif_large' })).toBe(
			'https://iiif.example.org/image/V1/full/!2048,2048/0/default.jpg'
		);
		expect(evaluateField(iiif, { expr: 'info', transform: 'iiif_preview' })).toBe(
			'https://iiif.example.org/image/V1/full/!400,400/0/default.jpg'
		);
		expect(evaluateField(item, { literal: '1', expr: 'kind' })).toBe('1');
	});

	it('has the same id transforms', () => {
		expect(slugify('/90402/SK_A_3262')).toBe('90402-sk-a-3262');
		expect(slugify('')).toBe('untitled');
		expect(base32('/90402/SK_A_3262')).toBe('f44tanbqgixvgs27ifptgmrwgi');
		expect(fileTitle('File:1665 Girl_with a Pearl Earring.jpg')).toBe(
			'1665 Girl with a Pearl Earring'
		);
	});

	it('maps and filters like the engine', () => {
		const mapping = { fields: { assetID: { expr: 'id' }, assetURI: { expr: 'url' } } };
		const filter = { drop_if_missing: ['assetURI'] };
		expect(mapItem({ id: 'a', url: 'u' }, mapping, filter).dropped).toBeNull();
		expect(mapItem({ id: 'b' }, mapping, filter).dropped).toBe('No assetURI');
		expect(mapItem({ id: 'c' }, { fields: { title: { expr: 'a[' } } }).errors.title).toBeTruthy();
		expect(syntaxError('a[')).toBeTruthy();
		expect(syntaxError('a[0].b')).toBeNull();
	});
});

describe('suggestions', () => {
	const wiki = extractItems(WIKIMEDIA, 'values(query.pages || `{}`)');
	const open = OPENVERSE.results;
	const best = (name: string, items: unknown[]) => suggest(field(name), items)[0];

	it('reads through wrappers like Artist.value', () => {
		expect(leaves(wiki[0]).find((l) => l.path.endsWith('Artist.value'))?.key).toBe('Artist');
	});

	it('suggests sensible paths for MediaWiki', () => {
		expect(best('assetID', wiki).expr).toBe('to_string(pageid)');
		expect(best('title', wiki)).toMatchObject({ expr: 'title', transform: 'file_title' });
		expect(best('creator', wiki)).toMatchObject({
			expr: 'imageinfo[0].extmetadata.Artist.value',
			transform: 'strip_html'
		});
		expect(best('rights', wiki).expr).toBe('imageinfo[0].extmetadata.LicenseShortName.value');
		expect(best('assetURI', wiki).expr).toBe('imageinfo[0].url');
		expect(best('previewURI', wiki).expr).toBe('imageinfo[0].thumburl');
		expect(best('identifier', wiki).expr).toBe('imageinfo[0].descriptionurl');
		expect(best('contentType', wiki).expr).toBe('imageinfo[0].mime');
		expect(best('width', wiki).expr).toBe('imageinfo[0].width');
		expect(best('height', wiki).expr).toBe('imageinfo[0].height');
		expect(best('fileSize', wiki).expr).toBe('imageinfo[0].size');
	});

	it('suggests sensible paths for Openverse', () => {
		expect(best('assetID', open).expr).toBe('id');
		expect(best('rights', open).expr).toBe('license_url');
		expect(best('identifier', open).expr).toBe('foreign_landing_url');
		expect(best('creator', open).expr).toBe('creator');
		expect(best('subject', open).expr).toBe("join(', ', tags[].name[].to_string(@))");
	});
});

describe('editing the YAML in place', () => {
	const YAML = `# My source
collection:
  id: test
mapping:
  items_path: "results"
  fields:
    title:       { expr: "title" }   # shown on cards
    assetID:
      expr: "id"
      transform: slugify # readable
adapter:
  default_query:
    format: "json"   # keep me
    page_size: "20"
`;

	it('changes one value and keeps comments and quoting elsewhere', () => {
		const out = edit(YAML, (doc) => setValue(doc, ['mapping', 'items_path'], 'data.items'));
		expect(out).toContain('items_path: "data.items"');
		expect(out).toContain('# My source');
		expect(out).toContain('# shown on cards');
		expect(out).toContain('transform: slugify # readable');
	});

	it('writes fields in the one-line form and edits existing ones key by key', () => {
		let out = edit(YAML, (doc) =>
			setField(doc, 'creator', { expr: 'creator', transform: 'strip_html' })
		);
		expect(out).toContain('creator: { expr: "creator", transform: "strip_html" }');
		out = edit(out, (doc) => setField(doc, 'assetID', { expr: 'uuid', transform: 'slugify' }));
		expect(out).toContain('expr: "uuid"');
		expect(out).toContain('transform: slugify # readable');
		out = edit(out, (doc) => setField(doc, 'title', null));
		expect(parseConfig(out).data.mapping?.fields?.title).toBeUndefined();
	});

	it('creates missing sections and edits string maps key by key', () => {
		let out = edit(YAML, (doc) => setValue(doc, ['asset_detail', 'path'], '/items/{asset_id}'));
		expect(parseConfig(out).data.asset_detail?.path).toBe('/items/{asset_id}');
		out = edit(out, (doc) =>
			setStringMap(
				doc,
				['adapter', 'default_query'],
				[
					['format', 'json'],
					['lang', 'en']
				]
			)
		);
		expect(out).toContain('format: "json" # keep me');
		expect(parseConfig(out).data.adapter?.default_query).toEqual({ format: 'json', lang: 'en' });
	});

	it('reports YAML syntax errors instead of editing', () => {
		expect(parseConfig('a: [').error).toBeTruthy();
		expect(edit('a: [', (doc) => setValue(doc, ['a'], 'b'))).toBe('a: [');
	});
});
