/* Portfolio gallery: category chips, hash deep-links, native <dialog> lightbox.
   Pure helpers are exported for `node --test`; DOM wiring runs only in a browser. No dependencies. */
(function (root) {
  'use strict';
  var LABELS = { installations: 'Installations', corporate: 'Corporate', private: 'Private Events', studio: 'Studio', weddings: 'Weddings' };

  function categoriesFrom(items) {
    var seen = [];
    for (var i = 0; i < items.length; i++) if (seen.indexOf(items[i].cat) < 0) seen.push(items[i].cat);
    return seen;
  }
  function hashToCategory(hash, known) {
    var h = String(hash || '').replace(/^#/, '').toLowerCase();
    return known.indexOf(h) >= 0 ? h : 'all';
  }
  function hashToItem(hash) {
    var m = /^#item-([a-z0-9-]+)$/i.exec(String(hash || ''));
    return m ? m[1] : null;
  }
  function filterItems(items, cat) {
    return items.filter(function (it) { return cat === 'all' || it.cat === cat; });
  }
  function nextIndex(i, n, dir) {
    return n === 0 ? 0 : ((i + dir) % n + n) % n;
  }

  var api = { LABELS: LABELS, categoriesFrom: categoriesFrom, hashToCategory: hashToCategory, hashToItem: hashToItem, filterItems: filterItems, nextIndex: nextIndex };
  if (typeof module !== 'undefined' && module.exports) { module.exports = api; return; }
  if (typeof document === 'undefined') return;

  /* ---------- DOM wiring ---------- */
  var grid = document.getElementById('pfGrid'); if (!grid) return;
  var tiles = Array.prototype.slice.call(grid.querySelectorAll('.pf-tile'));
  var items = tiles.map(function (el) {
    var img = el.querySelector('img');
    return { id: el.id.replace(/^item-/, ''), cat: el.getAttribute('data-cat'), el: el, src: el.getAttribute('href'), alt: img ? img.alt : '' };
  });
  var known = categoriesFrom(items);
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
  var count = document.querySelector('.pf-count');
  var current = 'all', visible = items.slice();

  function applyFilter(cat, pushHash) {
    current = cat; visible = filterItems(items, cat);
    items.forEach(function (it) { it.el.hidden = visible.indexOf(it) < 0; });
    chips.forEach(function (c) { c.setAttribute('aria-pressed', String(c.getAttribute('data-cat') === cat)); });
    if (count) count.textContent = visible.length + (visible.length === 1 ? ' piece' : ' pieces') + (cat === 'all' ? '' : ' · ' + LABELS[cat]);
    if (pushHash && history.replaceState) history.replaceState(null, '', cat === 'all' ? location.pathname : '#' + cat);
  }
  chips.forEach(function (c) { c.addEventListener('click', function () { applyFilter(c.getAttribute('data-cat'), true); }); });

  /* lightbox */
  var dlg = document.getElementById('lightbox');
  var lbImg = document.getElementById('lbImg'), lbCap = document.getElementById('lbCap'), lbCat = document.getElementById('lbCat');
  var idx = 0, lastFocus = null;
  var canDialog = dlg && typeof dlg.showModal === 'function';

  function show(i) {
    idx = i; var it = visible[idx]; if (!it) return;
    lbImg.src = it.src; lbImg.alt = it.alt; lbCap.textContent = it.alt; lbCat.textContent = LABELS[it.cat] || '';
    var pre = new Image(); pre.src = visible[nextIndex(idx, visible.length, 1)].src;
  }
  function open(it) {
    if (!canDialog) return false;
    lastFocus = it.el; show(visible.indexOf(it)); dlg.showModal(); dlg.querySelector('.lb__close').focus(); return true;
  }
  function close() { if (dlg.open) dlg.close(); }
  if (canDialog) {
    items.forEach(function (it) { it.el.addEventListener('click', function (e) { if (open(it)) e.preventDefault(); }); });
    dlg.querySelector('.lb__close').addEventListener('click', close);
    dlg.querySelector('.lb__prev').addEventListener('click', function () { show(nextIndex(idx, visible.length, -1)); });
    dlg.querySelector('.lb__next').addEventListener('click', function () { show(nextIndex(idx, visible.length, 1)); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg || e.target.classList.contains('lb__inner')) close(); });
    dlg.addEventListener('close', function () {
      lbImg.src = '';
      if (!lastFocus) return;
      /* a hash change can filter the opening tile out while the dialog is up: fall back to the first visible tile */
      var back = (lastFocus.hidden || lastFocus.offsetParent === null) ? tiles.filter(function (t) { return !t.hidden && t.offsetParent !== null; })[0] : lastFocus;
      if (back) back.focus();
    });
    dlg.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') { show(nextIndex(idx, visible.length, 1)); e.preventDefault(); }
      else if (e.key === 'ArrowLeft') { show(nextIndex(idx, visible.length, -1)); e.preventDefault(); }
    });
    var tx = null;
    dlg.addEventListener('touchstart', function (e) { tx = e.changedTouches[0].clientX; }, { passive: true });
    dlg.addEventListener('touchend', function (e) {
      if (tx === null) return; var dx = e.changedTouches[0].clientX - tx; tx = null;
      if (Math.abs(dx) >= 40) show(nextIndex(idx, visible.length, dx < 0 ? 1 : -1));
    }, { passive: true });
  }

  /* initial state from the hash */
  var itemId = hashToItem(location.hash);
  applyFilter(hashToCategory(location.hash, known), false);
  if (itemId) {
    var target = items.filter(function (it) { return it.id === itemId; })[0];
    if (target) { target.el.scrollIntoView({ block: 'center' }); open(target); }
  }
  window.addEventListener('hashchange', function () { if (canDialog) close(); applyFilter(hashToCategory(location.hash, known), false); });
})(this);
