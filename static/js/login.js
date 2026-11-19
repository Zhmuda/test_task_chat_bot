import { api } from "./api.js";

const KEY_PATTERN = /^[A-Za-z0-9_-]{8,255}$/;

function validateKey(value) {
  if (!value) return "";
  if (/[^A-Za-z0-9_-]/.test(value)) return "Допустимы только латинские буквы, цифры, «-» и «_»";
  if (value.length < 8) return `Минимум 8 символов (сейчас ${value.length})`;
  if (value.length > 255) return "Максимум 255 символов";
  return "";
}

export function initLogin({ onSuccess }) {
  const form = document.getElementById("login-form");
  const input = document.getElementById("access-key");
  const button = document.getElementById("login-btn");
  const error = document.getElementById("key-error");
  const control = input.closest(".field__control");
  const toggle = document.getElementById("toggle-key");

  let submitting = false;

  const setError = (message) => {
    error.textContent = message;
    control.classList.toggle("is-invalid", Boolean(message));
    input.setAttribute("aria-invalid", String(Boolean(message)));
  };

  const update = () => {
    setError(validateKey(input.value));
    button.disabled = submitting || !KEY_PATTERN.test(input.value);
  };

  input.addEventListener("input", update);

  toggle.addEventListener("click", () => {
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    toggle.setAttribute("aria-label", show ? "Скрыть ключ" : "Показать ключ");
    toggle.title = toggle.getAttribute("aria-label");
    input.focus();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (button.disabled) return;

    submitting = true;
    button.classList.add("is-loading");
    update();
    try {
      await api.login(input.value);
      input.value = "";
      setError("");
      onSuccess();
    } catch (err) {
      setError(err.message);
      form.classList.remove("shake");
      void form.offsetWidth;
      form.classList.add("shake");
      input.select();
    } finally {
      submitting = false;
      button.classList.remove("is-loading");
      update();
    }
  });

  return {
    focus: () => input.focus(),
  };
}
