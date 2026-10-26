import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";

type Phase = "idle" | "countdown" | "running" | "paused" | "stopped" | "error";
type MouseButton = "left" | "right";
type Effect = "mica" | "acrylic";

interface Status {
  phase: Phase;
  message: string;
  clicks: number;
}

interface Prefs {
  interval: string;
  button: MouseButton;
  effect: Effect;
  delay: number;
}

const MIN_INTERVAL_S = 0.01;
const PREFS_KEY = "autoclicker.prefs.v2";

const ACTION_LABEL: Record<Phase, string> = {
  idle: "开始连点",
  countdown: "取消",
  running: "暂停",
  paused: "继续连点",
  stopped: "开始连点",
  error: "重新开始",
};

const el = <T extends HTMLElement>(selector: string): T => {
  const node = document.querySelector<T>(selector);
  if (!node) throw new Error(`元素缺失：${selector}`);
  return node;
};

const dot = el<HTMLSpanElement>("#dot");
const statusText = el<HTMLParagraphElement>("#status-text");
const clickCount = el<HTMLSpanElement>("#click-count");
const metaClicks = el<HTMLSpanElement>("#meta-clicks");
const metaHint = el<HTMLSpanElement>("#meta-hint");
const intervalInput = el<HTMLInputElement>("#interval");
const actionBtn = el<HTMLButtonElement>("#action");
const segmented = el<HTMLDivElement>("#segmented");
const delaySegmented = el<HTMLDivElement>("#delay-segmented");
const hotkeyStatus = el<HTMLParagraphElement>("#hotkey-status");

const appWindow = getCurrentWindow();

const DELAY_OPTIONS = [0, 1000, 3000, 5000];

let phase: Phase = "idle";
let button: MouseButton = "left";
let effect: Effect = "acrylic";
let delayMs = 3000;
let clickPoll: number | undefined;

// ---------- 偏好持久化 ----------

function loadPrefs(): Prefs {
  const fallback: Prefs = { interval: "0.1", button: "left", effect: "acrylic", delay: 3000 };
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as Partial<Prefs>;
    return {
      interval: typeof parsed.interval === "string" ? parsed.interval : fallback.interval,
      button: parsed.button === "right" ? "right" : "left",
      effect: parsed.effect === "mica" ? "mica" : "acrylic",
      delay:
        typeof parsed.delay === "number" && DELAY_OPTIONS.includes(parsed.delay)
          ? parsed.delay
          : fallback.delay,
    };
  } catch {
    return fallback;
  }
}

function savePrefs(): void {
  const prefs: Prefs = { interval: intervalInput.value, button, effect, delay: delayMs };
  localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
}

// ---------- 间隔解析 ----------

/** 把输入框内容解析成毫秒；非法返回 null */
function parseInterval(text: string): number | null {
  if (!/^\d*\.?\d*$/.test(text) || text === "" || text === ".") return null;
  const seconds = Number.parseFloat(text);
  if (!Number.isFinite(seconds) || seconds <= 0) return null;
  const clamped = Math.max(seconds, MIN_INTERVAL_S);
  return Math.round(clamped * 1000);
}

function refreshIntervalValidity(): number | null {
  const ms = parseInterval(intervalInput.value);
  intervalInput.classList.toggle("is-invalid", ms === null);
  return ms;
}

// ---------- 状态渲染 ----------

function render(status: Status): void {
  phase = status.phase;
  dot.dataset.phase = status.phase;
  statusText.textContent = status.message;
  actionBtn.textContent = ACTION_LABEL[status.phase];
  actionBtn.dataset.phase = status.phase;
  clickCount.textContent = String(status.clicks);

  // 倒计时阶段把「点击次数」换成移开鼠标的提醒
  const counting = status.phase === "countdown";
  metaClicks.hidden = counting;
  metaHint.hidden = !counting;

  if (status.phase === "running" && clickPoll === undefined) {
    clickPoll = window.setInterval(() => {
      void invoke<Status>("status").then(render).catch(() => undefined);
    }, 250);
  } else if (status.phase !== "running" && clickPoll !== undefined) {
    window.clearInterval(clickPoll);
    clickPoll = undefined;
  }
}

// ---------- 交互 ----------

async function onAction(): Promise<void> {
  const ms = refreshIntervalValidity();
  if (ms === null) {
    intervalInput.focus();
    return;
  }
  savePrefs();
  await invoke("apply_config", { intervalMs: ms, button, delayMs });
  if (phase === "running" || phase === "countdown") {
    await invoke("pause");
  } else {
    await invoke("start");
  }
}

/** 把当前配置推给后端；间隔不合法时先不动，等用户改好 */
function pushConfig(): void {
  const ms = parseInterval(intervalInput.value);
  if (ms === null) return;
  void invoke("apply_config", { intervalMs: ms, button, delayMs }).catch(() => undefined);
}

