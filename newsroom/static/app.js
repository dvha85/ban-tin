'use strict';

const $ = id => document.getElementById(id);
const labelCategory = value => value === 'ai' ? 'AI thực dụng' : 'Thiết bị & phần mềm';
const labelStatus = value => ({draft: 'Đang soạn', approved: 'Đã duyệt', published: 'Đã ghi nhận đăng'})[value] || value;
const app = {state: null, view: 'inbox', category: 'all', articleId: null, draft: null,
  dirty: false, reviewDirty: false, tab: 'packet', csrf: '', busy: false, exportId: null};
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
  let response;
  try {
    response = await fetch(path, {credentials: 'same-origin', cache: 'no-store',
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRF-Token': app.csrf},
      body: body === undefined ? undefined : JSON.stringify(body)});
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
  if (hours < -2.4) return 'Ngày nguồn ở tương lai';
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
  app.view = name;
  document.querySelectorAll('.view').forEach(element => { element.hidden = element.id !== `view-${name}`; });
  document.querySelectorAll('.nav-item').forEach(element => element.classList.toggle('active', element.dataset.view === name));
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
  const days = $('age-filter').value;
  const items = app.state.articles.filter(item => {
    const age = item.published_at ? (Date.now() - Date.parse(item.published_at)) / 86400000 : null;
    return (app.category === 'all' || item.category === app.category) &&
      (days === 'all' || age === null || age <= Number(days)) &&
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
    meta.append(node('span', 'source-mark', item.source_name.charAt(0)), node('span', '', item.source_name),
      node('span', '', '·'), node('span', '', shortDate(item.published_at)));
    const bottom = node('div', 'story-bottom');
    bottom.append(node('span', `badge ${item.category}`, labelCategory(item.category)), node('span', '', `Ưu tiên ${item.score}/95`));
    card.append(meta, node('h3', '', item.title), node('p', 'excerpt', item.summary || 'Nguồn chưa có trích đoạn. Cần đọc nguồn gốc.'), bottom);
    listen(card, 'click', () => { app.articleId = item.id; renderStories(); });
    list.append(card);
  }
  $('list-footer').textContent = `${items.length}/${app.state.articles.length} tin hiển thị · tối đa 500 tin gần nhất. Tin chưa rõ ngày vẫn được giữ.`;
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
  return !(app.dirty || app.reviewDirty || hasPendingPublicationUrl(app.draft, $('post-url'))) || window.confirm('Có thay đổi chưa lưu. Bạn muốn bỏ phần chưa lưu để mở bài khác?');
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
  if (app.dirty && hasPendingPublicationUrl(app.draft, $('post-url')) &&
      !window.confirm('Lưu thay đổi có thể hủy duyệt và xóa URL đang nhập. Hãy sao chép URL nếu cần giữ lại. Bạn muốn tiếp tục lưu?')) return;
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
  if (!app.draft || app.draft.status !== 'approved' || app.dirty) throw new Error('Hãy chọn bản đã duyệt và lưu các thay đổi trước.');
  const url = $('post-url').value.trim();
  if (!url) throw new Error('Hãy nhập liên kết bài đã đăng trên Facebook.');
  if (!window.confirm(`Xác nhận đã tự đăng bài “${app.draft.title}” lên ${app.draft.page_name}?\nLiên kết: ${url}\nỨng dụng chỉ ghi nhận, không kiểm tra Facebook.`)) return;
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
  if (app.dirty || app.reviewDirty || hasPendingPublicationUrl(app.draft, $('post-url'))) { event.preventDefault(); event.returnValue = ''; }
});
loadState().then(poll).catch(error => toast(error.message, true));
