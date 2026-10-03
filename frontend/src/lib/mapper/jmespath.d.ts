// The jmespath package ships no types of its own (and @types/jmespath lacks
// `compile`); these are the two functions the mapper uses.
declare module 'jmespath' {
	export function search(data: unknown, expression: string): unknown;
	/** Parses an expression; throws on a syntax error. */
	export function compile(expression: string): unknown;
	const jmespath: { search: typeof search; compile: typeof compile };
	export default jmespath;
}
