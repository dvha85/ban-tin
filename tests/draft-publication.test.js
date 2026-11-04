'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {bindPublicationFields, hasPendingPublicationUrl} = require('../newsroom/static/draft-publication.js');

function fields() {
  return {input: {value: ''}, link: {href: '', removeAttribute() { this.href = ''; }}};
}
test('publication URL stays with its draft, including after recording', () => {
  const {input, link} = fields();
  const a = {id: 1, status: 'approved'}, b = {id: 2, status: 'approved'};
  bindPublicationFields(null, a, input, link);
  input.value = 'https://www.facebook.com/page/posts/111';
  assert.equal(hasPendingPublicationUrl(a, input), true);
  const posted = {...a, status: 'published', post_url: input.value};
  bindPublicationFields(a, posted, input, link);
  assert.equal(input.value, ''); assert.equal(link.href, posted.post_url);
  bindPublicationFields(posted, b, input, link);
  assert.equal(input.value, ''); assert.equal(link.href, '');
  bindPublicationFields(b, posted, input, link);
  assert.equal(link.href, posted.post_url);
});
test('unsent URL survives refresh of same draft and clears when switching', () => {
  const {input, link} = fields();
  const a = {id: 1, status: 'approved'}, b = {id: 2, status: 'approved'};
  input.value = 'https://www.facebook.com/page/posts/111';
  bindPublicationFields(a, {...a, revision: 2}, input, link);
  assert.equal(input.value, 'https://www.facebook.com/page/posts/111');
  assert.equal(hasPendingPublicationUrl(a, input), true);
  bindPublicationFields(a, b, input, link);
  assert.equal(input.value, ''); assert.equal(hasPendingPublicationUrl(b, input), false);
});
test('an unsent URL is discarded when approval is revoked on the same draft', () => {
  const {input, link} = fields();
  const approved = {id: 1, status: 'approved'};
  input.value = 'https://www.facebook.com/page/posts/111';
  const edited = {...approved, status: 'draft'};
  bindPublicationFields(approved, edited, input, link);
  assert.equal(input.value, '');
  bindPublicationFields(edited, approved, input, link);
  assert.equal(input.value, '');
  assert.equal(hasPendingPublicationUrl(approved, input), false);
});
