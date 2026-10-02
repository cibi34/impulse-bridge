import { describe, expect, it } from 'vitest';
import { interleave } from './search.svelte';

describe('interleave', () => {
	it('takes one item from each list in turn', () => {
		expect(interleave([['a1', 'a2', 'a3'], ['b1'], ['c1', 'c2']])).toEqual([
			'a1',
			'b1',
			'c1',
			'a2',
			'c2',
			'a3'
		]);
	});

	it('handles empty input', () => {
		expect(interleave([])).toEqual([]);
		expect(interleave([[], []])).toEqual([]);
	});
});
