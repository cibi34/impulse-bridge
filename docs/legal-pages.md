# Legal pages — what they must cover

The web app ships the legal pages with **placeholder text** (lorem ipsum) and a visible "Placeholder" notice. This page lists what each one needs and the facts about the app that the texts have to reflect, so whoever writes them has everything in one place. It is a checklist, not legal advice; have the final texts reviewed.

| Page | File | Notice shown |
|---|---|---|
| Imprint | `frontend/src/routes/(site)/legal/imprint/+page.svelte` | yes |
| Privacy | `…/legal/privacy/+page.svelte` | yes |
| Terms of use | `…/legal/terms/+page.svelte` | yes |
| Accessibility | `…/legal/accessibility/+page.svelte` | yes |
| Report content | `frontend/src/routes/(site)/report/+page.svelte` | yes |
| Credits & sources | `frontend/src/routes/(site)/credits/+page.svelte` | no (final) |

All pages use `LegalPage` (`frontend/src/lib/components/LegalPage.svelte`); pass `draft={false}` once a page is final. The pages are prerendered: rebuild and redeploy after editing (`docker compose up -d --build`).

## Imprint (German law: § 5 DDG, § 18 MStV)

- Provider: name and legal form, postal address (no P.O. box).
- Represented by (managing directors).
- Fast electronic contact: email address, plus a phone number or contact form.
- Register court and number, VAT ID (§ 27a UStG), if applicable.
- Person responsible for editorial content (§ 18 (2) MStV), with address.
- The project paragraph (IMPULSE, grant agreement No 101132704) is already final.

## Privacy (GDPR, § 25 TDDDG)

Facts to describe:

| Processing | Details |
|---|---|
| Server logs | Traefik and the app log each request with IP address, time, path, status, user agent. Docker keeps at most 3 × 10 MB per container, then the oldest data is overwritten (`deploy/docker-compose.yml`, `deploy/traefik/docker-compose.yml`). For a fixed retention in days, add a logrotate/journald policy and state it here. Hosting: the VM's provider (processor, Art. 28 GDPR). |
| Archive images | Browsers load previews directly from the archives: Europeana (`api.europeana.eu`, EU), Wikimedia Foundation (`upload.wikimedia.org`, `thumb.wikimedia.org`, USA), Heidelberg University Library (`digi.ub.uni-heidelberg.de`, DE). The archive receives the visitor's IP address and user agent — no cookies (`crossorigin="anonymous"`) and no referrer (`referrerpolicy="no-referrer"`). Needs a legal basis (e.g. Art. 6 (1) (f) GDPR) and the third-country transfer basis. Sources added later in the admin add hosts to this list. |
| Collections | Name, description, selected assets (metadata snapshots), creation and change times. Public at their URL. Optional creator email, never published. Stored in `data/curator.db` until deleted by the creator or an admin. |
| Email | Only if a creator enters an address: sign-in links (valid 15 minutes, single use) and, on request, the edit link. Sent through the SMTP provider set in the admin (processor). |
| Sessions | After sign-in: session cookie (`HttpOnly`, 30 days). Stored server-side with the email address. |
| Browser storage | `localStorage`: the current selection, the visitor's collections with their edit keys, the appearance setting (`curator-theme`). All set only by the visitor's own actions, nothing for analytics or tracking. Strictly necessary under § 25 (2) No. 2 TDDDG — **no cookie consent needed.** |
| Submission | "Submit to IMPULSE" opens the visitor's own email program; the Curator does not send that email. Recipient: the submission address set in the admin. |
| Not used | No analytics, no tracking, no advertising, no third-party scripts, fonts or embeds (fonts are self-hosted; the CSP allows scripts and connections only to the site itself). |

Also needed: the controller's contact, the data protection officer (if appointed), the rights under Art. 15–21 GDPR, and the supervisory authority.

If the operator later adds analytics or embeds (videos, maps), consent becomes necessary and the CSP (`frontend/vite.config.ts`) has to be widened — both deliberately.

## Terms of use

- The service and its provider; free of charge, no guaranteed availability.
- Rules for collection names and descriptions (they are public); keeping the edit link private.
- Licence for texts that creators write, if the provider needs one.
- Rights in the assets stay with the archives; each asset shows its licence. Only works whose licence IMPULSE accepts can be used (admin setting, default public domain, CC0, CC BY, CC BY-SA); each collection page lists the licences and the credits they require, and the web app offers them for copying and as CSV.
- Moderation: admins can hide (unlist), lock and delete collections. Under the DSA: statement of reasons (Art. 17), internal complaints if applicable, point of contact (Art. 11/12) and the languages for it.
- Liability, changes to the terms, applicable law.

## Accessibility

Only mandatory for public-sector bodies (EU Directive 2016/2102) and for services under the European Accessibility Act; recommended otherwise. Facts for the statement:

- Target: WCAG 2.2 AA. Automated checks (axe-core) report no violations on any page or dialog, in light and dark appearance; a manual audit has not been done yet.
- Keyboard use throughout, including reordering assets; reduced motion respected.
- Known limitation: images and metadata come from the archives, many images have no text alternative (titles and creators are used instead).
- Feedback contact and response time; enforcement or arbitration body if the law requires one.

## Report content (Art. 16 DSA)

The page explains how to report a collection and offers a template. Needed: the **report email address** (`REPORT_ADDRESS` in the page) and a short intro on how reports are handled. Admins act in **Admin → Collections** (lock or delete).

## Other places with legal wording

- The EU funding disclaimer in the footer (`frontend/src/lib/components/SiteFooter.svelte`) names the European Research Executive Agency (REA) as granting authority — confirm it against the grant agreement.
- The EU emblem (`frontend/static/brand/eu-funded-*.png`) is the official file, unmodified.

---

_Continue to the [docs index](README.md)._
