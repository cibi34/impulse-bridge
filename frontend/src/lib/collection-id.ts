/**
 * Collection ids follow the Impulse id-schema: lowercase letters and digits,
 * words joined by single hyphens. Mirrors collection_id_problem() in
 * app/curation/service.py, which has the final say.
 */

import { slugify } from '#lib/format.js';

export const ID_LENGTH = { min: 3, max: 80 } as const;

const ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Why `value` cannot be a collection id, or null. */
export function collectionIdProblem(value: string): string | null {
	if (value.length < ID_LENGTH.min) return `Use at least ${ID_LENGTH.min} characters.`;
	if (value.length > ID_LENGTH.max) return `Use at most ${ID_LENGTH.max} characters.`;
	if (!ID.test(value)) {
		return 'Use only lowercase letters a–z, digits and single hyphens, starting and ending with a letter or digit.';
	}
	return null;
}

/** The nearest valid id for some text ("Masters of Light" → "masters-of-light"), or null. */
export function suggestCollectionId(value: string): string | null {
	const slug = slugify(value).slice(0, ID_LENGTH.max).replace(/-+$/, '');
	return slug && slug !== value && !collectionIdProblem(slug) ? slug : null;
}
