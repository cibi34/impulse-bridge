import { describe, expect, it } from 'vitest';
import { rightsLabel, rightsUrl } from './rights';

describe('rightsLabel', () => {
	it.each([
		['http://creativecommons.org/publicdomain/zero/1.0/', 'CC0'],
		['http://creativecommons.org/publicdomain/mark/1.0/', 'Public domain'],
		['http://creativecommons.org/licenses/by-sa/4.0/', 'CC BY-SA 4.0'],
		['https://creativecommons.org/licenses/by/2.0', 'CC BY 2.0'],
		['http://rightsstatements.org/vocab/InC/1.0/', 'In copyright'],
		['http://rightsstatements.org/vocab/NoC-NC/1.0/', 'No copyright – non-commercial use only'],
		['CC BY-SA 4.0', 'CC BY-SA 4.0'],
		['Public domain', 'Public domain'],
		['https://example.org/terms', 'https://example.org/terms']
	])('%s → %s', (value, label) => {
		expect(rightsLabel(value)).toBe(label);
	});

	it('handles missing values and tells URIs apart', () => {
		expect(rightsLabel(undefined)).toBeNull();
		expect(rightsUrl('CC0')).toBeNull();
		expect(rightsUrl('http://creativecommons.org/publicdomain/zero/1.0/')).toBe(
			'http://creativecommons.org/publicdomain/zero/1.0/'
		);
	});
});