function setButton(next: MouseButton): void {
  button = next;
  segmented.querySelectorAll<HTMLButtonElement>(".seg").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.button === next);
  });
  savePrefs();
  pushConfig();
}

function setDelay(next: number): void {
  delayMs = next;
  delaySegmented.querySelectorAll<HTMLButtonElement>(".seg").forEach((node) => {
    node.classList.toggle("is-active", Number(node.dataset.delay) === next);
  });
  savePrefs();
  pushConfig();
}

function syncEffectButtons(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-effect]").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.effect === effect);
  });
}

async function setEffect(next: Effect): Promise<void> {
  try {
    await invoke("set_effect", { effect: next });
  } catch (error) {
    // Mica 在透明窗口上不一定生效，失败就退回 Acrylic
    if (next === "mica") {
      effect = "acrylic";
      syncEffectButtons();
      savePrefs();
      await invoke("set_effect", { effect: "acrylic" }).catch(() => undefined);
      return;
    }
    throw error;
  }
  effect = next;
  syncEffectButtons();
  savePrefs();
}

function bind(): void {
  actionBtn.addEventListener("click", () => void onAction().catch(reportError));

  intervalInput.addEventListener("input", () => {
    // 只允许数字和一个小数点，避免中文输入法污染
    const cleaned = intervalInput.value.replace(/[^\d.]/g, "");
    if (cleaned !== intervalInput.value) intervalInput.value = cleaned;
    refreshIntervalValidity();
  });

  intervalInput.addEventListener("blur", () => {
    const ms = parseInterval(intervalInput.value);
    if (ms === null) {
      intervalInput.value = "0.1";
    } else if (intervalInput.value.startsWith(".")) {
      intervalInput.value = `0${intervalInput.value}`;
    }
    refreshIntervalValidity();
    savePrefs();
  });

  intervalInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void onAction().catch(reportError);
    }
  });

  document.querySelectorAll<HTMLButtonElement>("[data-preset]").forEach((node) => {
    node.addEventListener("click", () => {
      intervalInput.value = node.dataset.preset ?? "0.1";
      refreshIntervalValidity();
      savePrefs();
    });
  });

  segmented.querySelectorAll<HTMLButtonElement>(".seg").forEach((node) => {
    node.addEventListener("click", () => {
      setButton(node.dataset.button === "right" ? "right" : "left");
    });
  });

  delaySegmented.querySelectorAll<HTMLButtonElement>(".seg").forEach((node) => {
    node.addEventListener("click", () => {
      setDelay(Number(node.dataset.delay ?? 3000));
    });
  });

  document.querySelectorAll<HTMLButtonElement>("[data-effect]").forEach((node) => {
    node.addEventListener("click", () => {
      const next: Effect = node.dataset.effect === "mica" ? "mica" : "acrylic";
      void setEffect(next).catch(reportError);
    });
  });

  el<HTMLButtonElement>("#btn-min").addEventListener("click", () => {
    void appWindow.minimize();
  });

  el<HTMLButtonElement>("#btn-close").addEventListener("click", () => {
    void appWindow.close();
  });

  window.addEventListener("contextmenu", (event) => event.preventDefault());
  window.addEventListener("dragstart", (event) => event.preventDefault());
}

function reportError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  dot.dataset.phase = "error";
  statusText.textContent = `出错了：${message}`;
}

async function main(): Promise<void> {
  const prefs = loadPrefs();
  intervalInput.value = prefs.interval;
  button = prefs.button;
  effect = prefs.effect;
  delayMs = prefs.delay;

  segmented.querySelectorAll<HTMLButtonElement>(".seg").forEach((node) => {
    node.classList.toggle("is-active", node.dataset.button === button);
  });
  delaySegmented.querySelectorAll<HTMLButtonElement>(".seg").forEach((node) => {
    node.classList.toggle("is-active", Number(node.dataset.delay) === delayMs);
  });
  syncEffectButtons();

  bind();
  refreshIntervalValidity();

  await listen<Status>("status", (event) => render(event.payload));
  render(await invoke<Status>("status"));

  // 首帧渲染完毕后再应用特效，避免白闪
  await invoke("apply_config", {
    intervalMs: parseInterval(intervalInput.value) ?? MIN_INTERVAL_S * 1000,
    button,
    delayMs,
  }).catch(() => undefined);
  await setEffect(effect).catch(() => undefined);

  // 热键自检：数字变了就说明按键真的被系统读到了
  let seenTriggers = -1;
  window.setInterval(() => {
    void invoke<number>("hotkey_triggers")
      .then((count) => {
        if (count === seenTriggers) return;
        seenTriggers = count;
        hotkeyStatus.textContent =
          count === 0 ? "热键监听中" : `热键已接收 ${count} 次`;
      })
      .catch(() => undefined);
  }, 800);
}

void main();
