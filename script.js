// ==== BACKEND CONFIG ====
// Points at your ngrok tunnel to main.py. If ngrok gives you a new URL
// (happens every time you restart the `ngrok http 8000` process on the
// free tier), update this line and redeploy.
const API_BASE_URL = "https://platter-sandbox-derby.ngrok-free.dev";

const conversation = document.getElementById('conversation');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const historyList = document.getElementById('historyList');
const emptyHistory = document.getElementById('emptyHistory');
const newChatBtn = document.getElementById('newChatBtn');
const sidebar = document.querySelector('.sidebar');
const backdrop = document.getElementById('backdrop');
const hamburgerBtn = document.getElementById('hamburgerBtn');
const addSiteBtn = document.getElementById('addSiteBtn');
const addSiteModal = document.getElementById('addSiteModal');
const cancelSiteBtn = document.getElementById('cancelSiteBtn');
const confirmSiteBtn = document.getElementById('confirmSiteBtn');
const siteUrlInput = document.getElementById('siteUrlInput');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const kgEmpty = document.getElementById('kgEmpty');
const kgCards = document.getElementById('kgCards');
const depthToggle = document.getElementById('depthToggle');

// delete-chat confirmation modal
const deleteChatModal = document.getElementById('deleteChatModal');
const deleteChatMessage = document.getElementById('deleteChatMessage');
const deleteChatCancelBtn = document.getElementById('deleteChatCancelBtn');
const deleteChatConfirmBtn = document.getElementById('deleteChatConfirmBtn');

// ==== Sanity check: catch "nothing happens" bugs immediately ====
// If index.html and script.js ever drift out of sync (an id gets renamed,
// or a piece of markup goes missing), the element lookups above silently
// return null — then calling .addEventListener on them further down would
// throw and silently kill every listener registration after that point,
// which looks exactly like "clicking the button does nothing". This
// checks up front and logs exactly which id is missing, in the console.
(function checkRequiredElements(){
  const required = {
    conversation, userInput, sendBtn, historyList, emptyHistory, newChatBtn,
    sidebar, backdrop, hamburgerBtn, addSiteBtn, addSiteModal, cancelSiteBtn,
    confirmSiteBtn, siteUrlInput, statusDot, statusText, kgEmpty, kgCards,
    depthToggle, deleteChatModal, deleteChatMessage, deleteChatCancelBtn,
    deleteChatConfirmBtn
  };
  const missing = Object.entries(required).filter(([, el]) => !el).map(([name]) => name);
  if(missing.length){
    console.error(
      `Graphitti: these elements are missing from index.html — ` +
      `matching ids are required in the HTML: ${missing.join(', ')}`
    );
  }
})();

const GREETING = "Hi, I'm your Graphitti medical assistant. Ask me about a condition, symptom, or treatment and I'll answer using the connected knowledge graph.";

// ---- chat state: each chat is { id, title, updatedAt, messages: [{text, sender}] | null }
let chats = [];
let currentChatId = null;

// ---- knowledge graph sites: { id, url, title, status: 'indexing' | 'indexed' | 'failed', depth }
let sites = [];
let selectedDepth = 1;

