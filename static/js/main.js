import { api, setUnauthorizedHandler } from "./api.js";
import { initChat } from "./chat.js";
import { initLogin } from "./login.js";

const screens = {
  boot: document.getElementById("boot"),
  login: document.getElementById("login-screen"),
  chat: document.getElementById("chat-screen"),
};

function show(name) {
  for (const [key, node] of Object.entries(screens)) node.hidden = key !== name;
}

const chat = initChat();

function openChat() {
  show("chat");
  chat.load();
}

function openLogin() {
  chat.reset();
  show("login");
  login.focus();
}

const login = initLogin({ onSuccess: openChat });

setUnauthorizedHandler(openLogin);

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await api.logout();
  } finally {
    openLogin();
  }
});

api.checkSession().then(openChat, openLogin);
