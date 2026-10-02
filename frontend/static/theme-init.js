// Apply the appearance the visitor chose (Dark is the default) before the
// first paint. Kept tiny and external so the Content Security Policy needs no
// inline script.
(function () {
	try {
		var theme = localStorage.getItem('curator-theme');
		if (theme === 'light' || theme === 'system') {
			document.documentElement.setAttribute('data-theme', theme);
		}
	} catch {
		/* storage unavailable: keep the default */
	}
})();
