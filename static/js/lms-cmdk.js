/* SFLL-117 — ⌘K command palette.
 *
 * Opens on ⌘K / Ctrl+K, fetches search results from the server
 * endpoint configured on #lms-cmdk[data-url], applies a small
 * client-side fuzzy score, and navigates on Enter / click.
 *
 * Result shape from the server:
 *   { pages: [...], players: [...], families: [...] }
 * where each item is { title, url, subtitle?, kind? }.
 */
(function () {
  'use strict';

  var DEBOUNCE_MS = 120;
  var MAX_PER_GROUP = 8;
  var GROUP_ORDER = [
    { key: 'pages',    label: 'Pages' },
    { key: 'players',  label: 'Players' },
    { key: 'families', label: 'Families' },
  ];

  function scoreItem(item, query) {
    if (!query) return 0;
    var q = query.toLowerCase();
    var hay = (item.title + ' ' + (item.subtitle || '')).toLowerCase();
    if (hay === q) return 100;
    if (hay.startsWith(q)) return 90;
    var idx = hay.indexOf(q);
    if (idx !== -1) return 70 - Math.min(idx, 40);
    /* subsequence match — every char in q appears in order in hay */
    var hi = 0, qi = 0, hits = 0;
    while (hi < hay.length && qi < q.length) {
      if (hay[hi] === q[qi]) { hits++; qi++; }
      hi++;
    }
    if (qi === q.length) return 30 + hits;
    return -1;
  }

  function rank(items, query) {
    if (!query) return items.slice(0, MAX_PER_GROUP);
    var scored = [];
    for (var i = 0; i < items.length; i++) {
      var s = scoreItem(items[i], query);
      if (s >= 0) scored.push({ item: items[i], score: s, idx: i });
    }
    scored.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.idx - b.idx;
    });
    return scored.slice(0, MAX_PER_GROUP).map(function (s) { return s.item; });
  }

  function renderResults(container, data, query) {
    container.innerHTML = '';
    var flat = [];
    GROUP_ORDER.forEach(function (group) {
      var items = rank((data[group.key] || []), query);
      if (!items.length) return;
      var section = document.createElement('div');
      section.className = 'lms-cmdk__group';
      var label = document.createElement('div');
      label.className = 'lms-cmdk__group-label';
      label.textContent = group.label;
      section.appendChild(label);
      items.forEach(function (item) {
        var idx = flat.length;
        var el = document.createElement('a');
        el.className = 'lms-cmdk__item';
        el.href = item.url;
        el.setAttribute('data-idx', String(idx));
        var title = document.createElement('div');
        title.className = 'lms-cmdk__item-title';
        var name = document.createElement('div');
        name.className = 'lms-cmdk__item-name';
        name.textContent = item.title;
        title.appendChild(name);
        if (item.subtitle) {
          var sub = document.createElement('div');
          sub.className = 'lms-cmdk__item-sub';
          sub.textContent = item.subtitle;
          title.appendChild(sub);
        }
        el.appendChild(title);
        var kind = document.createElement('span');
        kind.className = 'lms-cmdk__item-kind';
        kind.textContent = item.kind || group.label.toLowerCase();
        el.appendChild(kind);
        section.appendChild(el);
        flat.push({ el: el, url: item.url });
      });
      container.appendChild(section);
    });

    if (!flat.length) {
      var empty = document.createElement('div');
      empty.className = 'lms-cmdk__empty';
      var strong = document.createElement('strong');
      strong.textContent = 'Nothing matched.';
      empty.appendChild(strong);
      empty.appendChild(document.createTextNode(
        query ? 'Try a name, a page, or a partial match.' : 'Start typing to search.'
      ));
      container.appendChild(empty);
    }
    return flat;
  }

  function setActive(flat, idx) {
    flat.forEach(function (entry, i) {
      entry.el.setAttribute('data-active', i === idx ? 'true' : 'false');
      if (i === idx) {
        entry.el.scrollIntoView({ block: 'nearest' });
      }
    });
  }

  function init() {
    var modal = document.getElementById('lms-cmdk');
    if (!modal) return;
    var scrim = document.getElementById('lms-cmdk-scrim');
    var input = modal.querySelector('.lms-cmdk__input');
    var results = modal.querySelector('.lms-cmdk__results');
    var url = modal.getAttribute('data-url');
    var trigger = document.getElementById('lms-cmdk-trigger');

    var data = { pages: [], players: [], families: [] };
    var flat = [];
    var activeIdx = 0;
    var query = '';
    var pending = null;
    var loaded = false;

    function refresh() {
      flat = renderResults(results, data, query);
      activeIdx = 0;
      setActive(flat, activeIdx);
    }

    function fetchData(q) {
      if (!url) return Promise.resolve(data);
      var endpoint = url + (url.indexOf('?') === -1 ? '?' : '&') + 'q=' + encodeURIComponent(q || '');
      return fetch(endpoint, {
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
      }).then(function (resp) {
        if (!resp.ok) throw new Error('cmdk search ' + resp.status);
        return resp.json();
      });
    }

    function open() {
      if (scrim) scrim.hidden = false;
      modal.hidden = false;
      input.value = '';
      query = '';
      input.focus();
      if (!loaded) {
        fetchData('').then(function (json) {
          data = json || data;
          loaded = true;
          refresh();
        }).catch(function () { refresh(); });
      } else {
        refresh();
      }
    }

    function close() {
      if (scrim) scrim.hidden = true;
      modal.hidden = true;
    }

    function isOpen() {
      return !modal.hidden;
    }

    if (scrim) scrim.addEventListener('click', function (ev) {
      if (ev.target === scrim) close();
    });
    if (trigger) trigger.addEventListener('click', open);

    input.addEventListener('input', function () {
      query = input.value.trim();
      if (pending) clearTimeout(pending);
      pending = setTimeout(function () {
        fetchData(query).then(function (json) {
          data = json || data;
          refresh();
        }).catch(function () { refresh(); });
      }, DEBOUNCE_MS);
    });

    modal.addEventListener('click', function (ev) {
      if (ev.target.closest('.lms-cmdk__item')) {
        /* let the anchor navigate; close on next tick so scrim doesn't trap focus */
        setTimeout(close, 0);
      }
    });

    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'k' && (ev.metaKey || ev.ctrlKey)) {
        ev.preventDefault();
        if (isOpen()) close(); else open();
        return;
      }
      if (!isOpen()) return;
      if (ev.key === 'Escape') {
        ev.preventDefault();
        close();
      } else if (ev.key === 'ArrowDown') {
        ev.preventDefault();
        if (flat.length) {
          activeIdx = (activeIdx + 1) % flat.length;
          setActive(flat, activeIdx);
        }
      } else if (ev.key === 'ArrowUp') {
        ev.preventDefault();
        if (flat.length) {
          activeIdx = (activeIdx - 1 + flat.length) % flat.length;
          setActive(flat, activeIdx);
        }
      } else if (ev.key === 'Enter') {
        if (flat.length) {
          ev.preventDefault();
          window.location.href = flat[activeIdx].url;
        }
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
