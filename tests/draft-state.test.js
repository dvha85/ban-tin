'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {bindPublicationFields, hasPendingPublicationUrl, sectionDiffers, withInertTargets, verifiedCopyText, conflictTargetUrl, parseConflictTarget, sourceRelevanceWarning, platformLengthNotice, focusMovedItem, claimConflictDetails, hasOtherPendingChanges, metricFields, metricDisplayFields} = require('../newsroom/static/draft-state.js');

test('platform metrics differ while recorded legacy values remain visible', () => {
  assert.ok(metricFields('x').some(([key]) => key === 'reposts'));
  assert.ok(metricFields('threads').some(([key]) => key === 'replies'));
  assert.equal(metricFields('facebook').some(([key]) => key === 'reposts'), false);
  assert.ok(metricDisplayFields('x', {shares: 0}).some(([key]) => key === 'shares'));
  assert.equal(metricDisplayFields('x', {shares: null}).some(([key]) => key === 'shares'), false);
});

test('retry or discard of a correction respects other unsaved sections and URLs', () => {
  const own = {}, other = {};
  const editor = {querySelectorAll: () => [own]};
  assert.equal(hasOtherPendingChanges(editor, own, false), false);
  assert.equal(hasOtherPendingChanges(editor, own, true), true);
  editor.querySelectorAll = () => [own, other];
  assert.equal(hasOtherPendingChanges(editor, own, false), true);
});

test('correction failures retain the entered reason and URL, including non-conflict errors', () => {
  const correction = {reason: 'Sửa liên kết', url: 'https://x.com/test/status/12'};
  const invalid = new Error('Liên kết không hợp lệ');
  assert.deepEqual(claimConflictDetails(invalid, correction), {message: invalid.message, href: null, correction});
  const conflict = Object.assign(new Error('Liên kết đã dùng'), {target: {kind: 'legacy_draft', draft_id: 7}});
  assert.deepEqual(claimConflictDetails(conflict, correction), {message: conflict.message, href: '/?kind=legacy_draft&draft_id=7', correction});
  assert.throws(() => claimConflictDetails(invalid, null), /Liên kết không hợp lệ/);
});

test('reordering returns focus to the moved item and uses the other direction at an edge', () => {
  const calls = [];
  const buttons = {up: {disabled: false, focus: () => calls.push('up')}, down: {disabled: false, focus: () => calls.push('down')}};
  const section = {dataset: {itemId: '42'}, querySelector: selector => buttons[selector.includes('up') ? 'up' : 'down']};
  const editor = {querySelectorAll: () => [section]};
  focusMovedItem(editor, 42, -1);
  buttons.up.disabled = true;
  focusMovedItem(editor, 42, -1);
  focusMovedItem(editor, 99, 1);
  assert.deepEqual(calls, ['up', 'down']);
});

test('channel editor explains limits and uncertainty before export', () => {
  assert.match(platformLengthNotice('threads'), /ước lượng.*kiểm tra/i);
  assert.match(platformLengthNotice('x'), /kiểm tra.*nền tảng/i);
  assert.match(platformLengthNotice('facebook'), /nội bộ/i);
  assert.equal(platformLengthNotice('invalid'), '');
});

test('multiple selected items require source relevance review for each segment', () => {
  assert.equal(sourceRelevanceWarning(0), '');
  assert.equal(sourceRelevanceWarning(1), '');
  assert.match(sourceRelevanceWarning(2), /không tự xác định/);
  assert.match(sourceRelevanceWarning(3), /từng mục và nguồn/);
});

test('conflict links identify a local publication or legacy draft and reject malformed targets', () => {
  const publication = {kind: 'publication', bulletin_id: 2, variant_id: 3, publication_id: 4, position: 0};
  const legacy = {kind: 'legacy_draft', draft_id: 7};
  for (const target of [publication, legacy]) {
    const url = conflictTargetUrl(target);
    assert.match(url, /^\/\?/);
    assert.deepEqual(parseConflictTarget(new URL(url, 'http://localhost').search), target);
  }
  for (const target of [null, {kind: 'legacy_draft', draft_id: '../1'},
    {...publication, position: -1}, {...publication, bulletin_id: 0}, {...publication, variant_id: 1.5}]) {
    assert.equal(conflictTargetUrl(target), null);
  }
  assert.equal(parseConflictTarget('?kind=publication&bulletin_id=2&variant_id=3&publication_id=4&position=0&position=1'), null);
});

test('copy requires the same currently valid approval and the same segment', () => {
  const shown = {approval_id: 4, posts: ['đoạn cũ', 'nguồn']};
  assert.equal(verifiedCopyText(shown, {approval_id: 4, posts: ['đoạn cũ', 'nguồn']}, 0), 'đoạn cũ');
  for (const current of [{approval_id: 5, posts: shown.posts},
                         {approval_id: 4, posts: ['đoạn khác']},
                         {approval_id: 4, posts: []}, {posts: shown.posts}]) {
    assert.throws(() => verifiedCopyText(shown, current, 0), /thay đổi/);
  }
});

test('pending bulletin action blocks editor, list, inbox and navigation and restores them on failure', async () => {
  const targets = [{inert: false}, {inert: false}, {inert: false}, {inert: true}];
  let release;
  const pending = withInertTargets(targets, () => new Promise((resolve, reject) => { release = reject; }));
  assert.deepEqual(targets.map(target => target.inert), [true, true, true, true]);
  release(new Error('thử lỗi'));
  await assert.rejects(pending, /thử lỗi/);
  assert.deepEqual(targets.map(target => target.inert), [false, false, false, true]);
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
