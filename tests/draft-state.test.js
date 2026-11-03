'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {bindPublicationFields, hasPendingPublicationUrl, sectionDiffers, withInertTargets, verifiedCopyText} = require('../newsroom/static/draft-state.js');

test('copy requires the same currently valid approval and the same segment', () => {
  const shown = {approval_id: 4, posts: ['đoạn cũ', 'nguồn']};
  assert.equal(verifiedCopyText(shown, {approval_id: 4, posts: ['đoạn cũ', 'nguồn']}, 0), 'đoạn cũ');
  for (const current of [{approval_id: 5, posts: shown.posts},
                         {approval_id: 4, posts: ['đoạn khác']},
                         {approval_id: 4, posts: []}, {posts: shown.posts}]) {
    assert.throws(() => verifiedCopyText(shown, current, 0), /thay đổi/);
  }
});

test('pending bulletin action blocks editor, list and navigation and restores them on failure', async () => {
  const targets = [{inert: false}, {inert: false}, {inert: true}];
  let release;
  const pending = withInertTargets(targets, () => new Promise((resolve, reject) => { release = reject; }));
  assert.deepEqual(targets.map(target => target.inert), [true, true, true]);
  release(new Error('thử lỗi'));
  await assert.rejects(pending, /thử lỗi/);
  assert.deepEqual(targets.map(target => target.inert), [false, false, true]);
});

test('opening a bulletin keeps its editor and list inert until the response arrives', async () => {
  const editor = {inert: false};
  const list = {inert: false};
  let finish;
  const pending = withInertTargets([editor, list], () => new Promise(resolve => { finish = resolve; }));
  assert.equal(editor.inert, true);
  assert.equal(list.inert, true);
  finish('loaded');
  assert.equal(await pending, 'loaded');
  assert.equal(editor.inert, false);
  assert.equal(list.inert, false);
});

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

test('restoring all original values clears a section dirty flag', () => {
  const fields = [{value: 'Ban đầu'}, {value: '2026-11-03'}, {type: 'checkbox', checked: false}];
  const original = ['Ban đầu', '2026-11-03', false];
  assert.equal(sectionDiffers(fields, original), false);
  fields[0].value = 'Đã sửa';
  assert.equal(sectionDiffers(fields, original), true);
  fields[0].value = 'Ban đầu';
  fields[2].checked = true;
  assert.equal(sectionDiffers(fields, original), true);
  fields[2].checked = false;
  assert.equal(sectionDiffers(fields, original), false);
});
