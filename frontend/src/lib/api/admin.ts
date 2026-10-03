import { ApiError, request } from './client';
import type { Asset, Licence, LicenceCondition } from './types';

const enc = encodeURIComponent;

export interface AdminCollection {
	id: string;
	uri: string;
	name: string;
	description: string;
	organization: string;
	email: string | null;
	item_count: number;
	listed: boolean;
	disabled: boolean;
	submitted_at: string | null;
	created_at: string;
	updated_at: string;
}

export interface SourceSummary {
	filename: string;
	id: string | null;
	name: string | null;
	kind: string | null;
	base_url: string | null;
	loaded: boolean;
	error: string | null;
}

export interface ValidationIssue {
	loc: (string | number)[];
	msg: string;
	line: number | null;
}

export interface SourceFile {
	filename: string;
	yaml: string;
	id: string | null;
	valid: boolean;
	errors: ValidationIssue[];
	loaded: boolean;
	load_error: string | null;
}

export interface TestRun {
	valid: boolean;
	errors: { loc: (string | number)[]; msg: string }[];
	transformed: Asset[];
	/** How each transformed asset's `rights` value is read, in the same order. */
	licences: Licence[];
	raw_upstream: unknown;
	upstream_url: string | null;
}

export interface Template {
	key: string;
	label: string;
	yaml: string;
}

export interface AdminSettings {
	submission_email: string;
	smtp_host: string;
	smtp_port: number;
	smtp_security: 'starttls' | 'ssl' | 'none';
	smtp_username: string;
	mail_from: string;
	/** Licence conditions IMPULSE accepts; public domain and CC0 always are. */
	licence_conditions: LicenceCondition[];
	smtp_password_set: boolean;
	smtp_password_from_env: boolean;
	mail_configured: boolean;
	mail_log_only: boolean;
	server: {
		public_base_url: string;
		collection_owner_id: string;
		default_organization: string;
		max_assets_per_collection: number;
		config_dir: string;
		database: string;
	};
}

export type SettingsChanges = Partial<
	Pick<
		AdminSettings,
		| 'submission_email'
		| 'smtp_host'
		| 'smtp_port'
		| 'smtp_security'
		| 'smtp_username'
		| 'mail_from'
		| 'licence_conditions'
	>
> & { smtp_password?: string };

/** Validation issues from a 422 response of the file endpoints. */
export function validationIssues(error: unknown): ValidationIssue[] | null {
	if (error instanceof ApiError && error.status === 422) {
		const detail = (error.body as { detail?: { errors?: ValidationIssue[] } } | null)?.detail;
		if (detail?.errors) return detail.errors;
	}
	return null;
}

export const admin = {
	// ---- collections ----
	collections: async () =>
		(await request<{ collections: AdminCollection[] }>('/admin/api/collections')).collections,
	updateCollection: (id: string, changes: { listed?: boolean; disabled?: boolean }) =>
		request<AdminCollection>(`/admin/api/collections/${enc(id)}`, {
			method: 'PATCH',
			body: changes
		}),
	deleteCollection: (id: string) =>
		request<void>(`/admin/api/collections/${enc(id)}`, { method: 'DELETE' }),
	newEditKey: (id: string) =>
		request<{ edit_key: string }>(`/admin/api/collections/${enc(id)}/key`, { method: 'POST' }),

	// ---- sources ----
	sources: () => request<{ sources: SourceSummary[]; loaded_count: number }>('/admin/api/sources'),
	reload: () =>
		request<{ sources: SourceSummary[]; loaded_count: number }>('/admin/api/reload', {
			method: 'POST'
		}),
	file: (filename: string) => request<SourceFile>(`/admin/api/files/${enc(filename)}`),
	createFile: (yaml: string) =>
		request<SourceFile>('/admin/api/files', { method: 'POST', body: { yaml } }),
	saveFile: (filename: string, yaml: string) =>
		request<SourceFile>(`/admin/api/files/${enc(filename)}`, { method: 'PUT', body: { yaml } }),
	deleteFile: (filename: string) =>
		request<{ deleted: string }>(`/admin/api/files/${enc(filename)}`, { method: 'DELETE' }),
	validate: (yaml: string, signal?: AbortSignal) =>
		request<{ valid: boolean; errors: ValidationIssue[]; id: string | null }>(
			'/admin/api/validate',
			{
				method: 'POST',
				body: { yaml },
				signal
			}
		),
	test: (yaml: string, query: string, count: number) =>
		request<TestRun>('/admin/api/test', {
			method: 'POST',
			body: { yaml, query: query || null, count }
		}),
	templates: async () =>
		(await request<{ templates: Template[] }>('/admin/api/templates')).templates,

	// ---- settings ----
	settings: () => request<AdminSettings>('/admin/api/settings'),
	saveSettings: (changes: SettingsChanges) =>
		request<AdminSettings>('/admin/api/settings', { method: 'PUT', body: changes }),
	testEmail: (to: string) =>
		request<{ sent_to: string }>('/admin/api/settings/test-email', { method: 'POST', body: { to } })
};