depthToggle.addEventListener('click', (e) => {
  const btn = e.target.closest('.depth-btn');
  if(!btn) return;
  selectedDepth = Number(btn.dataset.depth);
  depthToggle.querySelectorAll('.depth-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
});

function renderConversation(messages){
  conversation.innerHTML = '';
  messages.forEach(m => addMessage(m.text, m.sender, false));
  conversation.scrollTop = conversation.scrollHeight;
}

// Renders the "Recent chats" list, including a per-row delete ("×") button.
function renderHistoryList(){
  historyList.innerHTML = '';
  if(chats.length === 0){
    historyList.appendChild(emptyHistory);
    return;
  }
  chats.forEach(chat => {
    const li = document.createElement('li');
    li.className = 'history-item' + (chat.id === currentChatId ? ' active' : '');
    li.dataset.chat = chat.id;
    // messages loaded → exact count; not loaded yet → backend's turn count
    const meta = chat.messages ? `${chat.messages.length} messages` : `${chat.turnCount || 0} messages`;
    li.innerHTML = `
      <span class="node-dot"></span>
      <div class="h-main">
        <span class="h-title">${chat.title}</span>
        <span class="h-meta">${meta}</span>
      </div>
      <button class="chat-delete" data-id="${chat.id}" aria-label="Delete chat" title="Delete chat">×</button>
    `;
    historyList.appendChild(li);
  });
}

function startNewChat(){
  currentChatId = null;
  renderConversation([{ text: GREETING, sender: 'bot' }]);
  renderHistoryList();
}

function addMessage(text, sender, scroll = true){
  const msg = document.createElement('div');
  msg.className = 'msg ' + sender;
  msg.innerHTML = `
    <div class="avatar ${sender}">${sender === 'user' ? 'You' : 'GX'}</div>
    <div class="bubble">${text}</div>
  `;
  conversation.appendChild(msg);
  if(scroll) conversation.scrollTop = conversation.scrollHeight;
}

// FastAPI sends errors two different shapes: raise HTTPException(...) gives
// { detail: "some string" }, but a Pydantic validation failure gives
// { detail: [{ loc, msg, type, ... }] } — an array of objects, not a
// string. Passing that straight into `new Error(...)` stringifies it to
// "[object Object]". This normalizes both shapes into one readable string.
function extractErrorMessage(errBody, fallback){
  const detail = errBody && errBody.detail;
  if(typeof detail === 'string') return detail;
  if(Array.isArray(detail)){
    return detail
      .map(d => (d && d.msg) ? d.msg : JSON.stringify(d))
      .join('; ');
  }
  if(detail) return JSON.stringify(detail);
  return fallback;
}

function escapeHtml(str){
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}

// ==== Helper: fetch wrapper with a clear error when the backend can't be
// reached at all (server down, wrong URL, CORS, ngrok tunnel dead, etc.) ====
async function safeFetch(url, options = {}){
  const headers = {
    // Free ngrok tunnels show a "you're about to visit..." interstitial
    // page to any request that doesn't send this header, which breaks
    // fetch() with a CORS-looking "Failed to fetch" error. Harmless no-op
    // if API_BASE_URL isn't an ngrok URL.
    'ngrok-skip-browser-warning': 'true',
    ...(options.headers || {})
  };

  try{
    return await fetch(url, { ...options, headers });
  }catch(err){
    console.error('safeFetch network failure:', err);
    throw new Error(
      `Cannot reach backend at ${API_BASE_URL}. Is main.py running, and is ` +
      `API_BASE_URL pointing at the right host/port? (${err.message})`
    );
  }
}

// ==== BACKEND CALL: chat query ====
// chat_id may be null for a brand-new chat — main.py creates one and
// returns its real chat_id in the response (see sendMessage below).
async function queryBackend(question, chatId){
  const res = await safeFetch(`${API_BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, chat_id: chatId })
  });
  if(!res.ok){
    const errBody = await res.json().catch(() => ({}));
    throw new Error(extractErrorMessage(errBody, `Backend returned ${res.status}`));
  }
  return res.json();
}

function sendMessage(){
  const text = userInput.value.trim();
  if(!text) return;

  const isNewChat = currentChatId === null;
  let chat;

  if(isNewChat){
    // main.py never generates its own chat_id (chat_id = req.chat_id or
    // "default") — if we ever sent null here, that first message would
    // silently land in a shared "default" bucket instead of its own
    // chat. So the frontend has to be the one source of truth for chat
    // IDs from the very first message, not just after the fact.
    currentChatId = 'chat_' + Date.now();
    chat = {
      id: currentChatId,
      title: text.length > 24 ? text.slice(0, 24) + '…' : text,
      updatedAt: new Date().toISOString(),
      messages: [{ text: GREETING, sender: 'bot' }]
    };
    chats.unshift(chat);
  }else{
    chat = chats.find(c => c.id === currentChatId);
  }

  chat.messages.push({ text, sender: 'user' });
  addMessage(text, 'user');
  userInput.value = '';
  userInput.style.height = 'auto';
  renderHistoryList();

  // typing indicator
  const typingId = 'typing_' + Date.now();
  const typingMsg = document.createElement('div');
  typingMsg.className = 'msg bot';
  typingMsg.id = typingId;
  typingMsg.innerHTML = `<div class="avatar bot">GX</div><div class="bubble">…</div>`;
  conversation.appendChild(typingMsg);
  conversation.scrollTop = conversation.scrollHeight;

  queryBackend(text, currentChatId)
    .then(data => {
      document.getElementById(typingId)?.remove();
      const reply = data.answer || "I couldn't generate an answer for that.";
      chat.messages.push({ text: reply, sender: 'bot' });
      addMessage(reply, 'bot');
      chat.updatedAt = new Date().toISOString();
      renderHistoryList();
    })
    .catch(err => {
      document.getElementById(typingId)?.remove();
      const reply = `⚠️ Couldn't reach the backend (${err.message}). Please check the backend connection.`;
      chat.messages.push({ text: reply, sender: 'bot' });
      addMessage(reply, 'bot');
      renderHistoryList();
    });
}

