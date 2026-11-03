'use strict';

const $ = id => document.getElementById(id);
const labelCategory = value => value === 'ai' ? 'AI thực dụng' : 'Thiết bị & phần mềm';
const labelStatus = value => ({draft: 'Đang soạn', approved: 'Đã duyệt', published: 'Đã ghi nhận đăng'})[value] || value;
const app = {state: null, view: 'inbox', category: 'all', articleId: null, draft: null,
  dirty: false, reviewDirty: false, tab: 'packet', csrf: '', busy: false, exportId: null,
  selectedArticles: new Set(), bulletin: null, bulletinDirty: false, variantId: null, publicationKeys: new Map()};
let pollTimer, toastTimer;

// All external/source/model text is inserted as text or input values, never HTML.
function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function listen(element, event, action) {
  element.addEventListener(event, ev => Promise.resolve().then(() => action(ev)).catch(error => toast(error.message, true)));
}
function toast(message, error = false) {
  clearTimeout(toastTimer);
  $('toast').textContent = message;
  $('toast').classList.toggle('error', error);
  $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 12000 : 6500);
}
async function api(path, body) {
  const payload = body === undefined ? undefined : requestJson(body);
  let response;
  try {
    response = await fetch(path, {credentials: 'same-origin', cache: 'no-store',
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRF-Token': app.csrf},
      body: payload});
  } catch (_) {
    throw new Error('Mất kết nối với Bàn tin. Giữ nội dung chưa lưu; kiểm tra cửa sổ chạy ứng dụng.');
  }
  const json = (response.headers.get('Content-Type') || '').includes('application/json');
  const result = json ? await response.json() : await response.text();
  if (!response.ok) throw new Error(result.error || 'Chưa thực hiện được. Hãy giữ bản đang sửa và thử lại.');
  return result;
}
async function mutation(action) {
  if (app.busy) return toast('Đang lưu thao tác trước. Vui lòng chờ một chút.');
  app.busy = true;
  $('editor-content').inert = true;
  try { return await action(); } finally {
    app.busy = false;
    $('editor-content').inert = false;
  }
}
function formatDate(value) {
  if (!value || Number.isNaN(Date.parse(value))) return 'Chưa rõ ngày';
  return new Intl.DateTimeFormat('vi-VN', {day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Ho_Chi_Minh'}).format(new Date(value));
}
function shortDate(value) {
  if (!value || Number.isNaN(Date.parse(value))) return 'Chưa rõ ngày';
  const hours = (Date.now() - Date.parse(value)) / 3600000;
  if (hours < 0) return 'Ngày nguồn ở tương lai';
  if (hours < 1) return 'Trong giờ qua';
  if (hours < 24) return `${Math.floor(hours)} giờ trước`;
  if (hours < 8 * 24) return `${Math.floor(hours / 24)} ngày trước`;
  return formatDate(value).split(' ')[0];
}
function link(url, text) {
  const element = node('a', '', text);
  element.href = url;
  element.target = '_blank';
  element.rel = 'noopener noreferrer';
  return element;
}
function view(name) {
  if (app.view === 'bulletins' && name !== 'bulletins' && app.bulletinDirty &&
      !window.confirm('Bản tin có thay đổi chưa lưu. Bạn muốn rời trang?')) return;
  if (app.view === 'bulletins' && name !== 'bulletins' && app.bulletinDirty) {
    app.bulletinDirty = false;
    renderBulletin();
  }
  app.view = name;
  document.querySelectorAll('.view').forEach(element => { element.hidden = element.id !== `view-${name}`; });
  document.querySelectorAll('.nav-item').forEach(element => element.classList.toggle('active', element.dataset.view === name));
  if (name === 'bulletins') loadBulletinList().catch(error => toast(error.message, true));
}
function renderState() {
  const state = app.state;
  const stats = state.stats;
  $('stat-articles').textContent = stats.articles;
  $('stat-drafts').textContent = stats.drafts;
  $('stat-approved').textContent = stats.approved;
  $('stat-published').textContent = stats.published_30d;
  $('nav-count').textContent = stats.articles;
  $('draft-count').textContent = stats.drafts + stats.approved;
  $('trial-total').textContent = stats.published_30d;
  $('trial-progress').value = Math.min(stats.published_30d, 30);
  $('trial-detail').textContent = `30 ngày: AI ${stats.ai_30d}/15 · Thiết bị/PM ${stats.tools_30d}/15`;
  $('data-path').textContent = state.data_dir;
  $('demo-banner').hidden = !state.demo;
  $('refresh-button').disabled = state.busy || state.demo;
  $('follow-button').disabled = state.busy || state.demo || !state.features?.custom_sources;
  $('source-upgrade-notice').hidden = !!state.features?.custom_sources;
  $('refresh-label').textContent = state.busy ? 'Đang đọc nguồn…' : 'Lấy tin mới';
  $('refresh-icon').classList.toggle('spin', state.busy);
  const enabledSources = state.sources.filter(source => source.enabled);
  const checked = enabledSources.filter(source => source.health);
  const ok = checked.filter(source => source.health.ok).length;
  $('refresh-status').textContent = state.demo ? 'Dữ liệu minh họa riêng' : state.busy ? 'Đang đọc nguồn · có thể tiếp tục biên tập' :
    checked.length ? `${ok}/${enabledSources.length} nguồn đang bật đọc được lần gần nhất` : 'Chưa đọc nguồn · nhấn Lấy tin mới';
  renderStories();
  renderDrafts();
  renderSources();
}
async function loadState() {
  const wasBusy = app.state && app.state.busy;
  app.state = await api('/api/state');
  app.csrf = app.state.csrf_token;
  if (!app.articleId && app.state.articles.length) app.articleId = app.state.articles[0].id;
  renderState();
  if (wasBusy && !app.state.busy) toast('Đã kết thúc lượt đọc nguồn. Xem Nguồn tin để biết nguồn nào cần thử lại.');
}
function poll() {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    try { await loadState(); } catch (error) { toast(error.message, true); }
    poll();
  }, app.state && app.state.busy ? 2000 : 30000);
}
function empty(title, text) {
  const box = node('div', 'empty-state');
  box.append(node('span', 'empty-symbol', '▤'), node('h3', '', title), node('p', '', text));
  return box;
}
function renderStories() {
  const search = $('search-input').value.trim().toLocaleLowerCase();
  const days = $('age-filter').value === 'custom' ? $('custom-age').value : $('age-filter').value;
  const customInvalid = $('age-filter').value === 'custom' && (!$('custom-age').validity.valid || !$('custom-age').value);
  $('custom-age-label').hidden = $('age-filter').value !== 'custom';
  const now = Date.now();
  const items = app.state.articles.filter(item => {
    return (app.category === 'all' || item.category === app.category) &&
      !customInvalid && matchesAge(item.published_at, days, now) &&
      `${item.title} ${item.summary} ${item.source_name}`.toLocaleLowerCase().includes(search);
  });
  const list = $('story-list');
  list.replaceChildren();
  if (!items.length) list.append(empty('Chưa có tin phù hợp.', app.state.stats.articles ?
    'Thử đổi bộ lọc hoặc khoảng thời gian. Bạn cũng có thể nhập nguồn đã tự đọc.' :
    'Lấy tin mới để bắt đầu. Nếu nguồn bị chặn, bạn có thể nhập liên kết và ghi chú thủ công.'));
  for (const item of items) {
    const card = node('button', `story-card${item.id === app.articleId ? ' selected' : ''}`);
    card.type = 'button';
    card.setAttribute('aria-pressed', String(item.id === app.articleId));
    const meta = node('div', 'story-meta');
    const dateKind = item.date_kind === 'published' ? 'Xuất bản' : item.date_kind === 'updated' ? 'Cập nhật' : 'Ngày chưa rõ loại';
    meta.append(node('span', 'source-mark', item.source_name.charAt(0)), node('span', '', item.source_name),
      node('span', '', '·'), node('span', '', `${dateKind}: ${shortDate(item.published_at)}`));
    const bottom = node('div', 'story-bottom');
    bottom.append(node('span', `badge ${item.category}`, labelCategory(item.category)), node('span', '', `Ưu tiên ${item.score}/95`));
    card.append(meta, node('h3', '', item.title), node('p', 'excerpt', item.summary || 'Nguồn chưa có trích đoạn. Cần đọc nguồn gốc.'), bottom);
    const used = (app.state.bulletin_usage || {})[item.id] || 0;
    if (used) card.append(node('p', 'small-note', `Đã dùng trong ${used} bản tin. Có thể chọn lại để cập nhật.`));
    listen(card, 'click', () => { app.articleId = item.id; renderStories(); });
    const wrapper = node('div', 'bulletin-story');
    const selection = node('label', 'bulletin-select');
    const checkbox = node('input');
    checkbox.type = 'checkbox';
    checkbox.checked = app.selectedArticles.has(item.id);
    checkbox.setAttribute('aria-label', `Chọn tin ${item.title} cho bản tin`);
    listen(checkbox, 'change', () => {
      if (checkbox.checked && app.selectedArticles.size >= 10) {
        checkbox.checked = false;
        return toast('Một bản tin có tối đa 10 tin.');
      }
      if (checkbox.checked) app.selectedArticles.add(item.id); else app.selectedArticles.delete(item.id);
      updateBulletinSelection();
    });
    selection.append(checkbox, document.createTextNode(' Chọn'));
    wrapper.append(selection, card);
    list.append(wrapper);
  }
  const hidden = hiddenSelectionCount(app.selectedArticles, items);
  $('list-footer').textContent = customInvalid ? `Nhập số ngày nguyên từ 1 đến 3650. ${hidden} tin đã chọn đang ẩn.` :
    `${items.length}/${app.state.articles.length} tin hiển thị · ${hidden} tin đã chọn đang ẩn · tối đa 500 tin gần nhất. Tin chưa rõ ngày hoặc có ngày tương lai nằm trong bộ lọc Tất cả.`;
  updateBulletinSelection();
  renderArticle();
}
function renderArticle() {
  const item = app.state.articles.find(article => article.id === app.articleId);
  const panel = $('article-detail');
  panel.replaceChildren();
  if (!item) return panel.append(empty('Bắt đầu bằng một nguồn tốt.', 'Chọn một tin ở bên trái, hoặc nhập nguồn bạn đã đọc.'));
  const meta = node('div', 'article-meta');
  meta.append(node('span', '', item.source_name), node('span', '', `${item.date_kind === 'updated' ? 'Cập nhật' : 'Ngày nguồn'}: ${formatDate(item.published_at)}`));
  const sourceLinks = node('div', 'source-link-list');
  item.sources.forEach(source => sourceLinks.append(link(source.url, `${source.source_name} · Mở nguồn gốc ↗`)));
  const ranking = node('div', 'ranking');
  const reasons = node('ul');
  item.reasons.forEach(reason => reasons.append(node('li', '', reason)));
  ranking.append(node('span', 'eyebrow', `ƯU TIÊN BIÊN TẬP · ${item.score}/95`), reasons,
    node('p', 'small-note', 'Điểm từ độ mới và từ khóa, không phải lượt tìm kiếm hay bảo đảm tin đáng đăng. Nhóm chủ đề cũng cần bạn kiểm tra.'));
  const actions = node('div', 'action-row');
  const existing = app.state.drafts.find(draft => draft.article_id === item.id && draft.status !== 'published');
  const create = node('button', 'button primary', existing ? 'Tiếp tục bản nháp →' : 'Tạo bản nháp →');
  listen(create, 'click', () => existing ? openDraft(existing) : createDraft(item.id));
  actions.append(create);
  panel.append(node('div', 'eyebrow', 'BƯỚC 1 · CHỌN & ĐỌC NGUỒN'),
    node('h2', '', item.title), meta, node('span', `badge ${item.category}`, labelCategory(item.category)),
    node('p', 'small-note', `Thu thập: ${formatDate(item.fetched_at)} · Không tự dịch hoặc tải ảnh`),
    node('p', 'source-excerpt', item.summary || 'Nguồn chưa cung cấp trích đoạn. Hãy mở nguồn gốc và bổ sung ghi chú.'),
    sourceLinks, node('div', 'notice', 'Trích đoạn RSS/API/web hoặc ghi chú không phải toàn bộ bài. Cần đọc nguồn và kiểm tra quyền sử dụng trước khi viết lại.'),
    ranking, actions);
  if (item.collection?.length) {
    for (const evidence of item.collection) panel.append(node('p', 'small-note',
      `Phương pháp: ${evidence.collection_method} · Phạm vi: trích đoạn · Hash: ${evidence.excerpt_hash.slice(0, 12)}`));
  }
}
function renderDrafts() {
  const list = $('draft-list');
  list.replaceChildren();
  const filter = $('draft-filter').value;
  const items = app.state.drafts.filter(draft => filter === 'all' || draft.status === filter);
  if (!items.length) list.append(empty('Chưa có bài.', 'Bắt đầu từ Hộp tin.'));
  items.forEach(draft => {
    const article = app.state.articles.find(item => item.id === draft.article_id);
    const card = node('button', `draft-card${app.draft && app.draft.id === draft.id ? ' selected' : ''}`);
    card.append(node('span', `badge ${draft.status}`, labelStatus(draft.status)),
      node('strong', '', draft.title || article?.title || `Bản nháp #${draft.id}`),
      node('small', '', `${labelCategory(draft.category)} · v${draft.revision}`));
    listen(card, 'click', () => openDraft(draft));
    list.append(card);
  });
}
function canLeaveDraft() {
  return !(app.dirty || app.reviewDirty || hasPendingPublicationUrl(app.draft, $('post-url'))) ||
    window.confirm('Có thay đổi hoặc liên kết chưa ghi nhận. Bạn muốn bỏ phần chưa lưu để mở bài khác?');
}
async function createDraft(articleId) {
  if (app.busy) return toast('Đang lưu thao tác trước. Vui lòng chờ.');
  if (!canLeaveDraft()) return;
  await mutation(async () => {
    const draft = await api('/api/drafts', {article_id: articleId});
    await loadState();
    await setDraft(draft);
    setTab('packet');
    view('drafts');
    toast('Đã tạo bản nháp. Sao chép gói tư liệu sang ChatGPT để bắt đầu.');
  });
}
async function openDraft(draft) {
  if (app.busy) return toast('Đang lưu thao tác trước. Vui lòng chờ.');
  if (app.draft?.id === draft.id) return view('drafts');
  if (!canLeaveDraft()) return;
  await setDraft(draft);
  setTab(draft.body ? 'write' : 'packet');
  view('drafts');
}
async function setDraft(draft) {
  bindPublicationFields(app.draft, draft, $('post-url'), $('published-link'));
  app.draft = structuredClone(draft);
  const stateIndex = app.state.drafts.findIndex(item => item.id === draft.id);
  if (stateIndex < 0) app.state.drafts.unshift(structuredClone(draft));
  else app.state.drafts[stateIndex] = structuredClone(draft);
  app.dirty = false;
  app.reviewDirty = false;
  $('editor-empty').hidden = true;
  $('editor-content').hidden = false;
  const values = {page: 'page_name', category: 'category', title: 'title', body: 'body', angle: 'angle'};
  for (const [id, field] of Object.entries(values)) {
    $(`field-${id}`).value = draft[field];
    $(`field-${id}`).disabled = draft.status === 'published';
  }
  renderSourceFields(draft.sources);
  $('review-checks').replaceChildren();
  for (const [key, text] of Object.entries(app.state.checks)) {
    const label = node('label');
    const check = node('input');
    check.type = 'checkbox';
    check.dataset.check = key;
    check.checked = draft.checks[key] === true;
    listen(check, 'change', () => { app.reviewDirty = true; });
    label.append(check, node('span', '', text));
    $('review-checks').append(label);
  }
  const metric = app.state.metrics[String(draft.id)] || {};
  for (const field of ['saves', 'shares', 'followers', 'minutes']) $(`metric-${field}`).value = metric[field] || 0;
  $('metric-note').value = metric.note || '';
  updateEditorMeta();
  renderDrafts();
  $('packet-text').value = 'Đang chuẩn bị tư liệu…';
  const packet = await api(`/api/drafts/${draft.id}/packet`);
  if (app.draft?.id === draft.id) $('packet-text').value = packet.text;
}
function setTab(name) {
  app.tab = name;
  document.querySelectorAll('.editor-tab').forEach(element => { element.hidden = element.id !== `tab-${name}`; });
  document.querySelectorAll('.editor-tabs button').forEach(element => element.classList.toggle('active', element.dataset.tab === name));
  updateEditorMeta();
}
function markDirty() {
  if (!app.draft || app.draft.status === 'published') return;
  app.dirty = true;
  app.reviewDirty = false;
  document.querySelectorAll('[data-check]').forEach(check => { check.checked = false; });
  updateEditorMeta();
}
function updateEditorMeta() {
  if (!app.draft) return;
  const draft = app.draft;
  $('editor-status').textContent = app.dirty ? 'Có sửa đổi chưa lưu' : labelStatus(draft.status);
  $('editor-status').className = `badge ${app.dirty ? 'draft' : draft.status}`;
  $('editor-revision').textContent = `Bài #${draft.id} · phiên bản ${draft.revision} · ${formatDate(draft.updated_at)}`;
  $('unsaved-notice').hidden = !app.dirty;
  $('body-length').textContent = `${$('field-body').value.length.toLocaleString('vi-VN')} ký tự`;
  $('save-draft').disabled = draft.status === 'published';
  const approved = ['approved', 'published'].includes(draft.status) && !app.dirty;
  $('export-button').disabled = !approved;
  $('approve-button').disabled = app.dirty || draft.status !== 'draft';
  document.querySelectorAll('[data-check]').forEach(check => { check.disabled = app.dirty || draft.status !== 'draft'; });
  $('publish-section').hidden = draft.status !== 'approved' || app.dirty;
  $('metrics-section').hidden = draft.status !== 'published';
  $('review-summary').textContent = app.dirty ? 'Cần lưu nội dung trước khi kiểm tra và duyệt.' :
    `${draft.title || '(Chưa có tiêu đề)'}\nPage: ${draft.page_name || '(Chưa nhập tên Page)'}\n${labelCategory(draft.category)} · ${draft.body.length} ký tự · ${draft.sources.length} nguồn`;
  $('add-source').disabled = draft.status === 'published' || $('source-fields').children.length >= 8;
}
function getSources() {
  return Array.from($('source-fields').children).map(card => ({...card.sourceRecord,
    title: card.querySelector('[data-source="title"]').value,
    url: card.querySelector('[data-source="url"]').value,
    summary: card.querySelector('[data-source="summary"]').value}));
}
function renderSourceFields(sources) {
  $('source-fields').replaceChildren();
  sources.forEach((source, index) => {
    const card = node('div', 'source-fields-card');
    card.sourceRecord = structuredClone(source);
    const heading = node('div', 'source-field-title');
    heading.append(node('span', 'small-note', `Nguồn ${index + 1} · ${source.source_name}`));
    if (sources.length > 1 && app.draft.status !== 'published') {
      const remove = node('button', 'text-button', 'Bỏ nguồn');
      remove.type = 'button';
      listen(remove, 'click', () => { const current = getSources(); current.splice(index, 1); renderSourceFields(current); markDirty(); });
      heading.append(remove);
    }
    card.append(heading);
    for (const [field, title] of [['title', 'Tiêu đề nguồn'], ['url', 'Liên kết HTTPS'], ['summary', 'Trích đoạn ngắn / ghi chú kiểm chứng']]) {
      const label = node('label', '', title);
      const input = node(field === 'summary' ? 'textarea' : 'input');
      input.dataset.source = field;
      input.value = source[field] || '';
      input.maxLength = field === 'summary' ? 3000 : field === 'url' ? 2000 : 300;
      input.disabled = app.draft.status === 'published';
      if (field === 'summary') input.rows = 3;
      if (field === 'url') input.type = 'url';
      listen(input, 'input', markDirty);
      label.append(input);
      card.append(label);
    }
    if (source.url) card.append(link(source.url, 'Mở nguồn đã lưu ↗'));
    card.append(node('p', 'small-note', `Mốc nguồn: ${formatDate(source.published_at)} · Lưu tư liệu: ${formatDate(source.retrieved_at)}`));
    if (source.collection_method) card.append(node('p', 'small-note',
      `${source.collection_method} · trích đoạn · ${source.excerpt_hash.slice(0, 12)} · sửa ghi chú sẽ bỏ dấu vết bản gốc khi lưu`));
    $('source-fields').append(card);
  });
}
function collectDraft() {
  const checks = {};
  document.querySelectorAll('[data-check]').forEach(check => { checks[check.dataset.check] = check.checked; });
  return {revision: app.draft.revision, page_name: $('field-page').value, category: $('field-category').value,
    title: $('field-title').value, body: $('field-body').value, angle: $('field-angle').value,
    sources: getSources(), checks};
}
async function saveDraft() {
  if (!app.draft) return;
  await mutation(async () => {
    const wasApproved = app.draft.status === 'approved';
    const draft = await api(`/api/drafts/${app.draft.id}/save`, collectDraft());
    await setDraft(draft);
    await loadState();
    toast(wasApproved && draft.status === 'draft' ? 'Đã lưu sửa đổi và hủy duyệt cũ. Hãy kiểm tra, duyệt lại.' : 'Đã lưu. Hãy sang bước 3 để kiểm tra và duyệt.');
  });
}
function renderSources() {
  const grid = $('sources-grid');
  grid.replaceChildren();
  const custom = app.state.sources.filter(source => source.custom).reverse();
  const catalog = app.state.sources.filter(source => !source.custom);
  [...custom, ...catalog].forEach(source => {
    const card = node('section', 'panel source-card');
    const health = source.health;
    const method = {rss: 'RSS', api: 'API công khai', web: 'Web · Crawl4AI'}[source.kind] || 'RSS';
    card.append(node('span', `badge ${health?.ok ? '' : 'draft'}`, !source.enabled ? 'Đang tắt' : health ? (health.ok ? 'Đọc được' : 'Cần kiểm tra') : 'Chưa đọc'),
      node('p', 'small-note', `${method}${source.custom ? ' · Bạn đã thêm' : ''}`),
      node('h3', '', source.name), link(source.site, 'Đến trang nguồn ↗'), node('code', '', source.url),
      node('p', '', health?.message || 'Nhấn “Lấy tin mới” để kiểm tra. Chưa có dữ liệu nào được tải từ nguồn này.'),
      node('small', '', `Lần gần nhất: ${formatDate(health?.checked_at)}`));
    if (source.kind === 'web') card.append(node('p', 'small-note', `Phạm vi: ${source.prefix} trên cùng tên miền; tối đa 3 bài mới/lượt.`));
    const toggle = node('button', 'button secondary small', source.enabled ? 'Tắt nguồn' : 'Bật nguồn');
    toggle.disabled = app.state.demo || app.state.busy;
    listen(toggle, 'click', async () => {
      const enable = !source.enabled;
      if (enable && !window.confirm(`Bật ${source.name}? Ứng dụng sẽ đọc định kỳ trong phạm vi nguồn này khi đang chạy. Web có kiểm tra robots.txt. Không gọi AI hoặc tải ảnh.`)) return;
      await api(`/api/collection/sources/${source.id}`, {enabled: enable, confirmed: enable});
      await loadState();
      toast(enable ? 'Đã bật nguồn. Nhấn Lấy tin mới để đọc.' : 'Đã tắt nguồn; giữ nguyên các tin đã lưu.');
    });
    card.append(toggle);
    grid.append(card);
  });
  const collection = app.state.collection;
  if (!collection) return;
  $('collector-status').textContent = `Crawl4AI: ${collection.crawl.message} Hermes/Browser Use: ${collection.browser.message}`;
  const jobs = $('collection-jobs');
  jobs.replaceChildren();
  const labels = {pending: 'Chờ xử lý', running: 'Đang chạy', completed: 'Đã nhận tư liệu', unknown: 'Mất dấu · không tự chạy lại', cancelled: 'Đã đóng', failed: 'Chưa hoàn tất'};
  if (!collection.jobs.length) jobs.append(node('p', 'muted', 'Chưa có nguồn cần điều hướng bằng AI. RSS/API/web chạy độc lập, không cần kết nối tài khoản.'));
  for (const job of collection.jobs) {
    const row = node('div', 'source-details');
    const name = app.state.sources.find(s => s.id === job.source_id)?.name || job.source_id;
    row.append(node('h4', '', `${name} · ${labels[job.status] || job.status}`),
      node('p', '', job.reason), node('p', 'small-note', job.message));
    if (job.status === 'pending') {
      const run = node('button', 'button secondary small', 'Chạy 1 lượt trình duyệt AI');
      run.disabled = !collection.browser.ready || app.state.busy || app.state.demo;
      listen(run, 'click', async () => {
        if (!window.confirm('Cho phép dùng model đã cấu hình: tối đa 12 vòng, 180 giây. Lượt này có thể phát sinh phí/hạn mức; số vòng không phải trần tiền. Không tự thử lại nếu mất dấu. Tiếp tục?')) return;
        await api(`/api/collection/jobs/${job.id}/run`, {confirmed: true});
        await loadState();
        poll();
        toast('Đã gửi tác vụ. Theo dõi kết quả tại đây.');
      });
      row.append(run);
    }
    if (['pending', 'unknown', 'failed'].includes(job.status)) {
      const cancel = node('button', 'text-button', 'Đóng tác vụ');
      cancel.disabled = app.state.demo;
      listen(cancel, 'click', async () => {
        if (!window.confirm('Đóng tác vụ này? Nếu mất dấu, hãy kiểm tra lượt dùng ở nhà cung cấp trước. Hạn mức đã tiêu thụ không được hoàn lại.')) return;
        await api(`/api/collection/jobs/${job.id}/cancel`, {});
        await loadState();
      });
      row.append(cancel);
    }
    jobs.append(row);
  }
}
function showText(title, text, note, exportId = null, canCopy = true) {
  app.exportId = exportId;
  $('text-dialog-title').textContent = title;
  $('dialog-text').value = text;
  $('text-dialog-note').textContent = note;
  $('download-export').hidden = exportId === null;
  $('copy-dialog').hidden = !canCopy;
  if (!$('text-dialog').open) $('text-dialog').showModal();
}
async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('Đã sao chép. Bạn có thể dán vào nơi cần dùng.');
  } catch (_) {
    showText('Sao chép thủ công', text, 'Trình duyệt chưa cho phép clipboard. Chọn ô dưới, nhấn Ctrl+A rồi Ctrl+C.');
    $('dialog-text').focus();
    $('dialog-text').select();
  }
}

