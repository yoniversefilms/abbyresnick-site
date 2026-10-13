const test = require('node:test');
const assert = require('node:assert/strict');
const r = require('../assets/js/review.js');

test('PAGES lists the three live pages in site order with root-relative sources', () => {
  assert.deepEqual(r.PAGES.map((p) => p.key), ['home', 'corporate', 'portfolio']);
  assert.deepEqual(r.PAGES.map((p) => p.src), ['/index.html', '/corporate.html', '/portfolio.html']);
  assert.deepEqual(r.PAGES.map((p) => p.label), ['Home', 'Corporate', 'Portfolio']);
});

test('pageByKey falls back to home for unknown keys', () => {
  assert.equal(r.pageByKey('corporate').label, 'Corporate');
  assert.equal(r.pageByKey('nope').key, 'home');
  assert.equal(r.pageByKey(undefined).key, 'home');
});

test('pickMime prefers mp4 (plays everywhere) then opus webm, else empty for the browser default', () => {
  const only = (ok) => (m) => ok.indexOf(m) >= 0;
  assert.equal(r.pickMime(only(['audio/mp4', 'audio/webm'])), 'audio/mp4');
  assert.equal(r.pickMime(only(['audio/webm;codecs=opus', 'audio/webm'])), 'audio/webm;codecs=opus');
  assert.equal(r.pickMime(only(['audio/webm'])), 'audio/webm');
  assert.equal(r.pickMime(only([])), '');
  assert.equal(r.pickMime(null), '');
});

test('extFor maps container mime types to file extensions', () => {
  assert.equal(r.extFor('audio/mp4'), 'm4a');
  assert.equal(r.extFor('audio/mp4;codecs=mp4a.40.2'), 'm4a');
  assert.equal(r.extFor('audio/webm;codecs=opus'), 'webm');
  assert.equal(r.extFor('audio/ogg'), 'ogg');
  assert.equal(r.extFor(''), 'webm');
});

test('fmtDuration renders m:ss and clamps negatives', () => {
  assert.equal(r.fmtDuration(0), '0:00');
  assert.equal(r.fmtDuration(999), '0:00');
  assert.equal(r.fmtDuration(61000), '1:01');
  assert.equal(r.fmtDuration(600000), '10:00');
  assert.equal(r.fmtDuration(-5), '0:00');
});

test('clipName is deterministic per note, to the second, and safe for every target', () => {
  const at = new Date(2026, 9, 12, 14, 7, 9); // local time
  assert.equal(r.clipName({ page: 'home', startedAt: at.getTime(), mime: 'audio/mp4' }), 'abby-note-2026-10-12-140709-home.m4a');
  assert.equal(r.clipName({ page: 'portfolio', startedAt: at.getTime(), mime: 'audio/webm' }), 'abby-note-2026-10-12-140709-portfolio.webm');
  assert.equal(r.clipName({ page: 'home', startedAt: at.getTime() + 1000, mime: 'audio/mp4' }), 'abby-note-2026-10-12-140710-home.m4a');
  assert.match(r.clipName({ page: 'x y', startedAt: at.getTime(), mime: '' }), /^[a-z0-9.-]+$/);
});

test('pathToPage maps the framed site\'s pathname to a page key, null for anything else', () => {
  assert.equal(r.pathToPage('/'), 'home');
  assert.equal(r.pathToPage('/index.html'), 'home');
  assert.equal(r.pathToPage('/corporate.html'), 'corporate');
  assert.equal(r.pathToPage('/portfolio.html?x=1#corporate'), 'portfolio');
  assert.equal(r.pathToPage('/PORTFOLIO.HTML'), 'portfolio');
  assert.equal(r.pathToPage('/thank-you.html'), null);
  assert.equal(r.pathToPage('/404.html'), null);
  assert.equal(r.pathToPage(''), 'home');
  assert.equal(r.pathToPage(undefined), 'home');
});

test('pagesLabel joins the distinct pages visited during a note', () => {
  assert.equal(r.pagesLabel(['home']), 'Home');
  assert.equal(r.pagesLabel(['home', 'portfolio', 'portfolio', 'home']), 'Home → Portfolio');
  assert.equal(r.pagesLabel([]), 'Home');
});

