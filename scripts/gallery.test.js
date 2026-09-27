const test = require('node:test');
const assert = require('node:assert/strict');
const g = require('../assets/js/gallery.js');

const items = [
  { id: 'a', cat: 'installations' }, { id: 'b', cat: 'corporate' },
  { id: 'c', cat: 'installations' }, { id: 'd', cat: 'studio' },
];

test('categoriesFrom keeps first-seen order and dedupes', () => {
  assert.deepEqual(g.categoriesFrom(items), ['installations', 'corporate', 'studio']);
});

test('hashToCategory maps known hashes and falls back to all', () => {
  const known = ['installations', 'corporate', 'studio'];
  assert.equal(g.hashToCategory('#corporate', known), 'corporate');
  assert.equal(g.hashToCategory('#CORPORATE', known), 'corporate');
  assert.equal(g.hashToCategory('#weddings', known), 'all');
  assert.equal(g.hashToCategory('#foo', known), 'all');
  assert.equal(g.hashToCategory('', known), 'all');
  assert.equal(g.hashToCategory('#', known), 'all');
  assert.equal(g.hashToCategory(undefined, known), 'all');
});

test('hashToItem extracts an item id', () => {
  assert.equal(g.hashToItem('#item-teq-table-wide'), 'teq-table-wide');
  assert.equal(g.hashToItem('#corporate'), null);
  assert.equal(g.hashToItem(''), null);
});

test('filterItems respects the active category', () => {
  assert.deepEqual(g.filterItems(items, 'all').map(i => i.id), ['a', 'b', 'c', 'd']);
  assert.deepEqual(g.filterItems(items, 'installations').map(i => i.id), ['a', 'c']);
  assert.deepEqual(g.filterItems(items, 'weddings'), []);
});

test('nextIndex wraps both ways within the filtered length', () => {
  assert.equal(g.nextIndex(1, 2, 1), 0);
  assert.equal(g.nextIndex(0, 2, -1), 1);
  assert.equal(g.nextIndex(0, 1, 1), 0);
  assert.equal(g.nextIndex(0, 0, 1), 0);
});

test('LABELS covers every category', () => {
  for (const c of ['installations', 'corporate', 'private', 'studio', 'weddings']) assert.ok(g.LABELS[c]);
});
