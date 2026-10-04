import { describe, expect, it } from 'vitest';
import {
	dimensionsLabel,
	fileSizeLabel,
	kindLabel,
	megapixelsLabel,
	plural,
	timeAgo
} from './format';

describe('format', () => {
	it('describes how long ago something happened', () => {
		const now = new Date('2026-10-02T12:00:00Z');
		expect(timeAgo('2026-10-02T11:59:40Z', now)).toBe('just now');
		expect(timeAgo('2026-10-02T11:55:00Z', now)).toBe('5 minutes ago');
		expect(timeAgo('2026-10-01T12:00:00Z', now)).toBe('yesterday');
	});

	it('pluralizes and labels content types', () => {
		expect(plural(1, 'asset')).toBe('1 asset');
		expect(plural(3, 'asset')).toBe('3 assets');
		expect(kindLabel('model/gltf-binary')).toBe('3D model');
		expect(kindLabel('image/jpeg')).toBe('Image');
		expect(kindLabel(undefined)).toBe('Asset');
	});
});

describe('sizes', () => {
	it('labels file sizes like the server', () => {
		expect(fileSizeLabel(8770678)).toBe('8.8 MB');
		expect(fileSizeLabel(3000)).toBe('3 KB');
		expect(fileSizeLabel(999)).toBe('999 bytes');
		expect(fileSizeLabel('n/a')).toBeNull();
	});

	it('labels pixel sizes', () => {
		expect(dimensionsLabel(3606, '2894')).toBe('3606 × 2894');
		expect(dimensionsLabel(10, null)).toBeNull();
		expect(megapixelsLabel(3606, 2894)).toBe('10.4 MP');
		expect(megapixelsLabel(800, 600)).toBeNull();
	});
});
