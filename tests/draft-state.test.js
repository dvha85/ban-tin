'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {bindPublicationFields, hasPendingPublicationUrl} = require('../newsroom/static/draft-state.js');

function fields() {
  return {input: {value: ''}, link: {href: '', removeAttribute(name) { if (name === 'href') this.href = ''; }}};
}

test('publication URL follows the selected draft, including after publication', () => {
  const {input, link} = fields();
  const first = {id: 1, status: 'approved'};
  const second = {id: 2, status: 'approved'};
  bindPublicationFields(null, first, input, link);
  input.value = 'https://www.facebook.com/page/posts/111';
  assert.equal(hasPendingPublicationUrl(first, input), true);
  const posted = {...first, status: 'published', post_url: input.value};
  bindPublicationFields(first, posted, input, link);
  assert.equal(input.value, '');
  assert.equal(link.href, posted.post_url);
  bindPublicationFields(posted, second, input, link);
  assert.equal(input.value, '');
  assert.equal(link.href, '');
  bindPublicationFields(second, posted, input, link);
  assert.equal(link.href, posted.post_url);
});

test('unsubmitted URL is preserved on refresh of same draft, cleared on switch', () => {
  const {input, link} = fields();
  const first = {id: 1, status: 'approved'};
  input.value = 'https://www.facebook.com/page/posts/111';
  bindPublicationFields(first, {...first, revision: 2}, input, link);
  assert.equal(hasPendingPublicationUrl(first, input), true);
  assert.match(input.value, /111/);
  bindPublicationFields(first, {id: 2, status: 'approved'}, input, link);
  assert.equal(input.value, '');
  assert.equal(hasPendingPublicationUrl({id: 2, status: 'approved'}, input), false);
});
