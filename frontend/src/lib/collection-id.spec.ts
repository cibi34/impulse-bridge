import { describe, expect, it } from 'vitest';
import { collectionIdProblem, suggestCollectionId } from './collection-id';

describe('collection ids', () => {
	it('accepts the id-schema and nothing else', () => {
		for (const ok of ['europeana-public-domain-images', 'masters-of-light-k3m9x2', 'a1b']) {
			expect(collectionIdProblem(ok)).toBeNull();
		}
		for (const bad of [
			'Europeana',
			'with space',
			'-leading',
			'trailing-',
			'double--hyphen',
			'a.b'
		]) {
			expect(collectionIdProblem(bad)).toContain('lowercase');
		}
		expect(collectionIdProblem('ab')).toContain('at least 3');
		expect(collectionIdProblem('x'.repeat(81))).toContain('at most 80');
	});

	it('suggests a valid id for other text', () => {
		expect(suggestCollectionId('Europeana Public Domain Images')).toBe(
			'europeana-public-domain-images'
		);
		expect(suggestCollectionId('Köln -- Dom')).toBe('koln-dom');
		expect(suggestCollectionId('already-fine')).toBeNull();
		expect(suggestCollectionId('!!')).toBeNull();
	});
});