function addSystemMessage(text){
  if(currentChatId === null){
    currentChatId = 'local_' + Date.now();
    chats.unshift({
      id: currentChatId,
      title: 'New chat',
      updatedAt: new Date().toISOString(),
      messages: [{ text: GREETING, sender: 'bot' }]
    });
  }
  const chat = chats.find(c => c.id === currentChatId);
  chat.messages.push({ text, sender: 'bot' });
  addMessage(text, 'bot');
  chat.updatedAt = new Date().toISOString();
  renderHistoryList();
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keydown', (e) => {
  if(e.key === 'Enter' && !e.shiftKey){
    e.preventDefault();
    sendMessage();
  }
});
userInput.addEventListener('input', () => {
  userInput.style.height = 'auto';
  userInput.style.height = Math.min(userInput.scrollHeight, 120) + 'px';
});

// main.py's /chat/history returns chat_histories[chat_id] directly, and
// _save_chat() stores each turn as { question, answer, time } — a PAIR,
// not a flat { role, content } message. The previous version of this
// function treated `answer` as just another name for `content`, which
// picked up the answer but silently dropped the question every time
// (labeling the whole pair as one "bot" message) — that's the actual bug.
// This checks for the paired shape explicitly and expands it into two
// messages, and only falls back to flat-shape guessing otherwise.
function mapBackendMessages(messages){
  const out = [];
  (messages || []).forEach(m => {
    if(m.question !== undefined || m.answer !== undefined){
      // paired shape: { question, answer, time }
      if(m.question) out.push({ text: m.question, sender: 'user' });
      if(m.answer) out.push({ text: m.answer, sender: 'bot' });
      return;
    }
    // flat shape fallback: { role, content } or close variants
    const text = m.content ?? m.text ?? m.message ?? null;
    const roleRaw = (m.role || m.sender || '').toString().toLowerCase();
    const sender = roleRaw === 'user' ? 'user' : 'bot';
    if(text !== null && text !== undefined) out.push({ text, sender });
  });
  return out;
}

