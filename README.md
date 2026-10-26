<div align="center">

# 🖱️ 鼠标连点器 Auto Clicker

**一款简单易用、开箱即用的 Windows 鼠标自动点击工具**

[![Tauri](https://img.shields.io/badge/Tauri-2.x-24C8DB?logo=tauri&logoColor=white)](https://tauri.app/)
[![Rust](https://img.shields.io/badge/Rust-1.77+-000000?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows11&logoColor=white)](#-快速开始)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Version-v2.0-orange)](#-更新日志)

*原生毛玻璃界面 · 全局快捷键控制 · 安装包约 5 MB*

</div>

---

## 📖 项目简介

**Auto Clicker** 基于 **Tauri 2 + Rust + TypeScript** 重写，用 WebView2 渲染界面、Rust 负责所有系统级操作，安装包比原 PySide6 版本小一个数量级，内存占用也更低。

## ✨ 功能特点

- 🧊 **原生毛玻璃界面** —— 由系统合成器（Acrylic）实时模糊，零抓屏开销，拖动窗口不再有模糊刷新延迟
- 🎯 **自定义点击间隔** —— 精确到 0.01 秒，输入实时校验，快捷预设一键填入
- 🖱️ **左键 / 右键切换** —— 自由选择需要自动点击的鼠标按键
- ⌨️ **全局快捷键** —— 无需切换窗口，随时开始 / 暂停 / 停止
- 📊 **实时状态显示** —— 待机、连点中、已暂停一目了然，附累计点击次数
- 🧵 **原生线程点击** —— 独立线程 + 原子开关，界面始终流畅
- 🛡️ **防失控保护** —— 鼠标急移到屏幕左上角可立即中止点击
- 📦 **一键打包** —— `tauri build` 产出 NSIS 安装包与单文件 EXE

## 🚀 快速开始

### 方式一：下载安装包（推荐）

1. 前往 [Releases](../../releases) 下载最新的 `AutoClicker_x64-setup.exe`（安装版）或 `AutoClicker.exe`（免安装）
2. 双击运行即可，**无需安装 Rust / Node / Python**

### 方式二：源码运行

**前置条件**：

- [Node.js](https://nodejs.org/) 20+
- [Rust](https://www.rust-lang.org/tools/install) 1.77+（MSVC 工具链）
- [Microsoft Edge WebView2](https://developer.microsoft.com/microsoft-edge/webview2/)（Win11 自带，Win10 一般也已预装）

```bash
git clone https://github.com/Cat-Drink/auto-clicker.git
cd auto-clicker

npm install
npm run tauri dev
```

## 📦 打包

```bash
npm run tauri build
```

产物：

| 文件 | 说明 |
|:---|:---|
| `src-tauri/target/release/AutoClicker.exe` | 免安装单文件 |
| `src-tauri/target/release/bundle/nsis/AutoClicker_2.0.0_x64-setup.exe` | NSIS 安装包 |

仓库内置 [GitHub Actions 工作流](.github/workflows/build-windows.yml)：推送 `v*` 标签后自动构建并上传到 Release。

## 🎮 使用方法

1. **设置点击间隔**：填入间隔时间（单位：秒），如 `0.1` 表示每 0.1 秒点击一次，最小 `0.01`
2. **选择点击按钮**：左键或右键
3. **开始 / 暂停连点**：按 `CTRL + ALT`，或点界面上的主按钮
4. **停止**：按 `ALT + Q`，或关闭窗口

### 快捷键一览

| 快捷键 | 功能 |
|:------:|:-----|
| <kbd>CTRL</kbd> + <kbd>ALT</kbd> | 开始 / 暂停连点 |
| <kbd>ALT</kbd> + <kbd>Q</kbd> | 停止连点 |

> 快捷键走的是低级键盘钩子（`WH_KEYBOARD_LL`）。若被其他软件占用或系统拦截，请尝试以管理员身份运行。

## 🧰 技术栈

| 层 | 用途 | 选型 |
|:---|:---|:---|
| 前端 | 界面、毛玻璃卡片、参数输入、状态展示 | TypeScript + Vite（无框架） |
| 桥接 | 命令调用 / 事件推送 | Tauri 2 IPC（`invoke` / `listen`） |
| 后端 | 点击引擎、全局热键、窗口特效 | Rust |
| 点击注入 | 模拟鼠标点击（SendInput） | `enigo` |
| 定时精度 | 毫秒级等待 | `spin_sleep` |
| 窗口特效 | Mica / Acrylic 毛玻璃、DWM 圆角 | `window-vibrancy` + `windows-sys` |

### 目录结构

```
AutoClicker/
├─ src/
│  ├─ main.ts            # UI 逻辑、参数校验、状态订阅
│  └─ style.css          # 毛玻璃卡片样式
├─ index.html
├─ src-tauri/
│  ├─ src/lib.rs         # Tauri 命令注册、应用入口
│  ├─ src/clicker.rs     # 点击引擎（线程 + enigo + spin_sleep）
│  ├─ src/hotkey.rs      # 全局热键（WH_KEYBOARD_LL）
│  ├─ src/effects.rs     # 窗口毛玻璃 / 圆角
│  └─ tauri.conf.json
└─ legacy/               # 旧版 Python + PySide6 实现（仅存档）
```

## ❓ 故障排除

<details>
<summary><b>快捷键不生效？</b></summary>

- 尝试以管理员身份运行（部分全屏游戏/提权窗口会屏蔽低级钩子）
- 检查是否有其他程序占用了 `CTRL + ALT`（部分输入法的「切换输入法」占用此组合）
- 界面状态栏会显示注册失败原因
</details>

<details>
<summary><b>窗口没有毛玻璃效果？</b></summary>

- Windows 11 且开启「透明效果」时才正常
- 默认使用 Acrylic（透明窗口下最稳定）；可在界面底部切换 Mica，Mica 更淡但拖动更跟手
- Windows 10 1809 以下系统不支持，会退化为半透明底色
</details>

<details>
<summary><b>点击间隔不准？</b></summary>

- 间隔下限为 0.01 秒，更小的值会被钳制
- 高负载下 Windows 调度抖动约 ±1–2 ms，属正常范围
</details>

<details>
<summary><b>杀毒软件报毒？</b></summary>

模拟鼠标输入的程序常被启发式引擎误判，可添加信任或自行编译。
</details>

## ⚠️ 注意事项

1. **合理使用**：请勿将本工具用于任何违反法律法规或平台规则的场景，使用风险自负
2. **性能影响**：过短的点击间隔会占用更多 CPU（自旋等待），建议按实际需求设置
3. **退出方式**：建议用窗口关闭按钮退出，确保键盘钩子被释放
4. **防失控**：连点过程中如需紧急中止，可将鼠标快速移至屏幕左上角

## 📜 许可证

本项目基于 [MIT License](LICENSE) 开源，可自由使用、修改和分发。

## 🗓️ 更新日志

<details open>
<summary><b>v2.0</b></summary>

- 🦀 全量重写：Tauri 2 + Rust + TypeScript，替换 Python + PySide6
- 🧊 毛玻璃改由系统合成器提供（Acrylic / Mica 可切换），删除抓屏 + 高斯模糊的自绘方案，拖动不再残影
- ⌨️ 全局热键改用低级键盘钩子，保留 `CTRL + ALT` 纯修饰键组合
- ⚡ 点击间隔改用「截止时间 + 分片等待 + 自旋」，10ms 级间隔精度稳定
- 📊 状态栏新增累计点击次数
- 📦 安装包体积从 ~40 MB 降到 ~5 MB
</details>

<details>
<summary><b>v1.3（Python 版）</b></summary>

- 🪟 界面迁移至 PySide6（Qt6），彻底解决 Tkinter 透明方案的文字重影与模糊问题
- 🧊 真实液态毛玻璃：抓取窗口背后的桌面内容实时高斯模糊，浅白磨砂卡片 + 深色文字，拖动后自动刷新
- 🖼️ 自绘无边框窗口：自绘标题栏支持拖动、最小化、关闭，窗口圆角
</details>

<details>
<summary><b>v1.2 / v1.1 / v1.0</b></summary>

- v1.2：亚克力背景、分段式左/右键选择器、间隔预设、状态指示灯
- v1.1：运行状态显示、修正点击间隔偏慢、防失控保护、打包与 CI
- v1.0：初始版本
</details>

---

<div align="center">

如果这个项目对你有帮助，欢迎点一个 ⭐ Star 支持一下！

</div>
