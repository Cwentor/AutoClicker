//! 窗口特效：Mica / Acrylic 毛玻璃 + DWM 圆角。
//!
//! 旧版靠「抓屏 + 高斯模糊」自绘，这里交给系统合成器，零抓屏开销。

use raw_window_handle::{HasWindowHandle, RawWindowHandle};
use tauri::WebviewWindow;
use window_vibrancy::{apply_acrylic, apply_mica, clear_acrylic, clear_mica};

/// 浅白磨砂底色，对齐旧版 FROST_TINT
const TINT: (u8, u8, u8, u8) = (248, 250, 255, 120);

/// DWMWA_WINDOW_CORNER_PREFERENCE = 33，DWMWCP_ROUND = 2
const DWMWA_WINDOW_CORNER_PREFERENCE: u32 = 33;
const DWMWCP_ROUND: i32 = 2;

pub fn setup(window: &WebviewWindow) {
    round_corners(window);
    // 默认 Acrylic：透明窗口下它是唯一稳定的方案，Mica 在 transparent 窗口上会失效
    if apply(window, "acrylic").is_err() {
        let _ = apply(window, "mica");
    }
}

pub fn apply(window: &WebviewWindow, kind: &str) -> Result<(), String> {
    match kind {
        "mica" => {
            let _ = clear_acrylic(window);
            apply_mica(window, Some(false)).map_err(|e| format!("Mica 不可用：{e}"))
        }
        "acrylic" => {
            let _ = clear_mica(window);
            apply_acrylic(window, Some(TINT)).map_err(|e| format!("Acrylic 不可用：{e}"))
        }
        "none" => {
            let _ = clear_acrylic(window);
            let _ = clear_mica(window);
            Ok(())
        }
        other => Err(format!("未知的特效类型：{other}")),
    }
}

pub fn round_corners(window: &WebviewWindow) {
    let Some(hwnd) = hwnd_of(window) else {
        return;
    };
    let preference = DWMWCP_ROUND;
    unsafe {
        windows_sys::Win32::Graphics::Dwm::DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            &preference as *const i32 as *const core::ffi::c_void,
            std::mem::size_of::<i32>() as u32,
        );
    }
}

fn hwnd_of(window: &WebviewWindow) -> Option<*mut core::ffi::c_void> {
    let handle = window.window_handle().ok()?;
    match handle.as_raw() {
        RawWindowHandle::Win32(win) => Some(win.hwnd.get() as *mut core::ffi::c_void),
        _ => None,
    }
}