function updateBulletinSelection() {
  $('create-bulletin').textContent = `Tạo bản tin từ tin đã chọn (${app.selectedArticles.size}/10)`;
  $('create-bulletin').disabled = app.selectedArticles.size === 0;
  $('clear-bulletin-selection').disabled = app.selectedArticles.size === 0 || app.busy;
}
function bulletinAction(button, action) {
  listen(button, 'click', async () => {
    if (app.busy) throw new Error('Đang xử lý thao tác trước. Vui lòng chờ.');
    app.busy = true;
    const editor = $('bulletin-editor');
    const nav = document.querySelector('.sidebar nav');
    editor.inert = true;
    nav.inert = true;
    $('create-bulletin').disabled = true;
    $('clear-bulletin-selection').disabled = true;
    try { return await action(); }
    finally {
      app.busy = false;
      editor.inert = false;
      nav.inert = false;
      updateBulletinSelection();
    }
  });
}
async function loadBulletinList() {
  const [entries, stats] = await Promise.all([api('/api/bulletins'), api('/api/bulletin-stats')]);
  $('bulletin-stats').textContent = `${stats.bulletins} bản tin · ${stats.variants} phiên bản kênh · ${stats.recorded_bulletins} bản tin có ghi nhận · ${stats.recorded_posts} đoạn đã ghi nhận. Không cộng với thống kê bài cũ ở trên.`;
  const list = $('bulletin-list');
  list.replaceChildren();
  if (!entries.length) list.append(empty('Chưa có bản tin.', 'Chọn tin trong Hộp tin để bắt đầu.'));
  for (const entry of entries) {
    const button = node('button', `draft-card${app.bulletin?.id === entry.id ? ' selected' : ''}`);
    button.append(node('strong', '', entry.title || `Bản tin #${entry.id}`),
      node('small', '', `${entry.edition_date} · ${entry.item_count} mục · v${entry.revision}`));
    listen(button, 'click', async () => {
      if (app.bulletinDirty && !window.confirm('Bản tin có thay đổi chưa lưu. Bỏ thay đổi và mở bản khác?')) return;
      app.bulletin = await api(`/api/bulletins/${entry.id}`);
      app.bulletinDirty = false;
      renderBulletin();
      await loadBulletinList();
    });
    list.append(button);
  }
}
function bulletinField(label, value, multiline = false) {
  const wrapper = node('label', 'bulletin-field', label);
  const input = node(multiline ? 'textarea' : 'input');
  if (multiline) input.rows = 4;
  input.value = value || '';
  wrapper.append(input);
  return {wrapper, input};
}
function trackBulletinSection(section, fields) {
  const original = fields.map(field => field.type === 'checkbox' ? field.checked : field.value);
  const update = () => {
    section.dataset.dirty = String(sectionDiffers(fields, original));
    const editor = $('bulletin-editor');
    app.bulletinDirty = Boolean(editor.querySelector('[data-dirty="true"]')) || hasPendingBulletinUrl();
  };
  section.addEventListener('input', update);
  section.addEventListener('change', update);
}
function hasPendingBulletinUrl(except = null) {
  return [...$('bulletin-editor').querySelectorAll('[data-publication-url]')]
    .some(input => input !== except && input.value.trim());
}
function renderBulletin() {
  const bulletin = app.bulletin;
  const editor = $('bulletin-editor');
  editor.replaceChildren();
  if (!bulletin) return;
  editor.append(node('h3', '', bulletin.title || `Bản tin #${bulletin.id}`),
    node('p', 'small-note', `Phiên bản ${bulletin.revision}. Lưu từng phần trước khi chuyển sang phần khác.`));
  const top = node('section', 'bulletin-block');
  const title = bulletinField('Tiêu đề', bulletin.title);
  const edition = bulletinField('Ngày bản tin', bulletin.edition_date);
  edition.input.type = 'date';
  const intro = bulletinField('Lời mở', bulletin.introduction, true);
  const conclusion = bulletinField('Lời kết', bulletin.conclusion, true);
  const save = node('button', 'button primary', 'Lưu thông tin bản tin');
  bulletinAction(save, async () => {
    if (hasPendingBulletinUrl() || (app.bulletinDirty && [...editor.querySelectorAll('.bulletin-item, .variant-editor')].some(el => el.dataset.dirty === 'true')))
      throw new Error('Hãy lưu hoặc bỏ thay đổi ở mục tin trước.');
    app.bulletin = await api(`/api/bulletins/${bulletin.id}/save`, {revision: bulletin.revision,
      title: title.input.value, edition_date: edition.input.value, introduction: intro.input.value, conclusion: conclusion.input.value});
    app.bulletinDirty = false; renderBulletin(); await loadBulletinList(); toast('Đã lưu bản tin.');
  });
  trackBulletinSection(top, [title.input, edition.input, intro.input, conclusion.input]);
  top.append(title.wrapper, edition.wrapper, intro.wrapper, conclusion.wrapper, save);
  editor.append(top);
  bulletin.items.forEach((item, position) => {
    const section = node('section', 'bulletin-block bulletin-item');
    section.append(node('h4', '', `Mục ${position + 1}`));
    const fields = Object.fromEntries([['title', 'Tiêu đề'], ['body', 'Nội dung'], ['angle', 'Góc nhìn'],
      ['verification_note', 'Ghi chú kiểm chứng']].map(([key, label]) => [key, bulletinField(label, item[key], key !== 'title')]));
    Object.values(fields).forEach(field => section.append(field.wrapper));
    const sources = node('div', 'source-link-list');
    item.sources.forEach(source => {
      sources.append(link(source.url, source.title || source.source_name || source.url));
      const dateLabel = source.date_kind === 'updated' ? 'Ngày cập nhật' : source.date_kind === 'published' ? 'Ngày xuất bản' : 'Ngày nguồn chưa rõ loại';
      sources.append(node('p', 'small-note', `${dateLabel}: ${formatDate(source.published_at)} · Thu thập: ${formatDate(source.retrieved_at)} · Tư liệu là trích đoạn hoặc ghi chú, cần mở nguồn gốc.`));
      const warnings = sourceWarnings(source);
      if (warnings.length) sources.append(node('p', 'small-note', `Cần kiểm tra: ${warnings.join(' ')} Đây là nhắc biên tập, không đánh giá độ tin cậy.`));
      const removeSource = node('button', 'text-button', 'Bỏ nguồn này');
      removeSource.disabled = item.sources.length <= 1;
      bulletinAction(removeSource, async () => {
        if (app.bulletinDirty) throw new Error('Hãy lưu các thay đổi trước khi bỏ nguồn.');
        if (!window.confirm(`Bỏ nguồn ${source.url} khỏi mục này?`)) return;
        app.bulletin = await api(`/api/bulletins/${bulletin.id}/items/${item.id}/save`,
          {bulletin_revision: bulletin.revision, revision: item.revision, remove_source_id: source.source_id});
        renderBulletin(); await loadBulletinList(); toast('Đã bỏ nguồn; cần kiểm chứng lại mục.');
      });
      sources.append(removeSource);
    });
    section.append(node('p', 'small-note', 'Nguồn đã lưu cho mục:'), sources);
    const checkLabel = node('label', 'bulletin-check');
    const verified = node('input'); verified.type = 'checkbox'; verified.checked = item.verified;
    checkLabel.append(verified, document.createTextNode(' Tôi đã đọc nguồn và kiểm chứng mục này'));
    section.append(checkLabel, node('p', 'small-note', 'Khi sửa nội dung, xác nhận kiểm chứng sẽ được bỏ; lưu lại rồi xác nhận ở lần lưu tiếp theo.'));
    trackBulletinSection(section, [...Object.values(fields).map(field => field.input), verified]);
    const actions = node('div', 'action-row');
    const saveItem = node('button', 'button secondary', 'Lưu mục');
    bulletinAction(saveItem, async () => {
      if (hasPendingBulletinUrl() || top.dataset.dirty === 'true' || [...editor.querySelectorAll('.bulletin-item, .variant-editor')].some(el => el !== section && el.dataset.dirty === 'true'))
        throw new Error('Hãy lưu hoặc bỏ thay đổi ở các phần khác trước.');
      const data = {bulletin_revision: bulletin.revision, revision: item.revision, verified: verified.checked};
      for (const [key, field] of Object.entries(fields)) data[key] = field.input.value;
      app.bulletin = await api(`/api/bulletins/${bulletin.id}/items/${item.id}/save`, data);
      app.bulletinDirty = false; renderBulletin(); await loadBulletinList(); toast('Đã lưu mục tin.');
    });
    actions.append(saveItem);
    const addSource = node('button', 'button secondary', 'Bổ sung nguồn');
    addSource.disabled = item.sources.length >= 3;
    bulletinAction(addSource, async () => {
      if (app.bulletinDirty) throw new Error('Hãy lưu thay đổi trước khi bổ sung nguồn.');
      const url = window.prompt('Liên kết nguồn HTTPS:'); if (url === null) return;
      const title = window.prompt('Tiêu đề nguồn:', ''); if (title === null) return;
      const summary = window.prompt('Ghi chú về nguồn:', ''); if (summary === null) return;
      app.bulletin = await api(`/api/bulletins/${bulletin.id}/items/${item.id}/save`, {
        bulletin_revision: bulletin.revision, revision: item.revision, add_source: {url, title, summary}});
      renderBulletin(); await loadBulletinList(); toast('Đã thêm nguồn; cần kiểm chứng lại mục.');
    });
    actions.append(addSource);
    const remove = node('button', 'button secondary', 'Bỏ mục khỏi bản tin');
    remove.disabled = bulletin.items.length <= 1;
    bulletinAction(remove, async () => {
      if (app.bulletinDirty) throw new Error('Hãy lưu thay đổi trước khi bỏ mục.');
      if (!window.confirm(`Bỏ mục “${item.title}” khỏi bản tin này?`)) return;
      app.bulletin = await api(`/api/bulletins/${bulletin.id}/items`, {revision: bulletin.revision, remove_item_id: item.id});
      renderBulletin(); await loadBulletinList(); toast('Đã bỏ mục khỏi bản tin.');
    });
    actions.append(remove);
    for (const [label, delta] of [['↑', -1], ['↓', 1]]) {
      const move = node('button', 'button secondary', label); move.disabled = position + delta < 0 || position + delta >= bulletin.items.length;
      bulletinAction(move, async () => {
        if (app.bulletinDirty) throw new Error('Hãy lưu thay đổi trước khi đổi thứ tự.');
        const ids = bulletin.items.map(row => row.id);
        [ids[position], ids[position + delta]] = [ids[position + delta], ids[position]];
        app.bulletin = await api(`/api/bulletins/${bulletin.id}/save`, {revision: bulletin.revision, item_ids: ids});
        renderBulletin(); await loadBulletinList();
      });
      actions.append(move);
    }
    section.append(actions); editor.append(section);
  });
  const packet = node('button', 'button secondary', 'Sao chép gói tư liệu');
  listen(packet, 'click', async () => {
    if (app.bulletinDirty) throw new Error('Hãy lưu thay đổi trước khi lấy gói tư liệu.');
    const result = await api(`/api/bulletins/${bulletin.id}/packet`); await copy(result.text);
  });
  editor.append(packet);
  const history = node('button', 'button secondary', 'Xem lịch sử bản tin');
  listen(history, 'click', async () => {
    const entries = await api(`/api/bulletins/${bulletin.id}/history`);
    showText('Lịch sử bản tin', entries.map(entry =>
      `${formatDate(entry.at)} · ${entry.entity_type} #${entry.entity_id} · v${entry.revision} · ${entry.action}\n${entry.snapshot}`
    ).join('\n\n────────────\n\n'), 'Tối đa 100 sự kiện mới nhất; dữ liệu được lưu trên máy này.', null, false);
  });
  editor.append(history);
  const candidates = app.state.articles.filter(article => !bulletin.items.some(item => item.article_id === article.id));
  if (candidates.length && bulletin.items.length < 10) {
    const addSection = node('section', 'bulletin-block');
    const select = node('select'); select.setAttribute('aria-label', 'Tin muốn thêm vào bản tin');
    for (const article of candidates) {
      const used = (app.state.bulletin_usage || {})[article.id] || 0;
      const option = node('option', '', `${article.title}${used ? ` · đã dùng trong ${used} bản tin` : ''}`); option.value = article.id; select.append(option);
    }
    const addItem = node('button', 'button secondary', 'Thêm tin vào bản tin');
    bulletinAction(addItem, async () => {
      if (app.bulletinDirty) throw new Error('Hãy lưu thay đổi trước khi thêm mục.');
      const article = candidates.find(row => row.id === Number(select.value));
      await loadState();
      const used = (app.state.bulletin_usage || {})[article.id] || 0;
      if (used && !window.confirm(`Tin “${article.title}” đã dùng trong ${used} bản tin khác. Vẫn thêm để cập nhật?`)) return;
      const chosen = chooseBulletinSources(article);
      if (chosen === null) return;
      const data = {revision: bulletin.revision, article_id: article.id};
      if (chosen !== undefined) data.source_selection = chosen;
      app.bulletin = await api(`/api/bulletins/${bulletin.id}/items`, data);
      await loadState(); renderBulletin(); await loadBulletinList(); toast('Đã thêm tin vào bản tin.');
    });
    addSection.append(select, addItem); editor.append(addSection);
  }
  const variants = node('section', 'bulletin-block');
  variants.append(node('h3', '', 'Phiên bản theo kênh'));
  editor.append(variants);
  renderVariants(variants, bulletin).catch(error => toast(error.message, true));
}
async function renderVariants(container, bulletin) {
  const variants = await api(`/api/bulletins/${bulletin.id}/variants`);
  if (!container.isConnected) return;
  const selector = node('select');
  const placeholder = node('option', '', 'Chọn phiên bản'); placeholder.value = ''; selector.append(placeholder);
  variants.forEach(variant => {
    const option = node('option', '', `${variant.platform.toUpperCase()} · ${variant.account_label || '(chưa đặt tên)'} · ${variant.status}`);
    option.value = variant.id; selector.append(option);
  });
  selector.value = variants.some(variant => variant.id === app.variantId) ? String(app.variantId) : '';
  const platform = node('select');
  for (const value of ['facebook', 'threads', 'x']) {
    const option = node('option', '', value.toUpperCase()); option.value = value; platform.append(option);
  }
  const create = node('button', 'button secondary', 'Tạo phiên bản');
  const area = node('div', 'variant-editor');
  bulletinAction(create, async () => {
    if (app.bulletinDirty) throw new Error('Hãy lưu các thay đổi trước khi tạo phiên bản.');
    const variant = await api(`/api/bulletins/${bulletin.id}/variants`, {platform: platform.value,
      account_label: '', bulletin_revision: bulletin.revision});
    app.variantId = variant.id; renderBulletin(); await loadBulletinList();
  });
  listen(selector, 'change', () => {
    if (app.bulletinDirty) {
      selector.value = app.variantId ? String(app.variantId) : '';
      throw new Error('Hãy lưu các thay đổi trước khi đổi phiên bản.');
    }
    app.variantId = selector.value ? Number(selector.value) : null;
    renderBulletin();
  });
  container.append(selector, platform, create, area);
  const variant = variants.find(row => row.id === app.variantId);
  if (!variant) return;
  const locked = !!variant.locked_at;
  const history = locked ? await api(`/api/variants/${variant.id}/archive`) : null;
  if (!container.isConnected) return;
  const displayItems = locked ? history.items : bulletin.items;
  const displaySegments = locked ? history.rendered_posts.map(post => ({text: post.body, item_ids: post.item_ids, source_ids: post.source_ids})) : variant.segments;
  const account = bulletinField('Tên tài khoản / Page', locked ? history.account_label : variant.account_label);
  account.input.disabled = locked;
  area.append(node('p', 'small-note', `Trạng thái: ${variant.status}${variant.needs_update ? ' · Bản tin gốc đã đổi, cần kiểm tra lại' : ''}${locked ? ` · Mục và nguồn theo bản duyệt lịch sử (${history.policy_version})` : ''}`), account.wrapper);
  const segmentList = node('div');
  function addSegment(segment) {
    const block = node('section', 'bulletin-block');
    const body = bulletinField('Nội dung đoạn', segment.text, true);
    body.input.disabled = locked;
    block.append(body.wrapper, node('p', 'small-note', 'Chọn mục và ít nhất một nguồn cho mỗi mục được nhắc đến.'));
    const rows = [];
    for (const item of displayItems) {
      const row = node('div', 'bulletin-source-row');
      const itemLabel = node('label', 'bulletin-check');
      const selected = node('input'); selected.type = 'checkbox'; selected.checked = segment.item_ids.includes(item.id); selected.disabled = locked;
      itemLabel.append(selected, document.createTextNode(item.title || `Mục ${item.id}`)); row.append(itemLabel);
      const sourceChecks = item.sources.map(source => {
        const label = node('label', 'bulletin-check'); const check = node('input'); check.type = 'checkbox';
        check.checked = segment.source_ids ? segment.source_ids.includes(source.source_id) : selected.checked;
        check.disabled = locked; label.append(check, document.createTextNode(source.url)); row.append(label);
        return {id: source.source_id, check};
      });
      rows.push({id: item.id, selected, sourceChecks}); block.append(row);
    }
    const remove = node('button', 'button secondary', 'Bỏ đoạn'); remove.disabled = locked;
    listen(remove, 'click', () => {
      if (segmentList.children.length <= 1) return toast('Cần giữ ít nhất một đoạn.');
      block.remove(); app.bulletinDirty = true; area.dataset.dirty = 'true';
    });
    block.append(remove); segmentList.append(block);
    block.collect = () => ({text: body.input.value, item_ids: rows.filter(row => row.selected.checked).map(row => row.id),
      source_ids: rows.filter(row => row.selected.checked).flatMap(row => row.sourceChecks.filter(source => source.check.checked).map(source => source.id))});
  }
  displaySegments.forEach(addSegment);
  area.append(segmentList);
  const add = node('button', 'button secondary', 'Thêm đoạn'); add.disabled = locked || variant.platform === 'facebook';
  listen(add, 'click', () => {
    if (segmentList.children.length >= 20) return toast('Tối đa 20 đoạn.');
    addSegment({text: '', item_ids: [], source_ids: []}); app.bulletinDirty = true; area.dataset.dirty = 'true';
  });
  area.append(add);
  const checks = {};
  for (const [key, label] of [['sources', 'Đã đọc và đối chiếu nguồn'], ['facts', 'Đã kiểm tra dữ kiện'],
    ['original', 'Nội dung có góc nhìn riêng'], ['rights', 'Đã kiểm tra quyền sử dụng'], ['claims', 'Không còn thông tin chưa xác minh']]) {
    const row = node('label', 'bulletin-check'); const check = node('input');
    check.type = 'checkbox'; check.checked = (locked ? history.checks : variant.checks)[key]; check.disabled = locked;
    checks[key] = check; row.append(check, document.createTextNode(label)); area.append(row);
  }
  const adopt = node('input'); adopt.type = 'checkbox'; adopt.disabled = locked;
  if (variant.needs_update) {
    const row = node('label', 'bulletin-check'); row.append(adopt, document.createTextNode(' Tôi đã kiểm tra lại theo bản tin mới')); area.append(row);
  }
  const attributionReview = node('input'); attributionReview.type = 'checkbox'; attributionReview.disabled = locked;
  if (variant.attribution_review_required) {
    area.append(node('p', 'notice warning', 'Bản sao giữ nguyên nội dung, nhưng một số mục hoặc nguồn đã thay đổi. Hãy chọn và đối chiếu lại nguồn cho từng đoạn.'));
    const row = node('label', 'bulletin-check'); row.append(attributionReview, document.createTextNode(' Tôi đã kiểm tra lại các mục và nguồn của bản sao')); area.append(row);
  }
  area.addEventListener('input', event => { if (!event.target.dataset.publicationUrl) { app.bulletinDirty = true; area.dataset.dirty = 'true'; } });
  area.addEventListener('change', event => { if (!event.target.dataset.publicationUrl) { app.bulletinDirty = true; area.dataset.dirty = 'true'; } });
  const collect = () => [...segmentList.children].map(block => block.collect());
  const actions = node('div', 'action-row');
  const save = node('button', 'button secondary', 'Lưu phiên bản'); save.disabled = locked;
  bulletinAction(save, async () => {
    if (hasPendingBulletinUrl() || container.previousElementSibling?.dataset.dirty === 'true' || [...$('bulletin-editor').querySelectorAll('.bulletin-item, .bulletin-block')].some(el => el !== area && !el.contains(area) && el.dataset.dirty === 'true'))
      throw new Error('Hãy lưu các phần bản tin khác trước.');
    const saved = await api(`/api/variants/${variant.id}/save`, {revision: variant.revision, account_label: account.input.value,
      segments: collect(), checks: Object.fromEntries(Object.entries(checks).map(([key, value]) => [key, value.checked])),
      adopt_bulletin_revision: adopt.checked, attribution_reviewed: attributionReview.checked});
    app.variantId = saved.id; app.bulletinDirty = false; renderBulletin();
    toast('Đã lưu. Nếu vừa sửa nội dung, hãy xác nhận lại 5 mục kiểm tra và lưu lần nữa.');
  });
  const preview = node('button', 'button secondary', locked ? 'Xem trước bản duyệt lịch sử' : 'Xem trước');
  listen(preview, 'click', async () => {
    if (locked) {
      showText('Bản duyệt lịch sử', history.rendered_posts.map(post => `${post.position + 1}. ${post.length}/${post.limit}\n${post.text}`).join('\n\n────────────\n\n'),
        `Văn bản và bộ đếm tại policy ${history.policy_version}; không xác nhận phù hợp với quy tắc hiện hành.`, null, false);
      return;
    }
    const result = await api(`/api/variants/${variant.id}/preview`, {segments: collect()});
    const omitted = result.omitted_item_ids.length ? ` Mục không có trong phiên bản: ${result.omitted_item_ids.join(', ')}.` : '';
    showText('Xem trước phiên bản', result.posts.map(post => `${post.position + 1}. ${post.length}/${post.limit}${post.valid ? '' : ' · CHƯA ĐẠT'}\n${post.text}`).join('\n\n────────────\n\n'), result.warning + omitted, null, false);
  });
  const split = node('button', 'button secondary', 'Đề xuất chia đoạn');
  split.disabled = locked || variant.platform === 'facebook';
  listen(split, 'click', async () => {
    area.inert = true;
    try {
      const result = await api(`/api/variants/${variant.id}/split`, {revision: variant.revision, segments: collect()});
      segmentList.replaceChildren(); result.segments.forEach(addSegment);
      app.bulletinDirty = true; area.dataset.dirty = 'true';
      toast('Đã chia theo ranh giới câu/đoạn. Hãy đọc lại, lưu và kiểm tra trước khi duyệt.');
    } finally { area.inert = false; }
  });
  const approve = node('button', 'button primary', 'Duyệt phiên bản'); approve.disabled = locked;
  bulletinAction(approve, async () => {
    if (app.bulletinDirty) throw new Error('Hãy lưu phiên bản và xác nhận 5 mục trước khi duyệt.');
    await api(`/api/variants/${variant.id}/approve`, {revision: variant.revision}); renderBulletin();
    toast('Đã duyệt phiên bản; ứng dụng chưa đăng bài.');
  });
  const exportButton = node('button', 'button secondary', 'Xem bản đã duyệt');
  listen(exportButton, 'click', async () => {
    const result = await api(`/api/variants/${variant.id}/export`);
    showText('Bản đã duyệt', result.posts.map((post, i) => `Đoạn ${i + 1}\n${post}`).join('\n\n────────────\n\n'), 'Dùng nút sao chép riêng của từng đoạn để tự đăng.', null, false);
  });
  const archive = node('button', 'button secondary', 'Xem bản lưu lịch sử');
  listen(archive, 'click', async () => {
    const result = await api(`/api/variants/${variant.id}/archive`);
    showText('Bản lưu lịch sử', result.posts.map((post, i) => `Đoạn ${i + 1}\n${post}`).join('\n\n────────────\n\n'),
      `Lịch sử theo policy ${result.policy_version}; không xem là bản sẵn sàng đăng khi quy tắc hiện hành đã thay đổi.`, null, false);
  });
  const clone = node('button', 'button secondary', 'Tạo bản sao');
  bulletinAction(clone, async () => {
    if (app.bulletinDirty) throw new Error('Hãy lưu thay đổi trước khi tạo bản sao.');
    const result = await api(`/api/variants/${variant.id}/clone`, {revision: variant.revision}); app.variantId = result.id; renderBulletin(); await loadBulletinList();
  });
  actions.append(save, preview, split, approve, exportButton, archive, clone); area.append(actions);
  if (variant.status !== 'draft') await renderVariantPublication(area, variant);
}
async function renderVariantPublication(area, variant) {
  let ready = true, output;
  try { output = await api(`/api/variants/${variant.id}/export`); }
  catch (_) { ready = false; output = await api(`/api/variants/${variant.id}/archive`); }
  const publications = await api(`/api/variants/${variant.id}/publications`);
  if (!area.isConnected) return;
  const section = node('section', 'bulletin-block');
  section.append(node('h4', '', 'Xuất và ghi nhận đăng thủ công'),
    node('p', 'small-note', 'Ứng dụng không đăng bài và không xác minh bài trên mạng xã hội.'));
  if (ready) {
    const download = node('a', 'button secondary', 'Tải bản đã duyệt (.txt)');
    download.href = `/api/variants/${variant.id}/download`; section.append(download);
  } else {
    section.append(node('p', 'notice warning', 'Bản hiển thị là lịch sử, không còn đủ điều kiện xuất để đăng. Hãy tạo bản sao và duyệt theo quy tắc hiện tại.'));
  }
  output.posts.forEach((text, position) => {
    const block = node('div', 'bulletin-block');
    const field = node('textarea'); field.rows = 5; field.readOnly = true; field.value = text;
    const copyButton = node('button', 'button secondary', `Sao chép đoạn ${position + 1}`);
    listen(copyButton, 'click', () => copy(text));
    block.append(node('h4', '', `Đoạn ${position + 1}`), field);
    if (ready) block.append(copyButton);
    const existing = publications.find(record => record.position === position && record.active);
    if (existing) {
      block.append(node('p', '', 'Đã ghi nhận:'), link(existing.url, existing.url));
      if (existing.metrics.length) {
        const details = node('details');
        details.append(node('summary', '', `Số liệu đã lưu (${existing.metrics.length})`));
        for (const metric of existing.metrics) {
          const values = JSON.parse(metric.payload);
          details.append(node('p', 'small-note', `${formatDate(metric.observed_at)} · ` +
            [['views', 'Xem'], ['likes', 'Thích'], ['saves', 'Lưu'], ['shares', 'Chia sẻ'],
              ['followers', 'Theo dõi mới'], ['minutes', 'Phút']].map(([key, label]) =>
              `${label}: ${values[key] === null ? 'chưa biết' : values[key]}`).join(' · ') +
            (values.note ? ` · ${values.note}` : '')));
        }
        block.append(details);
      }
      const addMetrics = node('button', 'button secondary', 'Nhập số liệu');
      bulletinAction(addMetrics, async () => {
        if (app.bulletinDirty) throw new Error('Hãy lưu thay đổi trước khi nhập số liệu.');
        const values = window.prompt('Nhập 6 số nguyên cách nhau bằng dấu phẩy theo thứ tự: lượt xem, thích, lưu, chia sẻ, theo dõi mới, phút chuẩn bị. Để trống giá trị chưa biết.', ',,,,,');
        if (values === null) return;
        const fields = values.split(',').map(value => value.trim());
        if (fields.length !== 6 || fields.some(value => value && !/^\d+$/.test(value)))
          throw new Error('Cần đúng 6 giá trị; mỗi giá trị là số nguyên không âm hoặc để trống.');
        const observed = window.prompt('Thời điểm quan sát (ISO 8601 có múi giờ):', new Date().toISOString());
        if (observed === null) return;
        const note = window.prompt('Ghi chú số liệu (không bắt buộc):', ''); if (note === null) return;
        const payload = {observed_at: observed, note};
        ['views', 'likes', 'saves', 'shares', 'followers', 'minutes'].forEach((key, index) => {
          payload[key] = fields[index] === '' ? null : Number(fields[index]);
        });
        await api(`/api/publications/${existing.id}/metrics`, payload);
        renderBulletin(); toast('Đã lưu số liệu do bạn nhập.');
      });
      const correct = node('button', 'button secondary', 'Đính chính liên kết');
      bulletinAction(correct, async () => {
        if (app.bulletinDirty) throw new Error('Hãy lưu các thay đổi trước khi đính chính.');
        const reason = window.prompt('Lý do đính chính (ít nhất 5 ký tự):'); if (reason === null) return;
        const url = window.prompt('Liên kết thay thế. Để trống để hủy ghi nhận:', existing.url); if (url === null) return;
        if (!window.confirm('Ghi nhận đính chính này? Lịch sử cũ vẫn được giữ.')) return;
        await api(`/api/publications/${existing.id}/corrections`, {revision: variant.revision, reason, url});
        renderBulletin(); await loadBulletinList(); toast('Đã lưu đính chính.');
      });
      block.append(addMetrics, correct);
    } else {
      const url = node('input'); url.type = 'url'; url.placeholder = 'Liên kết bài đã tự đăng'; url.dataset.publicationUrl = 'true';
      const report = node('button', 'button secondary', 'Ghi nhận đã đăng');
      bulletinAction(report, async () => {
        if (hasPendingBulletinUrl(url) || area.dataset.dirty === 'true' || [...$('bulletin-editor').querySelectorAll('.bulletin-item, .bulletin-block')].some(el => el !== area && !el.contains(area) && el.dataset.dirty === 'true'))
          throw new Error('Hãy lưu các thay đổi khác trước khi ghi nhận.');
        const value = url.value.trim(); if (!value) throw new Error('Hãy nhập liên kết bài đã đăng.');
        if (!window.confirm(`Ghi nhận đoạn ${position + 1} đã đăng trên ${variant.platform.toUpperCase()} · ${variant.account_label}?\n\n${value}\n\nỨng dụng không kiểm tra bài đăng.`)) return;
        const key = `${variant.id}:${position}:${value}`;
        if (!app.publicationKeys.has(key)) app.publicationKeys.set(key, crypto.randomUUID());
        await api(`/api/variants/${variant.id}/publications`, {revision: variant.revision, position, url: value,
          idempotency_key: app.publicationKeys.get(key)});
        app.bulletinDirty = false; renderBulletin(); await loadBulletinList(); toast('Đã ghi nhận thông tin do bạn nhập.');
      });
      url.addEventListener('input', () => {
        app.bulletinDirty = [...$('bulletin-editor').querySelectorAll('[data-dirty="true"]')].length > 0 ||
          [...$('bulletin-editor').querySelectorAll('[data-publication-url]')].some(input => input.value.trim());
      });
      block.append(url, report);
    }
    section.append(block);
  });
  const historical = publications.filter(record => !record.active);
  if (historical.length) {
    const details = node('details'); details.append(node('summary', '', `Lịch sử ghi nhận đã đính chính (${historical.length})`));
    historical.forEach(record => {
      const row = node('p', 'small-note', `Đoạn ${record.position + 1} · ${record.url} · ${formatDate(record.recorded_at)}`);
      details.append(row);
      record.events.forEach(event => details.append(node('p', 'small-note', `${event.action} · ${formatDate(event.at)} · ${event.payload}`)));
    });
    section.append(details);
  }
  area.append(section);
}
function chooseBulletinSources(article) {
  if (article.sources.length <= 3) return undefined;
  const answer = window.prompt(`Chọn 1–3 nguồn cho “${article.title}”, nhập số cách nhau bằng dấu phẩy:\n\n${article.sources.map((source, i) => `${i + 1}. ${source.source_name}: ${source.url}`).join('\n')}`);
  if (answer === null) return null;
  const indexes = answer.split(',').map(value => value.trim());
  if (indexes.length < 1 || indexes.length > 3 || indexes.some(value => !/^\d+$/.test(value) || Number(value) < 1 || Number(value) > article.sources.length) || new Set(indexes.map(Number)).size !== indexes.length)
    throw new Error('Hãy chọn 1–3 số nguồn khác nhau.');
  return indexes.map(value => article.sources[Number(value) - 1].url);
}
bulletinAction($('create-bulletin'), async () => {
  if (!app.selectedArticles.size) return;
  if (app.bulletinDirty && !window.confirm('Bản tin đang mở có thay đổi chưa lưu. Bỏ thay đổi và tạo bản mới?')) return;
  await loadState();
  const reused = [...app.selectedArticles].map(id => {
    const article = app.state.articles.find(row => row.id === id);
    const count = (app.state.bulletin_usage || {})[id] || 0;
    return article && count ? `• ${article.title} (${count} bản tin)` : null;
  }).filter(Boolean);
  if (reused.length && !window.confirm(`Các tin sau đã dùng trong bản tin khác:\n${reused.join('\n')}\n\nVẫn tạo bản tin mới?`)) return;
  const sourceSelection = {};
  for (const id of app.selectedArticles) {
    const article = app.state.articles.find(row => row.id === id);
    if (!article) throw new Error('Một tin đã chọn không còn trong danh sách. Hãy tải lại và chọn lại.');
    const chosen = chooseBulletinSources(article);
    if (chosen === null) return;
    if (chosen !== undefined) sourceSelection[String(id)] = chosen;
  }
  app.bulletin = await api('/api/bulletins', {article_ids: [...app.selectedArticles], title: '', source_selection: sourceSelection});
  app.selectedArticles.clear(); app.bulletinDirty = false; await loadState(); renderBulletin(); view('bulletins');
  toast('Đã tạo bản tin. Hãy bổ sung và kiểm chứng từng mục.');
});

