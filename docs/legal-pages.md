# Legal pages — what they say and what to fill in

The imprint, privacy notice, terms of use, accessibility statement and the report page are written. They are built from one file of facts, `frontend/src/lib/legal.ts`: who runs the Curator, where it is hosted, how to reach the provider. Values still in `[square brackets]` are placeholders: the lines that need them (address, contact, register entry, report address) are left out, and the pages show a "Test deployment" notice instead, until the value is filled in. The pages are prerendered: rebuild and redeploy after editing (`docker compose up -d --build`).

This page records the reasoning behind the texts and the facts they rely on. It is not legal advice; have the final texts reviewed.

| Page | File |
|---|---|
| Imprint | `frontend/src/routes/(site)/legal/imprint/+page.svelte` |
| Privacy | `…/legal/privacy/+page.svelte` |
| Terms of use | `…/legal/terms/+page.svelte` |
| Accessibility | `…/legal/accessibility/+page.svelte` |
| Report content | `frontend/src/routes/(site)/report/+page.svelte` |
| Credits & sources | `frontend/src/routes/(site)/credits/+page.svelte` |

## Who is the provider

The Curator is hosted and operated by Institut für Strategische Ästhetik gGmbH (K8), a partner in the IMPULSE consortium. German law (§ 5 DDG) asks for an imprint from whoever provides a service like this, and that is the operator, not the project: the project coordinator or the EU are named in the project paragraph, but they do not run the server. Linking to the project website alone would not do.

Minimum for the imprint, all in `legal.ts`: name and legal form, postal address, managing director(s), email and phone, register court and number, VAT ID if there is one. "Responsible for the content" (§ 18 (2) MStV) is only required for journalistic-editorial content, which the Curator has none of; the line is kept because it is customary and harmless.

Because visitors publish collections (names and descriptions), the Curator is a hosting service in the sense of the Digital Services Act. That brings three things, all covered: a point of contact for authorities and users (Art. 11, 12 — the contact email, languages German and English, in the imprint and the terms), a way to report content (Art. 16 — the report page), and reasons given to a creator whose collection is hidden, locked or deleted (Art. 17 — stated in the terms; admins act in **Admin → Collections**, and the creator's email is shown there when one was given).

## Facts in the privacy notice

| Processing | Details |
|---|---|
| Hosting | Virtual server of the provider named in `legal.ts` (`hosting`), located in Frankfurt, Germany; processor under Art. 28 GDPR. |
| Server logs | Traefik and the app log each request with IP address, time, path, status, user agent. Docker keeps at most 3 × 10 MB per container, then the oldest data is overwritten (`deploy/docker-compose.yml`, `deploy/traefik/docker-compose.yml`). For a fixed retention in days, add a logrotate/journald policy and change the notice. |
| Searches | The server queries the archives; the archives see the server's address, not the visitor's. |
| Archive images | Browsers load previews and files directly from the archives: Europeana (`api.europeana.eu`, NL; 3D previews from the providing museum, e.g. `mmb.cimec.ro`, RO), Heidelberg University Library (`digi.ub.uni-heidelberg.de`, DE), Statens Museum for Kunst (`iip.smk.dk`, DK), Zenodo / CERN (`zenodo.org`, CH — adequacy decision), Wellcome Collection (`iiif.wellcomecollection.org`, UK — adequacy decision), Cleveland Museum of Art (`openaccess-cdn.clevelandart.org`, USA), The Metropolitan Museum of Art (`images.metmuseum.org`, USA), Wikimedia Foundation (`upload.wikimedia.org`, `thumb.wikimedia.org`, USA). The archive receives the visitor's IP address and user agent — no cookies (`crossorigin="anonymous"`) and no referrer (`referrerpolicy="no-referrer"`). Legal basis given: Art. 6 (1) (f) GDPR; the US transfer is named as such. **A source added in the admin adds a host: add it to section 3 of the notice.** |
| Collections | Name, description, selected assets (metadata snapshots), creation and change times. Public at their URL. Optional creator email, never published. Stored in `data/curator.db` until deleted by the creator or an admin. |
| Email | Only if a creator enters an address: sign-in links (valid 15 minutes, single use) and the edit link, when a collection is created and again on request. Sent through the SMTP provider set in the admin — name it in `legal.ts` (`emailProvider`). |
| Sessions | After sign-in: session cookie (`HttpOnly`, 30 days). Stored server-side with the email address. |
| Browser storage | `localStorage`: the current selection, the visitor's collections with their edit keys, the appearance setting (`curator-theme`). Set only by the visitor's own actions, nothing for analytics or tracking. Strictly necessary under § 25 (2) No. 2 TDDDG — **no cookie consent needed.** |
| Submission | "Submit to IMPULSE" opens the visitor's own email program; the Curator does not send that email. |
| Not used | No analytics, no tracking, no advertising, no third-party scripts, fonts or embeds (fonts and the 3D viewer's code are self-hosted; the CSP allows scripts only from the site itself, and connections only to it and to `https:` archives — images, and the model file when a visitor opens the 3D viewer). |

Not stated, because not needed as things stand: a data protection officer (appoint one and add the contact if the law requires it), a named supervisory authority (the notice points to the right to complain; name the authority of the provider's federal state if you prefer).

If analytics or embeds (videos, maps) are ever added, consent becomes necessary and the CSP (`frontend/vite.config.ts`) has to be widened — both deliberately.

## Terms of use

Written for what the service is: free, a research prototype, collections public at their URL, names and descriptions the creator's responsibility, rights in the assets with the archives, licences to be respected by whoever uses the works (the collection page lists them), moderation with reasons, liability limited to what German law allows for a free service, German law. Mandatory consumer protections are left untouched.

## Accessibility

Only mandatory for public-sector bodies (EU Directive 2016/2102) and for services under the European Accessibility Act; the statement says it is voluntary. Facts: target WCAG 2.2 AA; automated checks (axe-core) report no violations on any page or dialog, in light and dark appearance; no manual audit yet; keyboard use throughout; known limitation that archive images rarely have text alternatives. Feedback goes to the contact email; the stated response time is two weeks.

## Report content (Art. 16 DSA)

The page names the report address (`reportEmail` in `legal.ts`), what a report needs, offers a template, and says what happens next: confirmation, review within a few days, unlist / lock / delete, outcome to the reporter, reasons to the creator where reachable.

## Other places with legal wording

- The EU funding disclaimer in the footer (`frontend/src/lib/components/SiteFooter.svelte`) and the imprint name the European Research Executive Agency (REA) as granting authority — confirm it against the grant agreement.
- The EU emblem (`frontend/static/brand/eu-funded-*.png`) is the official file, unmodified.
- The developer credit (`frontend/src/lib/components/DeveloperCredit.svelte`) links to the institute's website.

---

_Continue to the [docs index](README.md)._
