/**
 * The facts the legal pages are built from: who runs the Curator, where it
 * is hosted, how to reach us. Replace every value in [square brackets]; the
 * legal pages show a notice as long as one is left. The pages are
 * prerendered, so rebuild after editing (`docker compose up -d --build`).
 */
export const provider = {
	name: 'Institut für Strategische Ästhetik gGmbH',
	short: 'K8',
	website: 'https://k8.design',
	street: '[Street and number]',
	city: '[Postcode and city]',
	country: 'Germany',
	representedBy: '[Managing director(s)]',
	email: '[contact email address]',
	phone: '[phone number]',
	registerCourt: '[Register court]',
	registerNumber: '[HRB number]',
	/** Leave empty if there is none; the line is then left out. */
	vatId: '[VAT identification number]',
	/** Where reports about collections go (the Report content page). */
	reportEmail: '[report email address]',
	/** Who delivers the sign-in and edit-link emails (the SMTP service set in the admin). */
	emailProvider: '[email service provider]',
	hosting: { provider: 'Oracle', location: 'Frankfurt, Germany' },
	siteUrl: 'https://impulse-bridge.octo-code.de',
	impulse: {
		name: 'IMPULSE — Immersive digitisation: upcycling cultural heritage towards new reviving strategies',
		grant: '101132704',
		url: 'https://euimpulse.eu/'
	},
	updated: '5 October 2026'
};

export const isPlaceholder = (text: string): boolean => /^\[.*\]$/.test(text.trim());

/** True once a fact has been filled in: the pages show such lines, and leave the rest out. */
export const known = (text: string): boolean => text.trim() !== '' && !isPlaceholder(text);

const strings = (value: object): string[] =>
	Object.values(value).flatMap((v) => (typeof v === 'string' ? [v] : strings(v)));

/** True while any fact above is still a [placeholder]. */
export const legalDraft = strings(provider).some(isPlaceholder);