document.querySelectorAll('[data-view]').forEach(button => listen(button, 'click', () => view(button.dataset.view)));
document.querySelectorAll('[data-tab]').forEach(button => listen(button, 'click', () => setTab(button.dataset.tab)));
document.querySelectorAll('[data-close]').forEach(button => listen(button, 'click', () => $(button.dataset.close).close()));
document.querySelectorAll('[data-category]').forEach(button => listen(button, 'click', () => {
  app.category = button.dataset.category;
  document.querySelectorAll('[data-category]').forEach(item => item.classList.toggle('active', item === button));
  renderStories();
}));
listen($('search-input'), 'input', renderStories);
listen($('age-filter'), 'change', renderStories);
listen($('custom-age'), 'input', renderStories);
listen($('clear-bulletin-selection'), 'click', () => { app.selectedArticles.clear(); renderStories(); });
listen($('draft-filter'), 'change', renderDrafts);
listen($('refresh-button'), 'click', async () => {
  await api('/api/refresh', {});
  await loadState();
  poll();
});
listen($('import-button'), 'click', () => $('import-dialog').showModal());
let addingSource = false;
let followScopeAuto = true;
function followFields() {
  const web = $('follow-kind').value === 'web';
  $('follow-web-fields').hidden = !web;
  $('follow-prefix').required = web;
  if (web && followScopeAuto) {
    try {
      const path = new URL($('follow-url').value).pathname.replace(/\/+$/, '');
      $('follow-prefix').value = `${path}/`;
    } catch (_) { /* Keep the scope empty until a valid URL is entered. */ }
  }
}
listen($('follow-kind'), 'change', () => { $('follow-confirmed').checked = false; followFields(); });
listen($('follow-url'), 'input', () => { $('follow-confirmed').checked = false; followFields(); });
listen($('follow-prefix'), 'input', () => { followScopeAuto = false; $('follow-confirmed').checked = false; });
listen($('follow-button'), 'click', () => {
  if (addingSource) return;
  $('follow-form').reset();
  followScopeAuto = true;
  $('follow-error').hidden = true;
  followFields();
  $('follow-dialog').showModal();
});
listen($('follow-dialog'), 'cancel', event => { if (addingSource) event.preventDefault(); });
listen($('follow-form'), 'submit', async event => {
  event.preventDefault();
  if (addingSource) return;
  addingSource = true;
  const data = {name: $('follow-name').value, url: $('follow-url').value, kind: $('follow-kind').value,
    prefix: $('follow-prefix').value, confirmed: $('follow-confirmed').checked};
  const fields = [...$('follow-form').querySelectorAll('input,select,button'), $('follow-close')];
  fields.forEach(field => { field.disabled = true; });
  $('follow-error').hidden = true;
  $('follow-progress').hidden = false;
  try {
    const source = await api('/api/collection/sources', data);
    $('follow-dialog').close();
    view('sources');
    try { await loadState(); } catch (_) { toast('Nguồn đã lưu; tải lại trang để xem. Không cần thêm lại.', true); return; }
    toast(`Đã thêm ${source.name} (${source.kind === 'rss' ? 'RSS/Atom' : 'web'}). Nguồn đang bật; nhấn “Lấy tin mới” để đọc bài.`);
  } catch (error) {
    $('follow-error').textContent = error.message;
    $('follow-error').hidden = false;
  } finally {
    addingSource = false;
    fields.forEach(field => { field.disabled = false; });
    $('follow-progress').hidden = true;
  }
});
listen($('import-form'), 'submit', async event => {
  event.preventDefault();
  await mutation(async () => {
    const article = await api('/api/articles/import', {url: $('import-url').value,
      title: $('import-title').value, summary: $('import-summary').value});
    app.articleId = article.id;
    $('age-filter').value = 'all';
    $('search-input').value = '';
    app.category = 'all';
    document.querySelectorAll('[data-category]').forEach(item => item.classList.toggle('active', item.dataset.category === 'all'));
    await loadState();
    $('import-dialog').close();
    $('import-form').reset();
    view('inbox');
    toast('Đã thêm bài thủ công vào Hộp tin. Không tạo nguồn theo dõi, không tự tải trang.');
  });
});
listen($('draft-form'), 'submit', event => { event.preventDefault(); return saveDraft(); });
for (const id of ['field-page', 'field-title', 'field-body', 'field-angle', 'field-category']) listen($(id), 'input', markDirty);
listen($('add-source'), 'click', () => {
  const sources = getSources();
  if (sources.length >= 8) return toast('Bản đầu giới hạn 8 nguồn cho một bài.');
  sources.push({url: '', title: '', summary: '', source_name: 'Bổ sung thủ công',
    published_at: null, date_kind: 'unknown', retrieved_at: new Date().toISOString()});
  renderSourceFields(sources);
  markDirty();
});
listen($('copy-packet'), 'click', async () => {
  if (app.dirty) throw new Error('Hãy lưu thay đổi để gói tư liệu khớp nguồn và góc nhìn mới nhất.');
  await copy($('packet-text').value);
});
listen($('preview-button'), 'click', () => showText('Xem trước bản đang biên tập',
  `${$('field-title').value}\n\n${$('field-body').value}\n\nNguồn tham khảo:\n${getSources().map(source => source.url).join('\n')}`,
  'Đây là bản xem trước, có thể chưa được duyệt. Muốn đăng, hãy sang bước 3 và dùng bản xuất đã duyệt.', null, false));
