//! 全局热键：GetAsyncKeyState 轮询。
//!
//! 为什么不用 WH_KEYBOARD_LL 低级钩子：钩子回调在系统更新异步键状态之前
//! 被调用，且极容易被输入法、显卡驱动、游戏加速器等先注册的钩子截断
//! （低级钩子按 LIFO 顺序派发，前面的返回非零后就不往下传了）。实测在
//! 这台机器上钩子装上但一个事件都收不到，所以彻底放弃该方案。
//!
//! 轮询方案不依赖消息循环、不依赖钩子链、不受 UIPI 影响，读的是全局
//! 物理键状态，代价是常驻一个 8ms 周期的线程（CPU 占用可忽略）。

use std::io::Write;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, OnceLock};
use std::thread;
use std::time::Duration;

use windows_sys::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;

use crate::clicker::Clicker;

const VK_CONTROL_KEY: i32 = 0x11;
const VK_LCONTROL_KEY: i32 = 0xA2;
const VK_RCONTROL_KEY: i32 = 0xA3;
const VK_MENU_KEY: i32 = 0x12;
const VK_LMENU_KEY: i32 = 0xA4;
const VK_RMENU_KEY: i32 = 0xA5;
const VK_Q_KEY: i32 = 0x51;
const VK_F9_KEY: i32 = 0x78;
const VK_F10_KEY: i32 = 0x79;

/// 轮询周期。8ms 足够跟上人手按键，又不会烧 CPU
const POLL: Duration = Duration::from_millis(8);

static CLICKER: OnceLock<Arc<Clicker>> = OnceLock::new();
static LOG_READY: AtomicBool = AtomicBool::new(false);
/// 累计触发热键的次数，供界面自检
static TRIGGERS: AtomicU64 = AtomicU64::new(0);

/// 热键累计触发次数（含 Ctrl+Alt / F9 / F10 / Alt+Q）
pub fn triggers() -> u64 {
    TRIGGERS.load(Ordering::Relaxed)
}

pub fn install(clicker: Arc<Clicker>) {
    if CLICKER.set(Arc::clone(&clicker)).is_err() {
        return;
    }

    let spawned = thread::Builder::new()
        .name("hotkey-poll".into())
        .spawn(poll_loop);

    if spawned.is_err() {
        clicker.fail("热键线程启动失败");
    }
}

fn down(vk: i32) -> bool {
    unsafe { GetAsyncKeyState(vk) < 0 }
}

fn with_clicker(f: impl FnOnce(&Arc<Clicker>)) {
    if let Some(clicker) = CLICKER.get() {
        f(clicker);
    }
}

fn poll_loop() {
    log("热键轮询线程已启动");

    // 边沿检测：只在「从松到按」的那一刻动作，按住不放不重复触发
    let mut combo_latched = false;
    let mut f9_prev = false;
    let mut f10_prev = false;
    let mut alt_q_prev = false;

    loop {
        thread::sleep(POLL);

        let alt = down(VK_MENU_KEY) || down(VK_LMENU_KEY) || down(VK_RMENU_KEY);
        let ctrl = down(VK_CONTROL_KEY) || down(VK_LCONTROL_KEY) || down(VK_RCONTROL_KEY);

        let combo = ctrl && alt;
        if combo != combo_latched {
            combo_latched = combo;
            if combo {
                fire("CTRL+ALT 触发");
                with_clicker(|clicker| clicker.toggle());
            }
        }

        let f9 = down(VK_F9_KEY);
        if f9 && !f9_prev {
            fire("F9 触发");
            with_clicker(|clicker| clicker.toggle());
        }
        f9_prev = f9;

        let f10 = down(VK_F10_KEY);
        if f10 && !f10_prev {
            fire("F10 触发");
            with_clicker(|clicker| clicker.stop());
        }
        f10_prev = f10;

        let alt_q = alt && down(VK_Q_KEY);
        if alt_q && !alt_q_prev {
            fire("ALT+Q 触发");
            with_clicker(|clicker| clicker.stop());
        }
        alt_q_prev = alt_q;
    }
}

/// 记一次触发：累加计数 + 落日志
fn fire(label: &str) {
    TRIGGERS.fetch_add(1, Ordering::Relaxed);
    log(label);
}

/// 诊断日志：每次启动覆盖，路径 %LOCALAPPDATA%\com.catdrink.autoclicker\hotkey.log
fn log(message: &str) {
    let Some(dir) = std::env::var_os("LOCALAPPDATA") else {
        return;
    };
    let path = std::path::PathBuf::from(dir)
        .join("com.catdrink.autoclicker")
        .join("hotkey.log");
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let fresh = !LOG_READY.swap(true, Ordering::Relaxed);
    let mut options = std::fs::OpenOptions::new();
    options.create(true).write(true);
    if fresh {
        options.truncate(true);
    } else {
        options.append(true);
    }
    if let Ok(mut file) = options.open(path) {
        let _ = writeln!(file, "{message}");
    }
}
