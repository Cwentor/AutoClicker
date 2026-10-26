//! 鼠标连点器 - Tauri 2 入口。
//!
//! 分工：碰系统输入/窗口的都在 Rust，其余全交给前端 TS。

mod clicker;
mod effects;
mod hotkey;

use std::sync::Arc;

use tauri::{Manager, RunEvent, WebviewWindow, WindowEvent};

use clicker::{Clicker, MouseButton, Status};

struct AppState {
    clicker: Arc<Clicker>,
}

#[tauri::command]
fn apply_config(
    state: tauri::State<'_, AppState>,
    interval_ms: u64,
    button: MouseButton,
    delay_ms: u64,
) {
    state.clicker.set_config(interval_ms, button, delay_ms);
}

#[tauri::command]
fn start(state: tauri::State<'_, AppState>) {
    state.clicker.start();
}

#[tauri::command]
fn pause(state: tauri::State<'_, AppState>) {
    state.clicker.pause();
}

#[tauri::command]
fn stop(state: tauri::State<'_, AppState>) {
    state.clicker.stop();
}

#[tauri::command]
fn toggle(state: tauri::State<'_, AppState>) {
    state.clicker.toggle();
}

#[tauri::command]
fn status(state: tauri::State<'_, AppState>) -> Status {
    state.clicker.status()
}

/// 热键已触发的次数，用于界面自检「到底有没有收到按键」
#[tauri::command]
fn hotkey_triggers() -> u64 {
    hotkey::triggers()
}

#[tauri::command]
fn set_effect(window: WebviewWindow, effect: String) -> Result<(), String> {
    effects::apply(&window, &effect)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // 二次启动时把已有窗口拉到前台，不重复挂热键
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .setup(|app| {
            let window = app
                .get_webview_window("main")
                .expect("主窗口不存在，检查 tauri.conf.json");

            effects::setup(&window);

            let clicker = Clicker::new(app.handle().clone());
            // 记下窗口矩形，点击前用它判断鼠标是否压在自己窗口上
            if let (Ok(pos), Ok(size)) = (window.outer_position(), window.outer_size()) {
                clicker.set_window_rect(pos.x, pos.y, size.width, size.height);
            }
            hotkey::install(Arc::clone(&clicker));
            app.manage(AppState { clicker });

            // 特效先就位再显示，避免白色闪屏
            window.show()?;
            window.set_focus()?;
            Ok(())
        })
        .on_window_event(|window, event| {
            match event {
                WindowEvent::CloseRequested { .. } | WindowEvent::Destroyed => {
                    if let Some(state) = window.try_state::<AppState>() {
                        state.clicker.shutdown();
                    }
                }
                // 拖动窗口后同步矩形，否则「鼠标在窗口上」的判断会错位
                WindowEvent::Moved(pos) => {
                    if let Some(state) = window.try_state::<AppState>() {
                        if let Ok(size) = window.outer_size() {
                            state
                                .clicker
                                .set_window_rect(pos.x, pos.y, size.width, size.height);
                        }
                    }
                }
                _ => {}
            }
        })
        .invoke_handler(tauri::generate_handler![
            apply_config,
            start,
            pause,
            stop,
            toggle,
            status,
            hotkey_triggers,
            set_effect
        ])
        .build(tauri::generate_context!())
        .expect("Tauri 应用初始化失败");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = app_handle.try_state::<AppState>() {
                state.clicker.shutdown();
            }
        }
    });
}
