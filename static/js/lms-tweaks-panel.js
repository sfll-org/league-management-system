/* SFLL-117 — Tweaks panel.
 *
 * Reads/writes the four design-time knobs that swap CSS-variable
 * blocks defined in lms-tokens.css + lms-tweaks-cmdk.css:
 *
 *   data-palette   pacific | civic | fog | twilight
 *   data-type      humanist-display | humanist-plain | geometric | editorial
 *   data-density   balanced | compact | airy
 *   data-nav       side | top
 *
 * Persistence is per-browser via localStorage. The FOUC-free preload
 * happens in base.html via an inline script — this module owns the
 * panel UI itself plus the keyboard shortcut to open it (Shift+⌘.).
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'sfll.tweaks.v1';
  var DEFAULTS = {
    palette: 'pacific',
    type: 'humanist-display',
    density: 'balanced',
    nav: 'side',
  };

  function load() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return Object.assign({}, DEFAULTS);
      var parsed = JSON.parse(raw);
      return Object.assign({}, DEFAULTS, parsed || {});
    } catch (e) {
      return Object.assign({}, DEFAULTS);
    }
  }

  function save(state) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {
      /* localStorage disabled — apply for this page load only. */
    }
  }

  function apply(state) {
    var html = document.documentElement;
    html.setAttribute('data-palette', state.palette);
    html.setAttribute('data-type', state.type);
    html.setAttribute('data-density', state.density);
    html.setAttribute('data-nav', state.nav);
  }

  function syncButtons(panel, state) {
    var buttons = panel.querySelectorAll('.lms-tweaks__opt');
    buttons.forEach(function (btn) {
      var group = btn.getAttribute('data-group');
      var value = btn.getAttribute('data-value');
      btn.setAttribute('data-active', state[group] === value ? 'true' : 'false');
    });
  }

  function init() {
    var panel = document.getElementById('lms-tweaks');
    if (!panel) return;
    var trigger = document.getElementById('lms-tweaks-trigger');
    var closeBtn = panel.querySelector('.lms-tweaks__close');
    var resetBtn = panel.querySelector('.lms-tweaks__reset');

    var state = load();
    apply(state);
    syncButtons(panel, state);

    function open() { panel.setAttribute('data-open', 'true'); }
    function close() { panel.setAttribute('data-open', 'false'); }
    function toggle() {
      if (panel.getAttribute('data-open') === 'true') close(); else open();
    }

    if (trigger) trigger.addEventListener('click', toggle);
    if (closeBtn) closeBtn.addEventListener('click', close);

    panel.addEventListener('click', function (ev) {
      var btn = ev.target.closest('.lms-tweaks__opt');
      if (!btn) return;
      var group = btn.getAttribute('data-group');
      var value = btn.getAttribute('data-value');
      if (!group || !value) return;
      state[group] = value;
      save(state);
      apply(state);
      syncButtons(panel, state);
    });

    if (resetBtn) {
      resetBtn.addEventListener('click', function () {
        state = Object.assign({}, DEFAULTS);
        save(state);
        apply(state);
        syncButtons(panel, state);
      });
    }

    /* Keyboard: Shift+Cmd+. / Shift+Ctrl+. opens the panel. */
    document.addEventListener('keydown', function (ev) {
      if (ev.key === '.' && ev.shiftKey && (ev.metaKey || ev.ctrlKey)) {
        ev.preventDefault();
        toggle();
      } else if (ev.key === 'Escape' && panel.getAttribute('data-open') === 'true') {
        close();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
