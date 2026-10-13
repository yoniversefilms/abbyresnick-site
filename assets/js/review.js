/* Site review recorder (review/index.html): Abby records voice notes while browsing the live site.
   Pure helpers are exported for `node --test`; the DOM wiring lives in review/index.html. No dependencies. */
(function (root) {
  'use strict';

  var PAGES = [
    { key: 'home', label: 'Home', src: '/index.html' },
    { key: 'corporate', label: 'Corporate', src: '/corporate.html' },
    { key: 'portfolio', label: 'Portfolio', src: '/portfolio.html' }
  ];
  var MIME_PREFS = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm'];

  function pageByKey(key) {
    for (var i = 0; i < PAGES.length; i++) if (PAGES[i].key === key) return PAGES[i];
    return PAGES[0];
  }
  /* Maps a same-origin pathname (what the framed site navigated to) to a page key, or null for
     anything that is not one of the three reviewed pages (thank-you, 404, external). */
  function pathToPage(pathname) {
    var p = String(pathname || '').split('?')[0].split('#')[0].toLowerCase();
    if (p === '' || p === '/' || p === '/index.html' || p === '/index') return 'home';
    for (var i = 1; i < PAGES.length; i++) {
      if (p === PAGES[i].src || p === '/' + PAGES[i].key || p === '/' + PAGES[i].key + '/') return PAGES[i].key;
    }
    return null;
  }
  function pagesLabel(keys) {
    var seen = [], out = [];
    (keys || []).forEach(function (k) { if (seen.indexOf(k) < 0) { seen.push(k); out.push(pageByKey(k).label); } });
    return out.length ? out.join(' → ') : PAGES[0].label;
  }
  function pickMime(isSupported) {
    if (typeof isSupported !== 'function') return '';
    for (var i = 0; i < MIME_PREFS.length; i++) if (isSupported(MIME_PREFS[i])) return MIME_PREFS[i];
    return '';
  }
  function extFor(mime) {
    var m = String(mime || '').toLowerCase();
    if (m.indexOf('mp4') >= 0 || m.indexOf('aac') >= 0) return 'm4a';
    if (m.indexOf('ogg') >= 0) return 'ogg';
    return 'webm';
  }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function fmtDuration(ms) {
    var s = Math.max(0, Math.floor((Number(ms) || 0) / 1000));
    return Math.floor(s / 60) + ':' + pad2(s % 60);
  }
  function fmtClock(ts) {
    var d = new Date(ts), h = d.getHours(), m = d.getMinutes();
    var h12 = h % 12 === 0 ? 12 : h % 12;
    return h12 + ':' + pad2(m) + ' ' + (h < 12 ? 'AM' : 'PM');
  }
  function fmtStamp(ts) {
    var d = new Date(ts);
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + '-' + pad2(d.getHours()) + pad2(d.getMinutes()) + pad2(d.getSeconds());
  }
  function slug(s) { return String(s || 'page').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'page'; }
  /* Deterministic per note (start time to the second + page it started on): sorts chronologically in Drive
     and lets the upload endpoint skip a repeat of the same note. */
  function clipName(clip) {
    var first = (clip.pages && clip.pages[0]) || clip.page;
    return 'abby-note-' + fmtStamp(clip.startedAt) + '-' + slug(first) + '.' + extFor(clip.mime);
  }
  function totalBytes(clips) {
    var t = 0;
    for (var i = 0; i < clips.length; i++) t += Number(clips[i].size) || 0;
    return t;
  }
  function fmtBytes(n) {
    if (n >= 1024 * 1024) return (Math.round(n / (1024 * 1024) * 10) / 10) + ' MB';
    return Math.round(n / 1024) + ' KB';
  }
  function canShareFiles(nav, files) {
    if (!nav || typeof nav.share !== 'function' || typeof nav.canShare !== 'function') return false;
    if (!files || !files.length) return false;
    try { return !!nav.canShare({ files: files }); } catch (e) { return false; }
  }
  function shareText(clips) {
    var total = 0;
    for (var i = 0; i < clips.length; i++) total += Number(clips[i].durationMs) || 0;
    return clips.length + ' voice note' + (clips.length === 1 ? '' : 's') + ' on abbyresnick.com (' + fmtDuration(total) + ' total)';
  }
  /* The JSON body posted to the upload endpoint (Google Apps Script → Drive). `data` is base64. */
  function uploadPayload(clip, base64) {
    return {
      id: String(clip.id || clip.startedAt), name: clipName(clip), mime: clip.mime || 'audio/mp4', data: base64,
      page: (clip.pages && clip.pages[0]) || clip.page, pages: clip.pages || [clip.page],
      startedAt: clip.startedAt, durationMs: clip.durationMs, size: clip.size
    };
  }
  /* Status line for a note in the list. */
  function statusText(clip, hasEndpoint) {
    if (!hasEndpoint) return clip.uploaded ? 'Sent' : '';
    if (clip.uploaded) return 'Sent to Yonatan';
    if (clip.uploading) return 'Sending…';
    if (clip.failed) return 'Couldn’t send — will try again';
    return 'Not sent yet';
  }
  function isIOS(nav) {
    var ua = (nav && nav.userAgent) || '', touchMac = /Macintosh/.test(ua) && nav && nav.maxTouchPoints > 1;
    return /iPhone|iPad|iPod/.test(ua) || !!touchMac;
  }

  var api = {
    PAGES: PAGES, pageByKey: pageByKey, pathToPage: pathToPage, pagesLabel: pagesLabel, pickMime: pickMime, extFor: extFor,
    fmtDuration: fmtDuration, fmtClock: fmtClock, clipName: clipName, totalBytes: totalBytes, fmtBytes: fmtBytes,
    canShareFiles: canShareFiles, shareText: shareText, uploadPayload: uploadPayload, statusText: statusText, isIOS: isIOS
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Review = api;
})(this);
