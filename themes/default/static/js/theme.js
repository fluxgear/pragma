(() => {
  const root = document.documentElement;
  const toggle = document.getElementById('theme-toggle');
  const storageKey = 'pragma-theme-mode';

  const systemMode = () => (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

  const applyMode = (mode) => {
    root.setAttribute('data-bs-theme', mode);
    if (!toggle) {
      return;
    }
    toggle.setAttribute('aria-pressed', String(mode === 'dark'));
    const value = toggle.querySelector('.theme-toggle__value');
    if (value) {
      value.textContent = mode === 'dark' ? 'Dark' : 'Light';
    }
  };

  let mode = systemMode();
  try {
    const stored = window.localStorage.getItem(storageKey);
    if (stored === 'light' || stored === 'dark') {
      mode = stored;
    }
  } catch (error) {
    mode = systemMode();
  }

  applyMode(mode);

  if (toggle) {
    toggle.addEventListener('click', () => {
      mode = root.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
      applyMode(mode);
      try {
        window.localStorage.setItem(storageKey, mode);
      } catch (error) {
        return;
      }
    });
  }
})();
