// Shared across index.html, dashboard.html, pr_guardian.html
let users = [];
let currentUser = null;

const profileName = document.getElementById("profile-name");
const profileRole = document.getElementById("profile-role");
const avatarLetter = document.getElementById("avatar-letter");
const personaMenu = document.getElementById("persona-menu");
const profileStrip = document.getElementById("profile-strip");
const navDashboard = document.getElementById("nav-dashboard");
const navPrGuardian = document.getElementById("nav-pr-guardian");

// ---------- session-scoped chat storage ----------
const CHATS_KEY = "fossilize_chats";
const CURRENT_KEY = "fossilize_current_chat_id";

function loadChats() {
  try {
    return JSON.parse(sessionStorage.getItem(CHATS_KEY)) || [];
  } catch {
    return [];
  }
}
function saveChats(chats) {
  sessionStorage.setItem(CHATS_KEY, JSON.stringify(chats));
}
function getCurrentChatId() {
  return sessionStorage.getItem(CURRENT_KEY);
}
function setCurrentChatId(id) {
  sessionStorage.setItem(CURRENT_KEY, id);
}

function createChat() {
  const chats = loadChats();
  const newChat = {
    id: "chat_" + Date.now(),
    title: "New chat",
    history: [],
    archived: false
  };
  chats.unshift(newChat);
  saveChats(chats);
  setCurrentChatId(newChat.id);
  return newChat;
}

function getCurrentChat() {
  const chats = loadChats();
  let current = chats.find(c => c.id === getCurrentChatId());
  if (!current) {
    current = chats.find(c => !c.archived) || createChat();
    setCurrentChatId(current.id);
  }
  return current;
}

function updateCurrentChat(updater) {
  const chats = loadChats();
  const idx = chats.findIndex(c => c.id === getCurrentChatId());
  if (idx === -1) return;
  updater(chats[idx]);
  saveChats(chats);
}

function renderRecents() {
  const chats = loadChats().filter(c => !c.archived);
  const list = document.getElementById("recents-list");
  if (!list) return;
  const currentId = getCurrentChatId();
  if (!chats.length) {
    list.innerHTML = `<div class="empty-state" style="padding:12px 10px;">No chats yet</div>`;
    return;
  }
  list.innerHTML = chats.map(c => `
    <div class="recent-item ${c.id === currentId ? 'active' : ''}" data-id="${c.id}">
      <span class="recent-title" data-id="${c.id}">${escapeHtmlLocal(c.title)}</span>
      <span class="dots" data-id="${c.id}">&#8942;</span>
      <div class="recent-menu" data-id="${c.id}">
        <div class="recent-menu-item" data-action="rename">Rename</div>
        <div class="recent-menu-item" data-action="archive">Archive</div>
        <div class="recent-menu-item danger" data-action="delete">Delete</div>
      </div>
    </div>
  `).join("");

  list.querySelectorAll(".recent-item").forEach(item => {
    item.addEventListener("click", (e) => {
      if (e.target.closest(".dots") || e.target.closest(".recent-menu") || e.target.tagName === "INPUT") return;
      setCurrentChatId(item.getAttribute("data-id"));
      if (typeof loadCurrentChatIntoWindow === "function") {
        loadCurrentChatIntoWindow();
        renderRecents();
      } else {
        window.location.href = "/";
      }
    });
  });

  list.querySelectorAll(".dots").forEach(dot => {
    dot.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = dot.getAttribute("data-id");
      document.querySelectorAll(".recent-menu").forEach(m => {
        m.classList.toggle("open", m.getAttribute("data-id") === id && !m.classList.contains("open"));
      });
    });
  });

  

  list.querySelectorAll(".recent-menu-item").forEach(menuItem => {
    menuItem.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = menuItem.closest(".recent-menu").getAttribute("data-id");
      const action = menuItem.getAttribute("data-action");
      document.querySelectorAll(".recent-menu").forEach(m => m.classList.remove("open"));
      if (action === "delete") deleteChatById(id);
      if (action === "archive") archiveChatById(id);
      if (action === "rename") startInlineRename(id);
    });
  });
}