// Open a chat from the sidebar (click anywhere on the row except the
// delete button — that's handled separately below).
historyList.addEventListener('click', async (e) => {
  if(e.target.closest('.chat-delete')) return; // let the delete handler own this click
  const item = e.target.closest('.history-item');
  if(!item) return;
  const chat = chats.find(c => c.id === item.dataset.chat);
  if(!chat) return;

  currentChatId = chat.id;
  renderHistoryList();
  if(window.innerWidth <= 768) closeSidebar();

  if(chat.messages){
    renderConversation(chat.messages);
    return;
  }

  // not loaded yet — fetch this chat's real history from the backend
  renderConversation([{ text: GREETING, sender: 'bot' }, { text: 'Loading…', sender: 'bot' }]);
  try{
    const res = await safeFetch(`${API_BASE_URL}/chat/history?chat_id=${encodeURIComponent(chat.id)}`);
    if(!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json();
    // TEMP DIAGNOSTIC — open the browser console (F12) after clicking a
    // chat to see exactly what shape the backend actually returns. Once
    // this is confirmed working correctly, this line can be deleted.
    console.log('/chat/history response for', chat.id, ':', data);
    chat.messages = [{ text: GREETING, sender: 'bot' }, ...mapBackendMessages(data.messages)];
  }catch(err){
    chat.messages = [
      { text: GREETING, sender: 'bot' },
      { text: `⚠️ Couldn't load this chat (${err.message}).`, sender: 'bot' }
    ];
  }
  if(currentChatId === chat.id){
    renderConversation(chat.messages);
    renderHistoryList();
  }
});

// ==== Delete a chat — custom Yes/No confirmation modal ====
let pendingDeleteChatId = null;

function openDeleteChatModal(chatId, title){
  pendingDeleteChatId = chatId;
  deleteChatMessage.textContent = `Delete "${title}"? This can't be undone.`;
  deleteChatModal.classList.add('show');
}
function closeDeleteChatModal(){
  pendingDeleteChatId = null;
  deleteChatModal.classList.remove('show');
}

historyList.addEventListener('click', (e) => {
  const delBtn = e.target.closest('.chat-delete');
  if(!delBtn) return;
  e.stopPropagation();
  const chat = chats.find(c => c.id === delBtn.dataset.id);
  if(!chat) return;
  openDeleteChatModal(chat.id, chat.title);
});

deleteChatCancelBtn.addEventListener('click', closeDeleteChatModal);
deleteChatModal.addEventListener('click', (e) => {
  if(e.target === deleteChatModal) closeDeleteChatModal();
});

deleteChatConfirmBtn.addEventListener('click', async () => {
  const chatId = pendingDeleteChatId;
  if(!chatId) return;
  closeDeleteChatModal();

  // optimistic local removal
  chats = chats.filter(c => c.id !== chatId);
  if(currentChatId === chatId){
    startNewChat();
  }else{
    renderHistoryList();
  }

  // main.py's DELETE /chat/{chat_id} always responds 200 — "found or not"
  // is signaled by a status field in the JSON body, not the HTTP status.
  try{
    const res = await safeFetch(`${API_BASE_URL}/chat/${encodeURIComponent(chatId)}`, { method: 'DELETE' });
    if(!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json().catch(() => ({}));
    // "not_found" just means this chat only ever held local "added a
    // website" system messages and never reached the backend — nothing to
    // clean up, not a real failure, so don't warn about it.
    if(data.status && data.status !== 'success' && data.status !== 'not_found'){
      throw new Error(data.status);
    }
  }catch(err){
    console.error('Failed to delete chat on backend:', err);
    addSystemMessage(`⚠️ Chat removed locally, but couldn't delete it on the backend (${err.message}). It may reappear on refresh.`);
  }
});

newChatBtn.addEventListener('click', startNewChat);

// ---- sidebar toggle ----
function openSidebar(){
  sidebar.classList.add('open');
  backdrop.classList.add('show');
}
function closeSidebar(){
  sidebar.classList.remove('open');
  backdrop.classList.remove('show');
}
hamburgerBtn.addEventListener('click', () => {
  sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
});
backdrop.addEventListener('click', closeSidebar);

// ---- add website modal ----
function openSiteModal(){
  addSiteModal.classList.add('show');
  siteUrlInput.focus();
}
function closeSiteModal(){
  addSiteModal.classList.remove('show');
  siteUrlInput.value = '';
}
addSiteBtn.addEventListener('click', openSiteModal);
cancelSiteBtn.addEventListener('click', closeSiteModal);
addSiteModal.addEventListener('click', (e) => {
  if(e.target === addSiteModal) closeSiteModal();
});

function normalizeUrl(url){
  let u = url.trim();
  if(!/^https?:\/\//i.test(u)) u = 'https://' + u;
  return u;
}

// ==== Build a readable label from the URL, including the topic/page ====
// so "webmd.com/migraine" shows as "webmd.com" + a "migraine" topic line,
// instead of collapsing every page on a domain down to just the hostname.
// This is a client-side guess used immediately after adding a site, before
// the backend has responded with its own cleaned-up title.
function siteLabelParts(url){
  try{
    const parsed = new URL(normalizeUrl(url));
    const host = parsed.hostname.replace(/^www\./, '');
    const segments = parsed.pathname.split('/').filter(Boolean);
    if(segments.length === 0){
      return { host, topic: null };
    }
    const topic = decodeURIComponent(segments[segments.length - 1])
      .replace(/[-_]/g, ' ')
      .replace(/\.\w+$/, '') // strip trailing file extensions like .html
      .trim();
    return { host, topic: topic || null };
  }catch(e){
    return { host: url.trim(), topic: null };
  }
}

// Prefers the backend's cleaned title (main.py's _extract_topic_title —
// strips "WebMD", title-cases, etc.) once known; falls back to the raw
// URL-slug guess right after a site is added, before the backend replies.
function labelFor(site){
  const { host, topic } = siteLabelParts(site.url);
  return { host, topic: site.title || topic };
}

function updateStatusFooter(){
  const anyIndexed = sites.some(s => s.status === 'indexed');
  statusDot.classList.toggle('off', !anyIndexed);
  statusText.textContent = anyIndexed ? 'Knowledge graph connected' : 'Knowledge graph not connected';
}

function renderKgCards(){
  kgEmpty.style.display = sites.length ? 'none' : 'block';
  kgCards.innerHTML = sites.map(site => {
    const { host, topic } = labelFor(site);
    const nameHtml = topic
      ? `${escapeHtml(host)}<span class="kg-topic">${escapeHtml(topic)}</span>`
      : escapeHtml(host);
    return `
      <div class="kg-card">
        <div class="kg-card-top">
          <span class="kg-card-name">${nameHtml}</span>
          <span class="kg-badge ${site.status === 'indexing' ? 'indexing' : ''} ${site.status === 'failed' ? 'failed' : ''}">
            <span class="dot"></span>${site.status === 'indexing' ? 'Crawling' : site.status === 'failed' ? 'Failed' : 'Indexed'} · depth ${site.depth}
          </span>
        </div>
        <button class="kg-open-btn" data-id="${site.id}">Open graph ↗</button>
      </div>
    `;
  }).join('');
}

// ==== Graph view ====
// main.py serves a full-featured graph.html at GET /graph (category
// legend with click-to-filter, edge-click relation popups, node
// connection panels — all already built). This just opens it with the
// right URL pre-filled; no graph rendering happens here anymore.
//
// The ngrok-skip-browser-warning=true query param is added here (not just
// the header safeFetch uses elsewhere) because this is a real top-level
// browser navigation, not a fetch() call — you can't attach a custom
// header to window.open(url). Without this, ngrok's free-tier "you're
// about to visit a site served via ngrok" interstitial shows up instead
// of the graph on any device that hasn't already clicked through it once
// (which is why it only worked on the machine running the backend).
function openGraphWindow(site){
  const graphUrl = `${API_BASE_URL}/graph?url=${encodeURIComponent(site.url)}&ngrok-skip-browser-warning=true`;
  window.open(graphUrl, '_blank');
}

kgCards.addEventListener('click', (e) => {
  const btn = e.target.closest('.kg-open-btn');
  if(!btn) return;
  const site = sites.find(s => s.id === btn.dataset.id);
  if(site) openGraphWindow(site);
});

// ==== BACKEND CALL: crawl + poll status ====
async function pollCrawlStatus(site, attempt = 0){
  const MAX_ATTEMPTS = 30; // ~60s at 2s intervals
  try{
    const res = await safeFetch(`${API_BASE_URL}/status?url=${encodeURIComponent(site.url)}`);
    if(!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json();

    const { host, topic } = labelFor(site);
    const label = topic ? `${host} — ${topic}` : host;

    if(data.crawl_status === 'completed'){
      site.status = 'indexed';
      renderKgCards();
      updateStatusFooter();
      addSystemMessage(`<b>${escapeHtml(label)}</b>'s knowledge graph is ready (${data.node_count} nodes). Click "Open graph" in the sidebar to explore it.`);
      return;
    }
    if(data.crawl_status === 'failed'){
      site.status = 'failed';
      renderKgCards();
      updateStatusFooter();
      addSystemMessage(`⚠️ Crawling <b>${escapeHtml(label)}</b> failed. Please check the backend logs and try again.`);
      return;
    }
    // still crawling
    if(attempt >= MAX_ATTEMPTS){
      site.status = 'failed';
      renderKgCards();
      updateStatusFooter();
      addSystemMessage(`⚠️ Crawling <b>${escapeHtml(label)}</b> is taking too long — please check the backend connection.`);
      return;
    }
    setTimeout(() => pollCrawlStatus(site, attempt + 1), 2000);
  }catch(err){
    site.status = 'failed';
    renderKgCards();
    updateStatusFooter();
    addSystemMessage(`⚠️ Couldn't check crawl status for <b>${escapeHtml(labelFor(site).host)}</b> (${err.message}). Please check the backend connection.`);
  }
}

confirmSiteBtn.addEventListener('click', async () => {
  const raw = siteUrlInput.value.trim();
  if(!raw) return;
  const fullUrl = normalizeUrl(raw);
  closeSiteModal();

  const site = { id: 'site_' + Date.now(), url: fullUrl, status: 'indexing', depth: selectedDepth, title: null };
  const { host, topic } = labelFor(site);
  const label = topic ? `${host} — ${topic}` : host;

  sites.push(site);
  renderKgCards();
  updateStatusFooter();

  addSystemMessage(`Added <b>${escapeHtml(label)}</b> as a source (crawl depth ${site.depth}). Crawling it now and building its knowledge graph — I'll let you know once it's ready.`);

  try{
    const res = await safeFetch(`${API_BASE_URL}/crawl`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: fullUrl, depth: site.depth })
    });
    if(!res.ok){
      const errBody = await res.json().catch(() => ({}));
      throw new Error(extractErrorMessage(errBody, `Backend returned ${res.status}`));
    }
    const data = await res.json();

    // main.py's /crawl always returns "title" (via _extract_topic_title) —
    // grab it now so the card switches from the URL-slug guess to the
    // backend's cleaned-up title immediately, not just after polling.
    if(data.title) site.title = data.title;
    const finalLabelParts = labelFor(site);
    const finalLabel = finalLabelParts.topic ? `${finalLabelParts.host} — ${finalLabelParts.topic}` : finalLabelParts.host;

    if(data.status === 'already_crawled'){
      // main.py returns this immediately when the URL is already indexed —
      // no crawl actually started, so there's nothing to poll for.
      site.status = 'indexed';
      renderKgCards();
      updateStatusFooter();
      addSystemMessage(data.message || `<b>${escapeHtml(finalLabel)}</b> was already in the knowledge graph.`);
    }else{
      // status === 'started' — crawl running in the background, poll for completion
      renderKgCards();
      pollCrawlStatus(site);
    }
  }catch(err){
    site.status = 'failed';
    renderKgCards();
    updateStatusFooter();
    addSystemMessage(`⚠️ Failed to start crawl for <b>${escapeHtml(label)}</b> (${err.message}). Please check the backend connection.`);
  }
});

// ==== BACKEND CALL: load existing sources on page load ====
async function loadSourcesFromBackend(){
  try{
    const res = await safeFetch(`${API_BASE_URL}/sources`);
    if(!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json();
    sites = (data.sources || []).map(s => ({
      id: 'site_' + s.url,
      url: s.url,
      title: s.title || null,
      status: s.status === 'completed' ? 'indexed' : (s.status === 'failed' ? 'failed' : 'indexing'),
      depth: s.depth || 1
    }));
    renderKgCards();
    updateStatusFooter();
  }catch(err){
    console.error('Could not load sources from backend:', err);
    updateStatusFooter();
  }
}

// ==== BACKEND CALL: load chat list on page load ====
// Confirmed against main.py: GET /chat/list returns
// { chats: [{ chat_id, title, created_at, updated_at }] }, already sorted
// most-recently-updated first. There's no message count in this response —
// renderHistoryList() shows a relative time instead until a chat is opened
// (at which point the real message count is known).
//
// Any chat that only exists locally so far (e.g. created by adding a
// website — see addSystemMessage — but never sent a real question, so
// the backend has no record of it) is preserved instead of being wiped
// out when this refreshes the list from the server.
async function loadChatsFromBackend(){
  try{
    const res = await safeFetch(`${API_BASE_URL}/chat/list`);
    if(!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json();
    const list = data.chats || [];

    const alreadyLoaded = {};
    chats.forEach(c => { if(c.messages) alreadyLoaded[c.id] = c.messages; });

    // main.py's /chat/list returns { chat_id, title, last_question,
    // message_count } — no timestamp, and no sorting (dict insertion
    // order = oldest first), so reverse it to put newest chats on top.
    const backendChats = list
      .map(c => ({
        id: c.chat_id,
        title: c.title && c.title.length > 28 ? c.title.slice(0, 28) + '…' : (c.title || 'New chat'),
        turnCount: c.message_count,
        messages: alreadyLoaded[c.chat_id] || null
      }))
      .reverse();

    const backendIds = new Set(backendChats.map(c => c.id));
    const localOnly = chats.filter(c => !backendIds.has(c.id));

    chats = [...localOnly, ...backendChats];
    renderHistoryList();
  }catch(err){
    console.error('Could not load chats from backend:', err);
  }
}

// init
renderHistoryList();
renderKgCards();
if(window.innerWidth > 768) sidebar.classList.add('open');
loadSourcesFromBackend();
loadChatsFromBackend();
