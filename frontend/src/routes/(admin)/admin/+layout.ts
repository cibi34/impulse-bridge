// Admin pages talk to the admin API only; they render in the browser.
// In production, /admin (pages and API) sits behind the proxy's basic auth.
export const ssr = false;
