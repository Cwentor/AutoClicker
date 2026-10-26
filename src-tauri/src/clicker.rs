//! 点击引擎。
//!
//! 独立线程 + 原子开关：前端只管调命令，线程自己转圈点击。
//! 间隔精度靠「截止时间 + 分片等待 + spin_sleep」保证——Windows 默认
//! 定时器分辨率 15.6ms，裸 `thread::sleep` 会把 10ms 睡成 15ms 以上。
//!
//! 延迟启动：点击首个落点必然是当前鼠标位置。若鼠标还压在连点器自己
//! 的窗口按钮上，第一次点击就会点中「暂停」，表现为「刚开就停」。所以
//! 启动前留一段倒计时让用户把鼠标挪开，倒计时结束仍在窗口内则拒绝启动。

use std::sync::atomic::{AtomicBool, AtomicU64, AtomicU8, Ordering};
use std::sync::{Arc, Mutex, MutexGuard};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant};

use enigo::{Button, Direction, Enigo, Mouse, Settings};
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};

/// 最小点击间隔（毫秒），对齐旧版 0.01s 的下限
pub const MIN_INTERVAL_MS: u64 = 10;
/// 防失控保护区：鼠标进入屏幕左上角该像素范围内立即停止
const FAILSAFE_ZONE: i32 = 3;
/// 等待分片上限：兼顾响应速度（暂停/停止延迟）与 CPU 占用
const WAIT_SLICE: Duration = Duration::from_millis(20);
/// 距离截止时间不足该值时改用自旋，保证精度
const SPIN_GUARD: Duration = Duration::from_millis(1);
/// 倒计时刷新粒度
const COUNTDOWN_TICK: Duration = Duration::from_millis(40);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum MouseButton {
    Left,
    Right,
}

impl MouseButton {
    fn code(self) -> u8 {
        match self {
            Self::Left => 0,
            Self::Right => 1,
        }
    }

    fn from_code(code: u8) -> Self {
        if code == 1 {
            Self::Right
        } else {
            Self::Left
        }
    }

