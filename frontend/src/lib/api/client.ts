/**
 * Small fetch wrapper for the bridge's same-origin APIs. Errors become an
 * `ApiError` carrying the HTTP status and the server's `detail` message,
 * which is written for people and can be shown as is.
 */

export class ApiError extends Error {
	constructor(
		readonly status: number,
		message: string
	) {
		super(message);
		this.name = 'ApiError';
	}

	get isNetworkError(): boolean {
		return this.status === 0;
	}
}

export interface RequestOptions {
	method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
	body?: unknown;
	/** The collection edit key, sent as a bearer token. */
	editKey?: string | null;
	signal?: AbortSignal;
}

function messageFrom(status: number, body: unknown): string {
	if (body && typeof body === 'object' && 'detail' in body) {
		const detail = (body as { detail: unknown }).detail;
		if (typeof detail === 'string') return detail;
		if (Array.isArray(detail) && detail.length > 0) {
			// FastAPI validation errors: [{loc, msg}, …]
			const first = detail[0] as { msg?: string };
			if (first?.msg) return first.msg.replace(/^Value error, /, '');
		}
	}
	if (status === 429) return 'Too many requests. Please try again in a moment.';
	if (status >= 500) return 'Something went wrong on the server. Please try again.';
	return `Request failed (${status})`;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
	const headers: Record<string, string> = { Accept: 'application/json' };
	if (options.body !== undefined) headers['Content-Type'] = 'application/json';
	if (options.editKey) headers.Authorization = `Bearer ${options.editKey}`;

	let response: Response;
	try {
		response = await fetch(path, {
			method: options.method ?? 'GET',
			headers,
			body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
			credentials: 'same-origin',
			signal: options.signal
		});
	} catch (error) {
		if (error instanceof DOMException && error.name === 'AbortError') throw error;
		throw new ApiError(0, 'You appear to be offline, or the server is not reachable.');
	}

	if (response.status === 204) return undefined as T;
	const body = await response.json().catch(() => null);
	if (!response.ok) throw new ApiError(response.status, messageFrom(response.status, body));
	return body as T;
}

export function errorMessage(error: unknown): string {
	if (error instanceof ApiError) return error.message;
	if (error instanceof Error) return error.message;
	return 'Something went wrong.';
}
