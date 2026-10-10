/* ---------- CONFIG: point these at your RAG backend ---------- */
const CONFIG = {
  ASK_URL: "/api/ask",
  STATUS_URL: "/api/status",
  USE_MOCK: false,
};
/* -------------------------------------------------------------- */

const STORE_KEY = "novatech_history";
const $ = (id) => document.getElementById(id);

const exchange = $("exchange");
const form = $("askForm");
const input = $("questionInput");
const sendBtn = $("sendBtn");

let history = JSON.parse(localStorage.getItem(STORE_KEY) || "[]");

/* ---------- Helpers ---------- */
function save() {
  localStorage.setItem(STORE_KEY, JSON.stringify(history));
  $("historyCount").textContent = history.length;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text; // textContent keeps answers safe from HTML injection
  return node;
}

function formatTime(ts) {
  return new Date(ts).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

/* ---------- Views (Assistant / History) ---------- */
function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + name));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === name));
  $("composer").classList.toggle("hidden", name === "history");
  if (name === "history") renderHistory();
}
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showView(t.dataset.view)));

/* ---------- Knowledge base status ---------- */
function setStatus(state, message) {
  const banner = $("statusBanner");
  const pill = $("statusPill");
  banner.className = "banner banner-" + state;
  banner.textContent = (state === "ok" ? "✅ " : state === "err" ? "⚠️ " : "") + message;
  pill.className = "pill pill-" + state;
  pill.lastElementChild.textContent = state === "ok" ? "Ready" : state === "err" ? "Offline" : "Connecting";
}

async function loadStatus() {
  try {
    if (CONFIG.USE_MOCK) { setStatus("ok", "Ready — 120 document chunks indexed."); return; }
    const res = await fetch(CONFIG.STATUS_URL);
    if (!res.ok) throw new Error();
    const data = await res.json();
    setStatus("ok", `Ready — ${data.chunks} document chunks indexed.`);
  } catch {
    setStatus("err", "Can't reach the knowledge base. Check that the backend is running.");
  }
}

/* ---------- Question + answer display ---------- */
function buildCard(type, label, body) {
  const card = el("div", "qa-card " + type);
  card.append(el("div", "qa-label", label), el("div", "qa-body", body));
  return card;
}

function typingIndicator() {
  const wrap = el("div", "typing");
  wrap.append(el("span"), el("span"), el("span"));
  return wrap;
}

// Shows one question/answer pair. Both sections are created here, so nothing
// is on the page until a question is asked, and each new question replaces the last.
function renderExchange(item) {
  exchange.replaceChildren();
  const qCard = buildCard("question", "Question", item.question);
  exchange.append(qCard);
  const aCard = buildCard("answer", "Answer", item.answer || "");
  if (item.sources && item.sources.length) {
    const box = el("div", "sources");
    item.sources.forEach((s) => box.append(el("span", "source-chip", s)));
    aCard.append(box);
  }
  aCard.append(el("div", "qa-time", formatTime(item.time)));
  exchange.append(aCard);
}


async function fetchAnswer(question) {
  const res = await fetch(CONFIG.ASK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.error || "Server returned " + res.status);
  }

  return data;
}
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  input.value = "";
  sendBtn.disabled = true;
  showView("chat");

  // Question appears immediately; answer section shows a typing indicator until the reply arrives
  exchange.replaceChildren(buildCard("question", "Question", question));
  const aCard = buildCard("answer", "Answer", "");
  aCard.querySelector(".qa-body").append(typingIndicator());
  exchange.append(aCard);

  try {
    const data = await fetchAnswer(question);
    const item = { id: Date.now(), question, answer: data.answer, sources: data.sources || [], time: Date.now() };
    history.unshift(item);
    save();
    renderExchange(item);
  } catch (err) {
    exchange.lastElementChild.remove();
    const errCard = buildCard("answer error", "Answer", "Something went wrong while getting the answer. Check your connection and try again.");
    exchange.append(errCard);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

$("newChatBtn").addEventListener("click", () => {
  exchange.replaceChildren();
  showView("chat");
  input.focus();
});

/* ---------- History page ---------- */
function renderHistory() {
  const list = $("historyList");
  const term = $("historySearch").value.trim().toLowerCase();
  list.replaceChildren();

  const items = history.filter((h) => h.question.toLowerCase().includes(term));
  if (!items.length) {
    const msg = history.length ? "No questions match your search." : "No questions yet. Ask one from the Assistant tab.";
    list.append(el("li", "empty", msg));
    return;
  }

  items.forEach((h) => {
    const li = el("li", "history-item");
    const text = el("div");
    text.append(
      el("div", "history-q", h.question),
      el("div", "history-a", h.answer),
      el("div", "history-meta", formatTime(h.time))
    );
    const del = el("button", "history-del", "×");
    del.title = "Delete";
    del.setAttribute("aria-label", "Delete this question");
    del.addEventListener("click", (e) => {
      e.stopPropagation();
      history = history.filter((x) => x.id !== h.id);
      save();
      renderHistory();
    });
    li.append(text, del);
    li.addEventListener("click", () => { renderExchange(h); showView("chat"); });
    list.append(li);
  });
}

$("historySearch").addEventListener("input", renderHistory);
$("clearHistoryBtn").addEventListener("click", () => {
  if (history.length && confirm("Delete all history?")) {
    history = [];
    save();
    renderHistory();
  }
});

/* ---------- Init ---------- */
save();
loadStatus();