listen($('approve-button'), 'click', async () => {
  if (app.dirty) throw new Error('Cần lưu nội dung trước khi duyệt.');
  const checks = collectDraft().checks;
  if (!Object.values(checks).every(Boolean)) throw new Error('Hãy hoàn tất cả 5 mục kiểm tra trước khi duyệt.');
  await mutation(async () => {
    const saved = await api(`/api/drafts/${app.draft.id}/save`, {revision: app.draft.revision, checks});
    // Save returns a new revision even if approval later fails validation.
    // Adopt that receipt first so the next edit cannot accidentally use a stale revision.
    await setDraft(saved);
    const approved = await api(`/api/drafts/${saved.id}/approve`, {revision: saved.revision});
    await setDraft(approved);
    await loadState();
    toast('Đã duyệt đúng phiên bản này. Ứng dụng chưa đăng bài.');
  });
});
listen($('export-button'), 'click', async () => {
  const text = await api(`/api/drafts/${app.draft.id}/export`);
  showText('Bài đã duyệt — đăng thủ công', text,
    `Đích dự kiến: ${app.draft.page_name}. Tự kiểm tra lại trước khi dán. Nếu sửa nội dung, hãy quay về cập nhật và duyệt lại.`, app.draft.id);
});
listen($('copy-dialog'), 'click', () => copy($('dialog-text').value));
listen($('download-export'), 'click', () => {
  if (app.exportId !== null) window.location.assign(`/api/drafts/${app.exportId}/export`);
});
listen($('mark-published'), 'click', async () => {
  const url = $('post-url').value.trim();
  if (!url) throw new Error('Hãy nhập liên kết bài Facebook đã đăng.');
  if (!window.confirm(`Ghi nhận bài “${app.draft.title}” đã đăng trên Page “${app.draft.page_name}”?\n\nLiên kết: ${url}\n\nỨng dụng không kiểm tra Facebook.`)) return;
  await mutation(async () => {
    const draft = await api(`/api/drafts/${app.draft.id}/published`, {
      revision: app.draft.revision, post_url: url});
    await setDraft(draft);
    await loadState();
    toast('Đã ghi nhận lời xác nhận của bạn. Bản nội dung này được giữ nguyên.');
  });
});
listen($('history-button'), 'click', async () => {
  const rows = await api(`/api/drafts/${app.draft.id}/history`);
  const names = {created: 'Tạo bản nháp', saved: 'Lưu bản nháp / kiểm tra', approved: 'Duyệt',
    saved_approval_revoked: 'Sửa bài, hủy duyệt cũ', user_reported_manual_publication: 'Người dùng ghi nhận đã tự đăng'};
  const text = rows.map(row => {
    const snapshot = JSON.parse(row.snapshot);
    return `v${snapshot.revision} · ${names[row.action] || row.action} · ${formatDate(row.at)}\n${snapshot.title || '(Chưa có tiêu đề)'}\nPage: ${snapshot.page_name || '(Chưa có)'}\n\n${snapshot.body}\n\n${snapshot.sources.map(source => source.url).join('\n')}`;
  }).join('\n\n──────────────────\n\n');
  showText('Lịch sử các phiên bản đã lưu', text, 'Chỉ hiển thị các lần đã lưu; không tự khôi phục hoặc ghi đè bản hiện tại.');
});
listen($('copy-legacy-bulletin'), 'click', async () => {
  if (app.dirty || app.reviewDirty || hasPendingPublicationUrl(app.draft, $('post-url')))
    throw new Error('Hãy lưu nội dung và xử lý liên kết đang nhập trước khi tạo bản sao.');
  if (app.bulletinDirty) throw new Error('Hãy lưu thay đổi ở bản tin đang mở trước khi tạo bản sao.');
  const chosen = chooseBulletinSources(app.draft);
  if (chosen === null) return;
  await mutation(async () => {
    const data = {revision: app.draft.revision};
    if (chosen !== undefined) data.source_selection = chosen;
    const result = await api(`/api/drafts/${app.draft.id}/copy-bulletin`, data);
    app.bulletin = result.bulletin; app.variantId = result.variant_id; app.bulletinDirty = false;
    renderBulletin(); view('bulletins');
    toast('Đã tạo bản sao chưa duyệt; bản nháp cũ được giữ nguyên.');
  });
});
listen($('backup-button'), 'click', () => mutation(async () => {
  const result = await api('/api/backup', {});
  showText('Đã tạo bản sao lưu', result.path,
    'Đã kiểm tra toàn vẹn SQLite. Chép tệp này sang ổ khác hoặc thư mục sao lưu OneDrive. Không chép cơ sở dữ liệu đang chạy.');
}));
listen($('save-metrics'), 'click', () => mutation(async () => {
  const data = {note: $('metric-note').value};
  for (const field of ['saves', 'shares', 'followers', 'minutes']) data[field] = Number($(`metric-${field}`).value);
  await api(`/api/drafts/${app.draft.id}/metrics`, data);
  await loadState();
  toast('Đã lưu số liệu do bạn nhập.');
}));
window.addEventListener('beforeunload', event => {
  if (app.dirty || app.reviewDirty || app.bulletinDirty || hasPendingPublicationUrl(app.draft, $('post-url'))) {
    event.preventDefault(); event.returnValue = '';
  }
});
loadState().then(poll).catch(error => toast(error.message, true));
