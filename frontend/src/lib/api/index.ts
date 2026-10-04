import { request } from './client';
import type {
	AppConfig,
	Asset,
	AssetRef,
	Collection,
	CollectionItem,
	CollectionSummary,
	Failure,
	ImpulseCollection,
	LicenceTier,
	SearchPage,
	Source
} from './types';

export * from './types';
export { ApiError, errorMessage } from './client';

const enc = encodeURIComponent;

export const api = {
	config: () => request<AppConfig>('/api/config'),

	// ---- sources ----

	sources: async () => (await request<{ sources: Source[] }>('/api/sources')).sources,

	search: (
		source: string,
		params: {
			q?: string;
			offset?: number;
			count?: number;
			type?: 'image' | 'model';
			licence?: LicenceTier;
		},
		signal?: AbortSignal
	) => {
		const query = new URLSearchParams();
		if (params.q) query.set('s', params.q);
		if (params.offset) query.set('o', String(params.offset));
		if (params.count) query.set('c', String(params.count));
		if (params.type) query.set('type', params.type);
		if (params.licence) query.set('licence', params.licence);
		return request<SearchPage>(`/api/sources/${enc(source)}/assets?${query}`, { signal });
	},

	sourceAsset: (source: string, assetId: string) =>
		request<Asset>(`/api/sources/${enc(source)}/assets/${enc(assetId)}`),

	// ---- collections ----

	createCollection: (body: {
		name: string;
		description?: string;
		organization?: string;
		email?: string | null;
		items: AssetRef[];
	}) =>
		request<{ collection: Collection; edit_key: string; failed: Failure[] }>('/api/collections', {
			method: 'POST',
			body
		}),

	collection: (id: string, editKey?: string | null) =>
		request<Collection>(`/api/collections/${enc(id)}`, { editKey }),

	/** Overviews of stored collections; `moved` maps former ids to current ones. */
	summaries: async (
		ids: string[]
	): Promise<{ collections: CollectionSummary[]; moved: Record<string, string> }> =>
		ids.length === 0
			? { collections: [], moved: {} }
			: request<{ collections: CollectionSummary[]; moved: Record<string, string> }>(
					`/api/collections?ids=${ids.map(enc).join(',')}`
				),

	updateCollection: (
		id: string,
		editKey: string | null,
		changes: Partial<Pick<Collection, 'name' | 'description' | 'organization'>> & {
			email?: string;
		}
	) =>
		request<Collection>(`/api/collections/${enc(id)}`, {
			method: 'PATCH',
			body: changes,
			editKey
		}),

	deleteCollection: (id: string, editKey: string | null) =>
		request<void>(`/api/collections/${enc(id)}`, { method: 'DELETE', editKey }),

	addItems: (id: string, editKey: string | null, items: AssetRef[]) =>
		request<{ added: CollectionItem[]; failed: Failure[] }>(`/api/collections/${enc(id)}/items`, {
			method: 'POST',
			body: { items },
			editKey
		}),

	setPublished: (id: string, editKey: string | null, assetId: string, published: boolean) =>
		request<CollectionItem>(`/api/collections/${enc(id)}/items/${enc(assetId)}`, {
			method: 'PATCH',
			body: { published },
			editKey
		}),

	removeItem: (id: string, editKey: string | null, assetId: string) =>
		request<void>(`/api/collections/${enc(id)}/items/${enc(assetId)}`, {
			method: 'DELETE',
			editKey
		}),

	reorder: (id: string, editKey: string | null, assetIds: string[]) =>
		request<{ asset_ids: string[] }>(`/api/collections/${enc(id)}/order`, {
			method: 'PUT',
			body: { asset_ids: assetIds },
			editKey
		}),

	refresh: (id: string, editKey: string | null) =>
		request<{ refreshed: number; failed: Failure[] }>(`/api/collections/${enc(id)}/refresh`, {
			method: 'POST',
			editKey
		}),

	markSubmitted: (id: string, editKey: string | null) =>
		request<{ submitted_at: string }>(`/api/collections/${enc(id)}/submitted`, {
			method: 'POST',
			editKey
		}),

	resetKey: (id: string, editKey: string | null) =>
		request<{ edit_key: string }>(`/api/collections/${enc(id)}/key`, { method: 'POST', editKey }),

	emailEditLink: (id: string, editKey: string) =>
		request<{ sent_to: string }>(`/api/collections/${enc(id)}/email-link`, {
			method: 'POST',
			editKey
		}),

	/** The Impulse API's view of a collection (what the platform registers). */
	impulseCollection: async (id: string) =>
		(await request<{ data: ImpulseCollection }>(`/collections/${enc(id)}`)).data,

	// ---- sign-in ----

	requestSignIn: (email: string) =>
		request<{ detail: string }>('/api/auth/login', { method: 'POST', body: { email } }),

	verifySignIn: (token: string) =>
		request<{ email: string }>('/api/auth/verify', { method: 'POST', body: { token } }),

	me: () => request<{ email: string | null }>('/api/auth/me'),

	signOut: () => request<void>('/api/auth/logout', { method: 'POST' }),

	myCollections: async () =>
		(await request<{ collections: CollectionSummary[] }>('/api/me/collections')).collections
};
