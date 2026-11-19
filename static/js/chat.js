import { api } from "./api.js";
import { renderMarkdown } from "./markdown.js";

const MAX_LENGTH = 500;

const timeFormat = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
const dateFormat = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", year: "numeric" });
const fullFormat = new Intl.DateTimeFormat("ru-RU", { dateStyle: "long", timeStyle: "medium" });

function dayLabel(date) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return "Сегодня";
  if (date.toDateString() === yesterday.toDateString()) return "Вчера";
  return dateFormat.format(date);
}

export function initChat() {
  const scroller = document.getElementById("messages");
  const list = document.getElementById("message-list");
  const empty = document.getElementById("empty-state");
  const typing = document.getElementById("typing");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const sendBtn = document.getElementById("send-btn");
  const counter = document.getElementById("counter");
  const errorBox = document.getElementById("chat-error");
  const errorText = document.getElementById("chat-error-text");
  const clearBtn = document.getElementById("clear-btn");

  let pending = false;
  let lastDay = null;


  const scrollToBottom = () => {
    scroller.scrollTop = scroller.scrollHeight;
  };

  const updateEmptyState = () => {
    empty.hidden = list.children.length > 0 || pending;
  };

  const appendMessage = (message) => {
    const date = new Date(message.created_at);
    const day = date.toDateString();
    if (day !== lastDay) {
      const divider = document.createElement("div");
      divider.className = "day-divider";
      divider.textContent = dayLabel(date);
      list.append(divider);
      lastDay = day;
    }

    const wrapper = document.createElement("div");
    wrapper.className = `msg msg--${message.role}`;

    const bubble = document.createElement("div");
    bubble.className = "msg__bubble";
    if (message.role === "assistant") {
      bubble.innerHTML = renderMarkdown(message.content);
    } else {
      bubble.textContent = message.content;
    }

    const time = document.createElement("time");
    time.className = "msg__time";
    time.dateTime = message.created_at;
    time.textContent = timeFormat.format(date);
    time.title = fullFormat.format(date);

    wrapper.append(bubble, time);
    list.append(wrapper);
  };

  const renderAll = (messages) => {
    list.replaceChildren();
    lastDay = null;
    messages.forEach(appendMessage);
    updateEmptyState();
    scrollToBottom();
  };


  const showError = (message) => {
    errorText.textContent = message;
    errorBox.hidden = false;
  };
  const hideError = () => {
    errorBox.hidden = true;
  };

  const autosize = () => {
    input.style.height = "auto";
    input.style.height = `${input.scrollHeight}px`;
  };

  const updateComposer = () => {
    const length = input.value.length;
    counter.textContent = `${length} / ${MAX_LENGTH}`;
    counter.classList.toggle("is-near", length >= MAX_LENGTH * 0.9 && length <= MAX_LENGTH);
    counter.classList.toggle("is-over", length > MAX_LENGTH);
    const valid = input.value.trim().length > 0 && length <= MAX_LENGTH;
    sendBtn.disabled = pending || !valid;
    autosize();
  };

  const setPending = (value) => {
    pending = value;
    typing.hidden = !value;
    clearBtn.disabled = value;
    updateEmptyState();
    updateComposer();
    if (value) scrollToBottom();
  };


  const send = async () => {
    const text = input.value.trim();
    if (pending || !text || text.length > MAX_LENGTH) return;

    hideError();
    const draft = { role: "user", content: text, created_at: new Date().toISOString() };
    appendMessage(draft);
    const draftNode = list.lastElementChild;
    const savedInput = input.value;
    input.value = "";
    setPending(true);

    try {
      const { assistant_message } = await api.sendMessage(text);
      appendMessage(assistant_message);
    } catch (err) {
      draftNode.remove();
      const prev = list.lastElementChild;
      if (prev && prev.classList.contains("day-divider")) {
        prev.remove();
        lastDay = null;
      }
      if (err.status !== 401) {
        input.value = savedInput;
        showError(err.message);
      }
    } finally {
      setPending(false);
      scrollToBottom();
      input.focus();
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    send();
  });

  input.addEventListener("input", updateComposer);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      send();
    }
  });

  document.getElementById("chat-error-close").addEventListener("click", hideError);

  empty.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      input.value = chip.textContent;
      updateComposer();
      input.focus();
    });
  });

  clearBtn.addEventListener("click", async () => {
    if (!list.children.length) return;
    if (!confirm("Удалить всю историю переписки?")) return;
    try {
      await api.clearMessages();
      renderAll([]);
      hideError();
    } catch (err) {
      if (err.status !== 401) showError(err.message);
    }
  });

  return {
    async load() {
      hideError();
      try {
        renderAll(await api.getMessages());
      } catch (err) {
        if (err.status !== 401) showError(err.message);
      }
      updateComposer();
      input.focus();
    },
    reset() {
      list.replaceChildren();
      lastDay = null;
      input.value = "";
      hideError();
      updateComposer();
    },
  };
}