test('clipName uses the page the note started on', () => {
  const at = new Date(2026, 9, 12, 14, 7, 9).getTime();
  assert.equal(r.clipName({ pages: ['corporate', 'home'], startedAt: at, mime: 'audio/mp4' }), 'abby-note-2026-10-12-140709-corporate.m4a');
});

test('uploadPayload carries the file, its name, and the note metadata', () => {
  const at = new Date(2026, 9, 12, 14, 7, 9).getTime();
  const p = r.uploadPayload({ id: String(at), pages: ['home', 'portfolio'], startedAt: at, durationMs: 4000, mime: 'audio/mp4', size: 99 }, 'QUJD');
  assert.equal(p.id, String(at));
  assert.equal(p.name, 'abby-note-2026-10-12-140709-home.m4a');
  assert.equal(p.data, 'QUJD');
  assert.equal(p.mime, 'audio/mp4');
  assert.equal(p.page, 'home');
  assert.deepEqual(p.pages, ['home', 'portfolio']);
  assert.equal(p.durationMs, 4000);
  assert.equal(p.size, 99);
  assert.equal(r.uploadPayload({ page: 'home', startedAt: at, mime: '', size: 1 }, 'x').mime, 'audio/mp4');
  assert.equal(r.uploadPayload({ page: 'home', startedAt: at, mime: '', size: 1 }, 'x').id, String(at));
});

test('statusText reflects the upload state', () => {
  assert.equal(r.statusText({}, false), '');
  assert.equal(r.statusText({ uploaded: true }, false), 'Sent');
  assert.equal(r.statusText({ uploaded: true }, true), 'Sent to Yonatan');
  assert.equal(r.statusText({ uploading: true }, true), 'Sending…');
  assert.equal(r.statusText({ failed: true }, true), 'Couldn’t send — will try again');
  assert.equal(r.statusText({}, true), 'Not sent yet');
});

test('isIOS spots iPhones, iPads (including desktop-mode Safari) and nothing else', () => {
  assert.equal(r.isIOS({ userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15' }), true);
  assert.equal(r.isIOS({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', maxTouchPoints: 5 }), true);
  assert.equal(r.isIOS({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', maxTouchPoints: 0 }), false);
  assert.equal(r.isIOS({ userAgent: 'Mozilla/5.0 (Linux; Android 14) Chrome/120' }), false);
  assert.equal(r.isIOS(null), false);
});

test('totalBytes sums clip sizes and tolerates missing sizes', () => {
  assert.equal(r.totalBytes([{ size: 10 }, { size: 20 }, {}]), 30);
  assert.equal(r.totalBytes([]), 0);
});

test('fmtBytes is human readable', () => {
  assert.equal(r.fmtBytes(0), '0 KB');
  assert.equal(r.fmtBytes(512 * 1024), '512 KB');
  assert.equal(r.fmtBytes(3.5 * 1024 * 1024), '3.5 MB');
});

test('canShareFiles requires navigator.share + canShare agreeing on the files', () => {
  const files = [{ name: 'a' }];
  assert.equal(r.canShareFiles({ share() {}, canShare: (d) => !!d.files }, files), true);
  assert.equal(r.canShareFiles({ share() {}, canShare: () => false }, files), false);
  assert.equal(r.canShareFiles({ share() {} }, files), false);
  assert.equal(r.canShareFiles({}, files), false);
  assert.equal(r.canShareFiles(null, files), false);
  assert.equal(r.canShareFiles({ share() {}, canShare: () => true }, []), false);
});

test('shareText summarises the batch for the message body', () => {
  const t = r.shareText([{ page: 'home', durationMs: 60000 }, { page: 'portfolio', durationMs: 30000 }]);
  assert.match(t, /2 voice notes/);
  assert.match(t, /abbyresnick\.com/);
  assert.match(t, /1:30/);
  assert.match(r.shareText([{ page: 'home', durationMs: 1000 }]), /1 voice note /);
});
