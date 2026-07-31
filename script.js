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

const deleteChatModal = document.getElementById('deleteChatModal');
const deleteChatMessage = document.getElementById('deleteChatMessage');
const deleteChatCancelBtn = document.getElementById('deleteChatCancelBtn');
const deleteChatConfirmBtn = document.getElementById('deleteChatConfirmBtn');

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

let chats = [];
let currentChatId = null;

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
    const count = chat.messages ? chat.messages.length : (chat.turnCount || 0);
    li.innerHTML = `
      <span class="node-dot"></span>
      <div class="h-main">
        <span class="h-title">${chat.title}</span>
        <span class="h-meta">${count} messages</span>
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

async function safeFetch(url, options = {}){
  const headers = {
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

  if(currentChatId === null){
    currentChatId = 'chat_' + Date.now();
    chats.unshift({
      id: currentChatId,
      title: text.length > 24 ? text.slice(0, 24) + '…' : text,
      messages: [{ text: GREETING, sender: 'bot' }]
    });
  }
  const chat = chats.find(c => c.id === currentChatId);

  chat.messages.push({ text, sender: 'user' });
  addMessage(text, 'user');
  userInput.value = '';
  userInput.style.height = 'auto';
  renderHistoryList();

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
      renderHistoryList();
    })
    .catch(err => {
      document.getElementById(typingId)?.remove();
      const reply = ` Couldn't reach the backend (${err.message}). Please check the backend connection.`;
      chat.messages.push({ text: reply, sender: 'bot' });
      addMessage(reply, 'bot');
      renderHistoryList();
    });
}

function addSystemMessage(text){
  if(currentChatId === null){
    currentChatId = 'chat_' + Date.now();
    chats.unshift({
      id: currentChatId,
      title: 'New chat',
      messages: [{ text: GREETING, sender: 'bot' }]
    });
  }
  const chat = chats.find(c => c.id === currentChatId);
  chat.messages.push({ text, sender: 'bot' });
  addMessage(text, 'bot');
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

function flattenHistoryTurns(turns){
  const out = [];
  (turns || []).forEach(turn => {
    if(turn.question) out.push({ text: turn.question, sender: 'user' });
    if(turn.answer) out.push({ text: turn.answer, sender: 'bot' });
  });
  return out;
}

historyList.addEventListener('click', async (e) => {
  if(e.target.closest('.chat-delete')) return;
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

  
  renderConversation([{ text: GREETING, sender: 'bot' }, { text: 'Loading…', sender: 'bot' }]);
  try{
    const res = await safeFetch(`${API_BASE_URL}/chat/history?chat_id=${encodeURIComponent(chat.id)}`);
    if(!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json();
    chat.messages = [{ text: GREETING, sender: 'bot' }, ...flattenHistoryTurns(data.messages)];
  }catch(err){
    chat.messages = [
      { text: GREETING, sender: 'bot' },
      { text: ` Couldn't load this chat (${err.message}).`, sender: 'bot' }
    ];
  }
  if(currentChatId === chat.id){
    renderConversation(chat.messages);
    renderHistoryList();
  }
});

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

  chats = chats.filter(c => c.id !== chatId);
  if(currentChatId === chatId){
    startNewChat();
  }else{
    renderHistoryList();
  }

  try{
    const res = await safeFetch(`${API_BASE_URL}/chat/${encodeURIComponent(chatId)}`, { method: 'DELETE' });
    if(!res.ok && res.status !== 404){
      throw new Error(`Backend returned ${res.status}`);
    }
  }catch(err){
    console.error('Failed to delete chat on backend:', err);
    addSystemMessage(` Chat removed locally, but couldn't delete it on the backend (${err.message}). It may reappear on refresh.`);
  }
});

newChatBtn.addEventListener('click', startNewChat);

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
      .replace(/\.\w+$/, '') 
      .trim();
    return { host, topic: topic || null };
  }catch(e){
    return { host: url.trim(), topic: null };
  }
}

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
      ? `${host}<span class="kg-topic">${topic}</span>`
      : host;
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

function openGraphWindow(site){
  const graphUrl = `${API_BASE_URL}/graph?url=${encodeURIComponent(site.url)}`;
  window.open(graphUrl, '_blank');
}

kgCards.addEventListener('click', (e) => {
  const btn = e.target.closest('.kg-open-btn');
  if(!btn) return;
  const site = sites.find(s => s.id === btn.dataset.id);
  if(site) openGraphWindow(site);
});

async function pollCrawlStatus(site, attempt = 0){
  const MAX_ATTEMPTS = 30; 
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
      addSystemMessage(`<b>${label}</b>'s knowledge graph is ready (${data.node_count} nodes). Click "Open graph" in the sidebar to explore it.`);
      return;
    }
    if(data.crawl_status === 'failed'){
      site.status = 'failed';
      renderKgCards();
      updateStatusFooter();
      addSystemMessage(` Crawling <b>${label}</b> failed. Please check the backend logs and try again.`);
      return;
    }
    if(attempt >= MAX_ATTEMPTS){
      site.status = 'failed';
      renderKgCards();
      updateStatusFooter();
      addSystemMessage(` Crawling <b>${label}</b> is taking too long — please check the backend connection.`);
      return;
    }
    setTimeout(() => pollCrawlStatus(site, attempt + 1), 2000);
  }catch(err){
    site.status = 'failed';
    renderKgCards();
    updateStatusFooter();
    addSystemMessage(` Couldn't check crawl status for <b>${labelFor(site).host}</b> (${err.message}). Please check the backend connection.`);
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

  addSystemMessage(`Added <b>${label}</b> as a source (crawl depth ${site.depth}). Crawling it now and building its knowledge graph — I'll let you know once it's ready.`);

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

    if(data.title) site.title = data.title;
    const finalLabelParts = labelFor(site);
    const finalLabel = finalLabelParts.topic ? `${finalLabelParts.host} — ${finalLabelParts.topic}` : finalLabelParts.host;

    if(data.status === 'already_crawled'){
      site.status = 'indexed';
      renderKgCards();
      updateStatusFooter();
      addSystemMessage(data.message || `<b>${finalLabel}</b> was already in the knowledge graph.`);
    }else{
      renderKgCards();
      pollCrawlStatus(site);
    }
  }catch(err){
    site.status = 'failed';
    renderKgCards();
    updateStatusFooter();
    addSystemMessage(` Failed to start crawl for <b>${label}</b> (${err.message}). Please check the backend connection.`);
  }
});

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


async function loadChatsFromBackend(){
  try{
    const res = await safeFetch(`${API_BASE_URL}/chat/list`);
    if(!res.ok) throw new Error(`Backend returned ${res.status}`);
    const data = await res.json();
    const list = data.chats || [];

    const alreadyLoaded = {};
    chats.forEach(c => { if(c.messages) alreadyLoaded[c.id] = c.messages; });

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



renderHistoryList();
renderKgCards();
if(window.innerWidth > 768) sidebar.classList.add('open');
loadSourcesFromBackend();
loadChatsFromBackend();