    fn enigo(self) -> Button {
        match self {
            Self::Left => Button::Left,
            Self::Right => Button::Right,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Phase {
    Idle,
    /// 延迟启动倒计时中
    Countdown,
    Running,
    Paused,
    Stopped,
    Error,
}

/// 推给前端的状态快照，事件名 `status`
#[derive(Debug, Clone, Serialize)]
pub struct Status {
    pub phase: Phase,
    pub message: String,
    pub clicks: u64,
}

pub struct Clicker {
    app: AppHandle,
    /// 是否处于连点中（热键/按钮共用的唯一开关）
    running: AtomicBool,
    /// 是否处于延迟启动倒计时中
    counting: AtomicBool,
    /// 线程退出标志
    shutdown: AtomicBool,
    interval_ms: AtomicU64,
    /// 启动延迟（毫秒）
    delay_ms: AtomicU64,
    /// 已播报的倒计时秒数，避免重复 emit
    countdown_secs: AtomicU64,
    button: AtomicU8,
    clicks: AtomicU64,
    /// 倒计时截止时刻
    countdown_end: Mutex<Option<Instant>>,
    /// 主窗口矩形（物理像素），用于判断鼠标是否压在自己窗口上
    window_rect: Mutex<Option<(i32, i32, i32, i32)>>,
    /// 上一次判断时鼠标是否在窗口内，用于状态切换播报
    over_app: AtomicBool,
    phase: Mutex<(Phase, String)>,
    worker: Mutex<Option<JoinHandle<()>>>,
}

impl Clicker {
    pub fn new(app: AppHandle) -> Arc<Self> {
        Arc::new(Self {
            app,
            running: AtomicBool::new(false),
            counting: AtomicBool::new(false),
            shutdown: AtomicBool::new(false),
            interval_ms: AtomicU64::new(100),
            delay_ms: AtomicU64::new(3000),
            countdown_secs: AtomicU64::new(u64::MAX),
            button: AtomicU8::new(0),
            clicks: AtomicU64::new(0),
            countdown_end: Mutex::new(None),
            window_rect: Mutex::new(None),
            over_app: AtomicBool::new(false),
            phase: Mutex::new((Phase::Idle, "待机".into())),
            worker: Mutex::new(None),
        })
    }

    /// 记录主窗口矩形（物理像素），窗口移动时由 lib.rs 更新
    pub fn set_window_rect(&self, x: i32, y: i32, width: u32, height: u32) {
        let rect = (
            x,
            y,
            x.saturating_add(width as i32),
            y.saturating_add(height as i32),
        );
        *self.window_rect.lock().unwrap_or_else(|e| e.into_inner()) = Some(rect);
    }

    // ---------- 对外控制 ----------

    pub fn set_config(&self, interval_ms: u64, button: MouseButton, delay_ms: u64) {
        // 运行中改参数立即生效：线程每轮都会重读
        self.interval_ms
            .store(interval_ms.max(MIN_INTERVAL_MS), Ordering::Relaxed);
        self.button.store(button.code(), Ordering::Relaxed);
        self.delay_ms
            .store(delay_ms.min(MAX_DELAY_MS), Ordering::Relaxed);
    }

    pub fn start(self: &Arc<Self>) {
        if self.is_active() {
            return;
        }
        self.shutdown.store(false, Ordering::Relaxed);

        let delay = self.delay_ms.load(Ordering::Relaxed);
        if delay == 0 {
            self.running.store(true, Ordering::Relaxed);
            self.spawn_worker();
            self.emit(Phase::Running, "连点中");
            return;
        }

        let secs = delay.div_ceil(1000).max(1);
        self.set_countdown_end(Some(Instant::now() + Duration::from_millis(delay)));
        self.countdown_secs.store(secs, Ordering::Relaxed);
        self.counting.store(true, Ordering::Relaxed);
        self.spawn_worker();
        self.emit(Phase::Countdown, format!("{secs} 秒后开始"));
    }

    pub fn pause(&self) {
        self.running.store(false, Ordering::Relaxed);
        self.counting.store(false, Ordering::Relaxed);
        self.set_countdown_end(None);
        self.over_app.store(false, Ordering::Relaxed);
        self.emit(Phase::Paused, "已暂停");
    }

    pub fn stop(&self) {
        self.running.store(false, Ordering::Relaxed);
        self.counting.store(false, Ordering::Relaxed);
        self.set_countdown_end(None);
        self.over_app.store(false, Ordering::Relaxed);
        self.emit(Phase::Stopped, "已停止");
    }

    /// 内部错误（热键注册失败、线程异常）统一报到界面
    pub fn fail(&self, message: impl Into<String>) {
        self.running.store(false, Ordering::Relaxed);
        self.counting.store(false, Ordering::Relaxed);
        self.over_app.store(false, Ordering::Relaxed);
        self.emit(Phase::Error, message);
    }

    /// 热键入口：按当前状态反向切换（倒计时中按一下就取消）
    pub fn toggle(self: &Arc<Self>) {
        if self.is_active() {
            self.pause();
        } else {
            self.start();
        }
    }

    pub fn status(&self) -> Status {
        let (phase, message) = self.phase_lock().clone();
        Status {
            phase,
            message,
            clicks: self.clicks.load(Ordering::Relaxed),
        }
    }

    pub fn shutdown(&self) {
        self.running.store(false, Ordering::Relaxed);
        self.counting.store(false, Ordering::Relaxed);
        self.set_countdown_end(None);
        self.shutdown.store(true, Ordering::Relaxed);
        if let Some(handle) = self.worker.lock().ok().and_then(|mut w| w.take()) {
            let _ = handle.join();
        }
    }

    fn is_active(&self) -> bool {
        self.running.load(Ordering::Relaxed) || self.counting.load(Ordering::Relaxed)
    }

    // ---------- 内部 ----------

    fn phase_lock(&self) -> MutexGuard<'_, (Phase, String)> {
        self.phase.lock().unwrap_or_else(|e| e.into_inner())
    }

    fn set_countdown_end(&self, value: Option<Instant>) {
        *self.countdown_end.lock().unwrap_or_else(|e| e.into_inner()) = value;
    }

    fn countdown_end(&self) -> Option<Instant> {
        *self.countdown_end.lock().unwrap_or_else(|e| e.into_inner())
    }

    fn emit(&self, phase: Phase, message: impl Into<String>) {
        let message = message.into();
        *self.phase_lock() = (phase, message.clone());
        let payload = Status {
            phase,
            message,
            clicks: self.clicks.load(Ordering::Relaxed),
        };
        // 无窗口时（退出过程中）emit 失败可接受
        let _ = self.app.emit("status", payload);
    }

    /// 懒惰启动工作线程；已存活则复用
    fn spawn_worker(self: &Arc<Self>) {
        let mut slot = self.worker.lock().unwrap_or_else(|e| e.into_inner());
        if let Some(handle) = slot.as_ref() {
            if !handle.is_finished() {
                return;
            }
        }
        let me = Arc::clone(self);
        match thread::Builder::new()
            .name("click-worker".into())
            .spawn(move || me.worker_loop())
        {
            Ok(handle) => *slot = Some(handle),
            Err(err) => {
                drop(slot);
                self.running.store(false, Ordering::Relaxed);
                self.counting.store(false, Ordering::Relaxed);
                self.emit(Phase::Error, format!("点击线程启动失败：{err}"));
            }
        }
    }

    fn worker_loop(&self) {
        let mut enigo = match Enigo::new(&Settings::default()) {
            Ok(enigo) => enigo,
            Err(err) => {
                self.running.store(false, Ordering::Relaxed);
                self.counting.store(false, Ordering::Relaxed);
                self.emit(Phase::Error, format!("输入注入初始化失败：{err}"));
                return;
            }
        };

        let mut next = Instant::now();
        while !self.shutdown.load(Ordering::Relaxed) {
            if self.counting.load(Ordering::Relaxed) {
                self.countdown_step();
                // 倒计时刚结束的那一轮从「现在」重新计时，不补点
                next = Instant::now();
                continue;
            }

            if !self.running.load(Ordering::Relaxed) {
                // 暂停时空转有代价，歇一下
                self.running_wait_gap();
                next = Instant::now();
                continue;
            }

            if self.failsafe_hit(&enigo) {
                self.running.store(false, Ordering::Relaxed);
                self.emit(Phase::Error, "已触发防失控保护");
                continue;
            }

            // 鼠标压在自己窗口上时不注入点击，否则会点中自家按钮把自己点停。
            // 等用户把鼠标移出去，立刻恢复。
            if self.cursor_in_window() {
                if !self.over_app.swap(true, Ordering::Relaxed) {
                    self.emit(Phase::Running, "鼠标在窗口上，移出后开始点击");
                }
                spin_sleep::sleep(Duration::from_millis(30));
                next = Instant::now();
                continue;
            }
            if self.over_app.swap(false, Ordering::Relaxed) {
                self.emit(Phase::Running, "连点中");
            }

            let button = MouseButton::from_code(self.button.load(Ordering::Relaxed));
            if let Err(err) = enigo.button(button.enigo(), Direction::Click) {
                self.running.store(false, Ordering::Relaxed);
                self.emit(Phase::Error, format!("点击失败：{err}"));
                continue;
            }
            self.clicks.fetch_add(1, Ordering::Relaxed);

            let interval = Duration::from_millis(
                self.interval_ms
                    .load(Ordering::Relaxed)
                    .max(MIN_INTERVAL_MS),
            );
            next += interval;
            let now = Instant::now();
            if next <= now {
                // 落后了（间隔被调小 / 系统卡顿），别追债
                next = now;
            }
            if !self.wait_until(next) {
                next = Instant::now();
            }
        }
    }

    /// 倒计时推进：每秒播报一次，到点后校验鼠标位置再正式开点
    fn countdown_step(&self) {
        let Some(deadline) = self.countdown_end() else {
            self.counting.store(false, Ordering::Relaxed);
            return;
        };

        let now = Instant::now();
        if now >= deadline {
            self.counting.store(false, Ordering::Relaxed);
            self.set_countdown_end(None);
            self.running.store(true, Ordering::Relaxed);
            // 鼠标若还压在窗口上不用拦——worker 会先跳过点击并提示
            let over = self.cursor_in_window();
            self.over_app.store(over, Ordering::Relaxed);
            let hint = if over {
                "鼠标在窗口上，移出后开始点击"
            } else {
                "连点中"
            };
            self.emit(Phase::Running, hint);
            return;
        }

        let remain = deadline.saturating_duration_since(now).as_millis() as u64;
        let secs = remain.div_ceil(1000).max(1);
        if self.countdown_secs.swap(secs, Ordering::Relaxed) != secs {
            self.emit(Phase::Countdown, format!("{secs} 秒后开始"));
        }
        spin_sleep::sleep(COUNTDOWN_TICK);
    }

    /// 鼠标是否落在主窗口矩形内（物理像素坐标系）
    fn cursor_in_window(&self) -> bool {
        let Some((x0, y0, x1, y1)) = *self.window_rect.lock().unwrap_or_else(|e| e.into_inner())
        else {
            // 还没拿到窗口几何就别拦人
            return false;
        };
        let Some((cx, cy)) = cursor_pos() else {
            return false;
        };
        cx >= x0 && cx < x1 && cy >= y0 && cy < y1
    }

    /// 暂停时的低耗等待，但要能被 start/shutdown 快速唤醒
    fn running_wait_gap(&self) {
        for _ in 0..4 {
            if self.running.load(Ordering::Relaxed) || self.shutdown.load(Ordering::Relaxed) {
                return;
            }
            spin_sleep::sleep(Duration::from_millis(5));
        }
    }

    /// 等到 deadline。返回 false 表示中途被暂停/退出打断。
    fn wait_until(&self, deadline: Instant) -> bool {
        loop {
            if self.shutdown.load(Ordering::Relaxed) || !self.running.load(Ordering::Relaxed) {
                return false;
            }
            let now = Instant::now();
            if now >= deadline {
                return true;
            }
            let remain = deadline - now;
            if remain <= SPIN_GUARD {
                std::hint::spin_loop();
            } else {
                // 分片睡：留 1ms 自旋余量，且每片不超过 WAIT_SLICE
                let slice = (remain - SPIN_GUARD).min(WAIT_SLICE);
                spin_sleep::sleep(slice);
            }
        }
    }

    fn failsafe_hit(&self, enigo: &Enigo) -> bool {
        match enigo.location() {
            Ok((x, y)) => x <= FAILSAFE_ZONE && y <= FAILSAFE_ZONE,
            // 取不到坐标就跳过检测，不要因此中断连点
            Err(_) => false,
        }
    }
}

/// 启动延迟上限（毫秒）
pub const MAX_DELAY_MS: u64 = 10_000;

fn cursor_pos() -> Option<(i32, i32)> {
    use windows_sys::Win32::Foundation::POINT;
    use windows_sys::Win32::UI::WindowsAndMessaging::GetCursorPos;

    let mut point = POINT { x: 0, y: 0 };
    if unsafe { GetCursorPos(&mut point) } != 0 {
        Some((point.x, point.y))
    } else {
        None
    }
}
