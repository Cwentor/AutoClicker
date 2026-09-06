<div align="center">

# 🖱️ 鼠标连点器 Auto Clicker

**一款简单易用、开箱即用的 Windows 鼠标自动点击工具**

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows11&logoColor=white)](#-快速开始)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Version-v1.3-orange)](#-更新日志)

*图形化界面 · 快捷键控制 · 支持打包为独立 EXE*

</div>

---

## 📖 项目简介

**auto_clicker** 是一款基于 Python + PySide6（Qt6）开发的鼠标连点器，能够帮助用户自动执行鼠标点击操作，适用于游戏挂机、数据录入、重复测试等各种需要重复点击的场景。

## ✨ 功能特点

- 🎨 **液态毛玻璃界面** —— 实时高斯模糊的磨砂背景 + 白玻璃卡片 + 分段式控件
- 🎯 **自定义点击间隔** —— 精确到 0.01 秒，输入实时校验，快捷预设一键填入
- 🖱️ **左键 / 右键切换** —— 自由选择需要自动点击的鼠标按键
- ⌨️ **全局快捷键** —— 无需切换窗口，随时开始 / 暂停 / 停止
- 📊 **实时状态显示** —— 待机、连点中、已暂停一目了然
- 🧵 **多线程设计** —— 点击逻辑后台运行，界面始终流畅不卡顿
- 🛡️ **防失控保护** —— 鼠标急移到屏幕左上角可立即中止点击
- 📦 **一键打包 EXE** —— 附带构建脚本，无需安装 Python 即可分发运行

## 🚀 快速开始

### 方式一：下载 EXE（推荐）

1. 前往 [Releases](../../releases) 页面下载最新的 `AutoClicker.exe`
2. 双击运行即可，**无需安装 Python 和任何依赖**

> 💡 也可以自行打包，参见 [打包为 EXE](#-打包为-exe) 一节。

### 方式二：源码运行

**前置条件**：安装 [Python 3.9+](https://www.python.org/downloads/)（Windows 安装时请勾选 *Add to PATH*）

```bash
# 1. 克隆项目
git clone https://github.com/Cat-Drink/auto-clicker.git
cd auto-clicker

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动程序
python auto_clicker.py
```

## 📦 打包为 EXE

项目提供了一键打包脚本，自动完成虚拟环境创建、依赖安装和 PyInstaller 打包：

```bash
# 双击运行，或在命令行执行
build_windows.bat
```

打包完成后，可执行文件位于 **`dist\AutoClicker.exe`**（单文件、无控制台窗口）。

> 💡 产物使用英文文件名，以避免中文文件名在 GitHub Release 上传时出现编码问题。

也可以手动执行 PyInstaller：

```bash
pip install -r requirements-dev.txt
pyinstaller auto_clicker.spec --noconfirm
```

此外，仓库内置了 [GitHub Actions 工作流](.github/workflows/build-windows.yml)，推送 `v*` 标签后会自动构建并在 Release 中附带 EXE 文件。

## 🎮 使用方法

1. **设置点击间隔**：在“点击间隔”输入框中填入间隔时间（单位：秒），如 `0.1` 表示每 0.1 秒点击一次
2. **选择点击按钮**：在“点击按钮”区域选择左键或右键
3. **开始 / 暂停连点**：按下快捷键 `CTRL + ALT`
4. **停止程序**：按下快捷键 `ALT + Q`，或直接关闭窗口

### 快捷键一览

| 快捷键 | 功能 |
|:------:|:-----|
| <kbd>CTRL</kbd> + <kbd>ALT</kbd> | 开始 / 暂停连点 |
| <kbd>ALT</kbd> + <kbd>Q</kbd> | 停止程序 |

## 🧰 技术栈 / 依赖

| 依赖 | 说明 |
|:----|:-----|
| [pyautogui](https://pypi.org/project/PyAutoGUI/) | 模拟鼠标点击操作 |
| [keyboard](https://pypi.org/project/keyboard/) | 全局键盘快捷键监听 |
| [PySide6](https://pypi.org/project/PySide6/) | 图形化界面（Qt6）与毛玻璃效果 |
| PyInstaller | 打包为独立 EXE（开发依赖） |

## ❓ 故障排除

<details>
<summary><b>快捷键不生效？</b></summary>

- 尝试以管理员身份运行程序
- 检查是否有其他程序占用了相同的快捷键
- `keyboard` 库在部分系统上需要管理员权限才能监听全局按键
</details>

<details>
<summary><b>点击操作不执行？</b></summary>

- 确认已按下 `CTRL + ALT` 开始连点（界面状态应显示“连点中”）
- 检查点击间隔设置是否合理（最小 0.01 秒）
- 确保鼠标指针位于需要点击的位置
</details>

<details>
<summary><b>杀毒软件报毒？</b></summary>

PyInstaller 打包的单文件 EXE 偶尔会被杀毒软件误报，可添加信任或将源码自行打包。
</details>

## ⚠️ 注意事项

1. **合理使用**：请勿将本工具用于任何违反法律法规或平台规则的场景，使用风险自负
2. **性能影响**：过短的点击间隔可能占用较多系统资源，建议按实际需求设置
3. **退出方式**：建议使用 `ALT + Q` 或关闭窗口退出，以确保热键钩子被正确释放
4. **防失控**：连点过程中如需紧急中止，可将鼠标快速移至屏幕左上角

## 📜 许可证

本项目基于 [MIT License](LICENSE) 开源，可自由使用、修改和分发。

## 🗓️ 更新日志

<details open>
<summary><b>v1.3</b></summary>

- 🪟 界面迁移至 PySide6（Qt6），彻底解决 Tkinter 透明方案的文字重影与模糊问题
- 🧊 真实液态毛玻璃：抓取窗口背后的桌面内容实时高斯模糊，浅白磨砂卡片 + 深色文字，拖动后自动刷新
- 🖼️ 自绘无边框窗口：自绘标题栏支持拖动、最小化、关闭，窗口圆角
</details>

<details>
<summary><b>v1.2</b></summary>

- 🎨 界面全面重构为液态毛玻璃风格：Windows 11 DWM 亚克力背景、窗口圆角、深色玻璃卡片
- 🎛️ 关键控件重新设计：分段式左/右键选择器、间隔快捷预设、大号主操作按钮
- 💡 新增运行状态指示灯（连点时呼吸闪烁），支持鼠标直接点击开始/暂停
</details>

<details>
<summary><b>v1.1</b></summary>

- ✨ 新增实时运行状态显示栏（待机 / 连点中 / 已暂停）
- 🐛 修正实际点击间隔比设置值慢 0.1 秒的问题（关闭 pyautogui 内置暂停）
- 🛡️ 点击间隔输入实时校验，非法输入自动回落，杜绝运行时报错
- 🛡️ 接入 pyautogui 防失控保护（FAILSAFE）
- 🔧 新增 Windows 打包能力：PyInstaller spec、一键构建脚本、CI 工作流
- 📖 重写并美化 README 文档
</details>

<details>
<summary><b>v1.0</b></summary>

- 🎉 初始版本发布：基本连点功能、图形化界面、快捷键控制
</details>

---

<div align="center">

如果这个项目对你有帮助，欢迎点一个 ⭐ Star 支持一下！

</div>
