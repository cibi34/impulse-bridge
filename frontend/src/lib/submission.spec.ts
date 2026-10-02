import { describe, expect, it } from 'vitest';
import { buildSubmission, MAILTO_LIMIT, shortMailto } from './submission';

const entry = (id: string, name: string) => ({
	id,
	uri: `https://curator.example/collections/${id}`,
	name,
	description: 'Test',
	organization: 'IMPULSE Curator',
	owner_id: 'impulse-curator',
	published: 1
});

describe('buildSubmission', () => {
	it('puts the platform entry into the mail and fits short ones into a mailto link', () => {
		const s = buildSubmission('team@example.org', [entry('masters-k3m9x2', 'Masters of light')]);
		expect(s.subject).toBe('New collection for IMPULSE: Masters of light');
		expect(s.body).toContain('"uri": "https://curator.example/collections/masters-k3m9x2"');
		expect(s.mailto).toMatch(/^mailto:team%40example\.org\?subject=/);
		expect(decodeURIComponent(s.mailto!)).toContain('"owner_id": "impulse-curator"');
	});

	it('lists several collections and drops the mailto link when it gets too long', () => {
		const many = Array.from({ length: 12 }, (_, i) => entry(`c-${i}`, `Collection ${i}`));
		const s = buildSubmission('team@example.org', many);
		expect(s.subject).toBe('12 new collections for IMPULSE');
		expect(s.body).toContain('• Collection 11');
		expect(s.mailto).toBeNull();
		expect(shortMailto(s).length).toBeLessThan(MAILTO_LIMIT);
	});
});