function startInlineRename(id) {
  const span = document.querySelector(`.recent-title[data-id="${id}"]`);
  if (!span) return;
  const chats = loadChats();
  const chat = chats.find(c => c.id === id);
  const input = document.createElement("input");
  input.type = "text";
  input.value = chat.title;
  input.className = "recent-title-input";
  span.replaceWith(input);
  input.focus();
  input.select();

  function commit() {
    const newTitle = input.value.trim() || "New chat";
    updateChat(id, c => { c.title = newTitle; });
    renderRecents();
  }
  let cancelled = false;
  input.addEventListener("blur", () => { if (!cancelled) commit(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") input.blur();
    if (e.key === "Escape") { cancelled = true; renderRecents(); }
  });
}

function escapeHtmlLocal(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
function updateChat(id, updater) {
  const chats = loadChats();
  const idx = chats.findIndex(c => c.id === id);
  if (idx === -1) return;
  updater(chats[idx]);
  saveChats(chats);
}

function deleteChatById(id) {
  const chats = loadChats();
  const wasCurrent = id === getCurrentChatId();
  const remaining = chats.filter(c => c.id !== id);
  saveChats(remaining);

  if (wasCurrent) {
    const stillOpen = remaining.filter(c => !c.archived);
    if (!stillOpen.length) createChat();
    else setCurrentChatId(stillOpen[0].id);
    if (typeof loadCurrentChatIntoWindow === "function") loadCurrentChatIntoWindow();
  }
  renderRecents();
}

function archiveChatById(id) {
  updateChat(id, chat => { chat.archived = true; });
  const wasCurrent = id === getCurrentChatId();
  if (wasCurrent) {
    const remaining = loadChats().filter(c => !c.archived);
    if (!remaining.length) createChat();
    else setCurrentChatId(remaining[0].id);
    if (typeof loadCurrentChatIntoWindow === "function") loadCurrentChatIntoWindow();
  }
  renderRecents();
}
// initial load
if (!loadChats().length) createChat();
renderRecents();


async function loadUsers() {
  try {
    const res = await fetch("/api/users");
    users = await res.json();
  } catch (err) {
    console.error("Failed to load users", err);
    users = [];
  }
  if (users.length) {
    const savedId = sessionStorage.getItem("fossilize_persona_id");
    const saved = savedId ? users.find(u => u.id === savedId) : null;
    currentUser = saved || users[0];
    renderProfile();
    renderPersonaMenu();
    applyRoleAccess();
    document.dispatchEvent(new CustomEvent("persona-loaded", { detail: currentUser }));
  } else {
    profileName.textContent = "Unavailable";
    profileRole.textContent = "";
  }
}
// Auto-expand sidebar if any nav item or the profile strip is clicked while collapsed
document.getElementById("sidebar").addEventListener("click", (e) => {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar.classList.contains("collapsed")) return;

  const isCollapseBtn = e.target.closest("#collapse-btn");
  const isNavOrProfile = e.target.closest(".nav-item, .profile-strip");

  if (isNavOrProfile && !isCollapseBtn) {
    sidebar.classList.remove("collapsed");
  }
}, true); // capture phase — runs before the nav item's own onclick/navigation

function renderProfile() {
  if (!currentUser) return;
  profileName.textContent = currentUser.name;
  profileRole.textContent = currentUser.role;
  avatarLetter.textContent = (currentUser.name || "?").charAt(0).toUpperCase();
}

function applyRoleAccess() {
  const isManager = currentUser && currentUser.role === "manager";
  [navDashboard, navPrGuardian].forEach(el => {
    if (!el) return;
    el.classList.toggle("disabled", !isManager);
    el.title = isManager ? "" : "Manager access only";
  });
}

function renderPersonaMenu() {
  personaMenu.innerHTML = users.map(u => `
    <div class="persona-option ${currentUser && u.id === currentUser.id ? 'selected' : ''}" data-id="${u.id}">
      <div class="avatar" style="width:24px;height:24px;font-size:11px;">${(u.name||'?').charAt(0).toUpperCase()}</div>
      <div>
        <div style="font-weight:600;">${u.name}</div>
        <div style="font-size:11px;color:var(--text-muted);">${u.role}</div>
      </div>
    </div>
  `).join("");
  personaMenu.querySelectorAll(".persona-option").forEach(el => {
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      const id = el.getAttribute("data-id");
      currentUser = users.find(u => u.id === id) || currentUser;
      sessionStorage.setItem("fossilize_persona_id", currentUser.id);
      renderProfile();
      renderPersonaMenu();
      applyRoleAccess();
      personaMenu.classList.remove("open");
      // let the page react if it needs to (e.g. re-render dashboard access state)
      document.dispatchEvent(new CustomEvent("persona-changed", { detail: currentUser }));
    });
  });
}

profileStrip.addEventListener("click", () => {
  personaMenu.classList.toggle("open");
});
document.addEventListener("click", (e) => {
  if (!profileStrip.contains(e.target)) personaMenu.classList.remove("open");
});
document.addEventListener("click", () => {
  document.querySelectorAll(".recent-menu").forEach(m => m.classList.remove("open"));
});
const collapseBtn = document.getElementById("collapse-btn");
if (collapseBtn) {
  collapseBtn.addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("collapsed");
  });
}

// highlight current page in nav — expects each page's active <div class="nav-item"> to carry data-page="chat|dashboard|pr-guardian"
(function highlightCurrentPage() {
  const path = window.location.pathname;
  const map = { "/": "chat", "/dashboard": "dashboard", "/pr-guardian": "pr-guardian" };
  const current = map[path];
  document.querySelectorAll(".nav-item[data-page]").forEach(el => {
    el.classList.toggle("current", el.getAttribute("data-page") === current);
  });
})();
(function setupSidebarResize() {
  const sidebar = document.getElementById("sidebar");
  const handle = document.getElementById("sidebar-resize-handle");
  if (!sidebar || !handle) return;

  const MIN_WIDTH = 230;
  const MAX_WIDTH = 420;
  let dragging = false;

  handle.addEventListener("mousedown", (e) => {
    if (sidebar.classList.contains("collapsed")) return;
    dragging = true;
    handle.classList.add("dragging");
    document.body.classList.add("resizing-sidebar");
    e.preventDefault();
  });

  document.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const newWidth = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, e.clientX));
    sidebar.style.width = newWidth + "px";
    sidebar.style.minWidth = newWidth + "px";
  });

  document.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove("dragging");
    document.body.classList.remove("resizing-sidebar");
  });
})();
loadUsers();