export type LicenceCondition = 'by' | 'sa' | 'nc' | 'nd';

/** The search's licence filter: no conditions, or attribution at most. */
export type LicenceTier = 'free' | 'by';

/** How the server reads an asset's `rights` value (app/licensing.py). */
export interface Licence {
	/** "pd", "cc0", "by", "by-sa", … or "other" for anything not openly licensed. */
	code: string;
	label: string;
	url: string | null;
	conditions: LicenceCondition[];
	/** Whether IMPULSE accepts it (admin setting). */
	allowed: boolean;
}

/** An asset in the Impulse schema, as the bridge maps it from a source. */
export interface Asset {
	assetID: string;
	title?: string;
	description?: string;
	creator?: string;
	contributor?: string;
	date?: string;
	rights?: string;
	identifier?: string;
	subject?: string;
	type?: string;
	language?: string;
	publisher?: string;
	contentType?: string;
	assetURI?: string;
	previewURI?: string;
	scale?: string;
	published?: number;
	format?: string;
	coverage?: string;
	/** Pixels of the media file, where the archive says (web app only). */
	width?: number;
	height?: number;
	/** Bytes of the media file, where the archive says (web app only). */
	fileSize?: number;
	/** Added by the web app API to search results and source lookups. */
	licence?: Licence;
	[field: string]: unknown;
}

export interface Source {
	id: string;
	name: string | null;
	description: string | null;
	organization: string | null;
}

export interface SearchPage {
	source: string;
	items: Asset[];
	/** Assets left out because IMPULSE doesn't accept their licence. */
	hidden: number;
	offset: number;
	/** Where the next page starts; null when there are no more results. */
	next_offset: number | null;
}

export interface CollectionItem {
	asset_id: string;
	source: string;
	source_asset_id: string;
	published: boolean;
	licence: Licence;
	asset: Asset;
	added_at: string;
	refreshed_at: string;
}

export interface Collection {
	id: string;
	uri: string;
	name: string;
	description: string;
	organization: string;
	created_at: string;
	updated_at: string;
	submitted_at: string | null;
	listed: boolean;
	item_count: number;
	items: CollectionItem[];
	can_edit: boolean;
	/** Only for editors. */
	email?: string | null;
	locked?: boolean;
}

export interface CollectionSummary {
	id: string;
	uri: string;
	name: string;
	description: string;
	item_count: number;
	updated_at: string;
	submitted_at: string | null;
	previews: (string | null)[];
}

export interface Failure {
	source: string;
	asset_id: string;
	reason: string;
}

export interface AssetRef {
	source: string;
	asset_id: string;
}

export interface AppConfig {
	app_name: string;
	submission_email: string | null;
	sign_in_available: boolean;
	max_assets_per_collection: number;
	licence_conditions: LicenceCondition[];
}

/** Collection metadata as the Impulse API publishes it. */
export interface ImpulseCollection {
	id: string;
	uri: string;
	name: string;
	description: string;
	organization: string;
	owner_id: string;
	published: number;
}
