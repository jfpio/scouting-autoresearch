// Share the site's existing theme preference. The standalone page also follows Auto.
(() => {
  const media = matchMedia('(prefers-color-scheme: dark)');
  const apply = () => {
    let theme;
    try {
      theme = window.parent !== window ? window.parent.document.documentElement.dataset.theme : null;
      theme ||= localStorage.getItem('starlight-theme');
    } catch { /* The system preference is available even with storage disabled. */ }
    document.documentElement.dataset.theme = theme === 'dark' || (theme !== 'light' && media.matches) ? 'dark' : 'light';
    document.dispatchEvent(new Event('mapThemeChanged'));
  };
  apply();
  media.addEventListener('change', apply);
  window.addEventListener('storage', apply);
  try {
    if (window.parent !== window) new MutationObserver(apply).observe(window.parent.document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
  } catch { /* Standalone remains usable without access to a parent. */ }
})();
