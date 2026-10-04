/**
 * The Impulse asset fields the mapper offers, in the order it shows them.
 * `kind` drives suggestions and checks; `group` the layout.
 */

export type FieldKind =
	| 'id'
	| 'title'
	| 'text'
	| 'person'
	| 'date'
	| 'institution'
	| 'page'
	| 'media'
	| 'preview'
	| 'licence'
	| 'mime'
	| 'list'
	| 'genre'
	| 'code'
	| 'scale'
	| 'width'
	| 'height'
	| 'bytes'
	| 'place'
	| 'extent';

export type FieldGroup = 'required' | 'recommended' | 'more';

export interface FieldDef {
	name: string;
	label: string;
	help: string;
	kind: FieldKind;
	group: FieldGroup;
	/** A fixed value that is often right (offered as a one-click choice). */
	literal?: string;
}

export const FIELDS: FieldDef[] = [
	{
		name: 'assetID',
		label: 'Asset ID',
		help: 'Unique and stable per asset; used to look it up again. Text, not a number.',
		kind: 'id',
		group: 'required'
	},
	{
		name: 'title',
		label: 'Title',
		help: 'Shown on cards and in Unity.',
		kind: 'title',
		group: 'required'
	},
	{
		name: 'assetURI',
		label: 'Media file',
		help: 'The image or 3D file Unity loads — a direct file URL, not a web page.',
		kind: 'media',
		group: 'required'
	},
	{
		name: 'previewURI',
		label: 'Preview image',
		help: 'A small image for cards; the media file works too if there is none.',
		kind: 'preview',
		group: 'required'
	},
	{
		name: 'rights',
		label: 'Licence',
		help: 'Decides whether the asset can be used at all. A licence URL or a name like “CC BY 4.0”.',
		kind: 'licence',
		group: 'required'
	},
	{
		name: 'contentType',
		label: 'Content type',
		help: 'MIME type: image/jpeg, image/png, model/gltf-binary, …',
		kind: 'mime',
		group: 'required',
		literal: 'image/jpeg'
	},
	{
		name: 'creator',
		label: 'Creator',
		help: 'Artist, photographer or maker — part of the credits.',
		kind: 'person',
		group: 'recommended'
	},
	{
		name: 'contributor',
		label: 'Institution',
		help: 'The museum, library or archive that holds the work.',
		kind: 'institution',
		group: 'recommended'
	},
	{
		name: 'identifier',
		label: 'Source page',
		help: 'Link to the work’s page at the archive (“View at the source”).',
		kind: 'page',
		group: 'recommended'
	},
	{
		name: 'description',
		label: 'Description',
		help: 'A sentence or two about the work.',
		kind: 'text',
		group: 'recommended'
	},
	{
		name: 'date',
		label: 'Date',
		help: 'When the work was made.',
		kind: 'date',
		group: 'recommended'
	},
	{ name: 'subject', label: 'Subject', help: 'Keywords or topics.', kind: 'list', group: 'more' },
	{
		name: 'type',
		label: 'Type',
		help: 'The kind of work: painting, photograph, …',
		kind: 'genre',
		group: 'more'
	},
	{
		name: 'language',
		label: 'Language',
		help: 'Language of the work.',
		kind: 'code',
		group: 'more'
	},
	{
		name: 'publisher',
		label: 'Publisher',
		help: 'Who published it.',
		kind: 'institution',
		group: 'more'
	},
	{
		name: 'coverage',
		label: 'Place',
		help: 'Where the work is from or shows.',
		kind: 'place',
		group: 'more'
	},
	{
		name: 'width',
		label: 'Width (px)',
		help: 'Pixel width of the media file — shown in the web app, sent to Unity inside “format”.',
		kind: 'width',
		group: 'more'
	},
	{
		name: 'height',
		label: 'Height (px)',
		help: 'Pixel height of the media file.',
		kind: 'height',
		group: 'more'
	},
	{
		name: 'fileSize',
		label: 'File size (bytes)',
		help: 'Size of the media file in bytes.',
		kind: 'bytes',
		group: 'more'
	},
	{
		name: 'format',
		label: 'Format',
		help: 'File format, medium or the work’s dimensions, as text. Pixel size and file size are added to it for Unity.',
		kind: 'extent',
		group: 'more'
	},
	{
		name: 'scale',
		label: 'Scale',
		help: 'Size factor for Unity; “1” means the model is in metres.',
		kind: 'scale',
		group: 'more',
		literal: '1'
	}
];

export const GROUP_LABELS: Record<FieldGroup, string> = {
	required: 'Needed for IMPULSE',
	recommended: 'Recommended',
	more: 'More'
};

/** Fields whose absence makes an asset unusable (offered for the filter). */
export const ESSENTIAL = ['assetID', 'title', 'assetURI', 'previewURI', 'rights'];

export const TRANSFORMS = [
	{ value: 'strip_html', label: 'Remove HTML' },
	{ value: 'file_title', label: 'File name → title' },
	{ value: 'slugify', label: 'Slug (readable id)' },
	{ value: 'base32', label: 'Base32 (reversible id)' },
	{ value: 'lower', label: 'Lower case' },
	{ value: 'upper', label: 'Upper case' }
] as const;

export type TransformName = (typeof TRANSFORMS)[number]['value'];
