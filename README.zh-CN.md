<div align="center">

[English](README.md) · **简体中文** · [日本語](README.ja.md) · [한국어](README.ko.md)

<img src="assets/icons/app/app-256.png" alt="Translate 应用图标" width="96" height="96">

# Translate

**微信输入法与微软拼音候选词实时翻译助手。**<br>
输入拼音时查看候选译文，直接把所选译文输入当前应用。

[![最新版本](https://img.shields.io/github/v/release/Rickywu05/translate?label=release&color=0f7b6c)](https://github.com/Rickywu05/translate/releases/latest)
[![下载量](https://img.shields.io/github/downloads/Rickywu05/translate/total?color=0f7b6c)](https://github.com/Rickywu05/translate/releases)
[![平台](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20x64-0078d4)](#运行要求)
[![许可证：MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[**下载**](https://github.com/Rickywu05/translate/releases/latest) · [快速开始](#快速开始) · [功能](#功能) · [隐私](#隐私) · [常见问题](#常见问题)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/hero-en-dark.png">
  <img alt="微信输入法候选的英文译文和第一候选的完整预览" src="screenshots/readme/hero-en-light.png">
</picture>

</div>

Translate 是一个安静运行在 Windows 后台的微信输入法（WeType）辅助工具。输入拼音时，候选窗下方显示对应译文。按 **Alt+1…9**，即可把译文输入聊天、邮件或文档，无需离开当前输入框。

## 功能

| 功能 | 说明 |
|---|---|
| 常见词即时显示 | 内置词典支持离线中文到英文查询。 |
| 短语与句子翻译 | 使用所选服务批量翻译候选，重复内容从缓存读取；速度取决于服务。 |
| 插入或复制 | Alt+1…9 插入译文，Alt+Shift+1…9 复制译文，保持原输入框焦点。 |
| 长译文预览 | 第一候选显示不全时展开预览，也可按 Alt 加反引号手动查看。 |
| 七种目标语言 | 英语、日语、韩语、法语、德语、西班牙语、俄语。 |
| 自选翻译服务 | OpenAI、Claude、Gemini、Grok、DeepSeek、OpenCode Go，以及兼容接口。 |
| 低干扰运行 | 无常驻主窗口和托盘图标，输入时显示浮窗，支持开机自启和可检测密码框排除。 |
| 本地保护 | 密钥存于 Windows 凭据管理器，日志不记录候选原文或译文。 |
| 多语言界面 | 英语、简体中文、日语、韩语，支持跟随系统的浅深主题。 |

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/hero-ja-dark.png">
  <img alt="日语目标语言示例" src="screenshots/readme/hero-ja-light.png">
</picture>
</div>

## 快速开始

1. 从 [Releases](https://github.com/Rickywu05/translate/releases/latest) 下载 `Translate-<version>-win-x64.zip`。
2. 解压到固定位置，例如 `%LOCALAPPDATA%\Programs\Translate`。
3. 运行 `Translate.exe`，无需安装 Python、Node.js 或其他开发工具，也无需管理员权限。

启动后没有主窗口。使用微信输入法输入拼音，浮窗会自动出现。开机自启默认开启，可在设置 → 通用中关闭。

> [!TIP]
> 未配置服务时，内置词典仍可离线翻译部分中文词语为英文。短语、句子和其他目标语言需要翻译服务。

**配置翻译服务：**再次运行 `Translate.exe`，或按 **Ctrl+Alt+O** 打开设置。

1. 在翻译 → 服务中选择服务商，检查接口地址和模型；“加载模型”可获取可用模型列表。
2. 输入密钥，点击“测试连接”，然后“保存”。密钥存入 Windows 凭据管理器。
3. 在概览 → 翻译成中选择目标语言。

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/settings-overview-dark.png">
  <img alt="设置概览页面" src="screenshots/readme/settings-overview-light.png" width="680">
</picture>
</div>

<details>
<summary><b>支持的翻译服务</b></summary>

| 服务 | API 格式 | 凭据 |
|---|---|---|
| OpenAI | Chat Completions | API Key |
| Claude（Anthropic） | Messages | API Key |
| Gemini（Google） | Gemini API | API Key |
| Grok（xAI） | OpenAI 兼容 | API Key |
| DeepSeek | OpenAI 兼容 | API Key |
| OpenCode Go | 按模型选择接口格式 | 套餐 API Key |
| 自定义 | OpenAI、Claude 或 Gemini 兼容 | Bearer Token、x-api-key、自定义请求头、查询参数或无认证 |

各服务可配置接口、模型和超时。请确认所选服务允许这一用途；某些套餐（如 OpenCode Go）面向编程工具。

</details>

## 快捷键

| 按键 | 操作 |
|---|---|
| <kbd>Alt</kbd>+<kbd>1</kbd> … <kbd>9</kbd> | 插入对应译文 |
| <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>1</kbd> … <kbd>9</kbd> | 复制对应译文 |
| <kbd>Alt</kbd>+<kbd>&#96;</kbd> | 显示或隐藏完整译文预览 |
| <kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | 预览其他候选 |
| <kbd>Alt</kbd>+<kbd>PgUp</kbd> / <kbd>PgDn</kbd> | 滚动完整译文 |
| <kbd>Alt</kbd>+<kbd>0</kbd> | 显示或隐藏浮窗 |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>P</kbd> | 暂停或恢复翻译 |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>O</kbd> | 打开设置 |

右键候选可插入、复制或重试。鼠标操作请开启**设置 → 外观 → 保持面板可点击**：微信输入法的透明窗口会拦截紧贴候选条区域的点击，该设置将面板移到透明窗口之外。

## 隐私

- **本地读取：**微信输入法候选和拼音、候选窗位置，以及用于排除应用和可检测密码框的前台应用信息。
- **外发：**未缓存候选及目标语言仅发送给你选择的服务；词典结果也可能交给该服务精修。本地模式或未配置服务时不发送翻译请求。
- **存储：**设置不含密钥；密钥存入 Windows 凭据管理器；符合规则的短词加密缓存到磁盘；长句只留在内存。日志仅含诊断信息。
- 没有项目账户、遥测或自动更新检查。密码检测和短词筛选都有覆盖范围限制。

完整说明见 [隐私文档（英文）](docs/privacy.md)。

## 运行要求

| 项目 | 要求 |
|---|---|
| Windows | 10 或 11，x64 |
| 输入法 | [微信输入法](https://z.weixin.qq.com/)（已测试 **3.0.0.34**）和/或 **微软拼音**（Windows 11，已在 26200 版本测试） |
| 选择输入法 | 设置 → 通用 → 输入法：*自动*（跟随你正在使用的输入法）、*微信输入法* 或 *微软拼音* |
| 翻译服务 | 可选；短语、句子和非英文目标需要自己的 API Key |
| 空间 | 下载约 61 MB，解压约 156 MB |
| WebView2 | Windows 11 及较新的 Windows 10 已内置 Microsoft Edge WebView2 运行时（缺失时 Translate 会提示） |

## 已知限制

- 使用微信输入法内部消息，版本更新可能导致失效；请在 [Issues](https://github.com/Rickywu05/translate/issues) 提供版本信息。
- Frida 会附加到输入法服务端进程，部分安全软件可能告警。
- 尚未代码签名，首次启动可能出现 SmartScreen 提示。
- 面板位置跟随微信输入法候选栏的实际绘制位置（不受布局、缩放比例和屏幕边缘影响）；缩放比例不同的多屏组合和 Windows ARM 尚未测试。
- 当前为便携版，没有安装器或开始菜单入口。移动目录后重新运行一次 EXE，让自启路径更新。
- 本地词典只覆盖中文到英文。

## 常见问题

<details>
<summary><b>Windows 提示保护了我的电脑？</b></summary>

程序尚未签名，SmartScreen 可能不认识它。确认下载来源后，可选择“更多信息 → 仍要运行”。发布页附有 `SHA256SUMS.txt`，可核对文件：

```powershell
Get-FileHash .\Translate-0.2.1-win-x64.zip -Algorithm SHA256
```

</details>

<details>
<summary><b>启动后什么都没有？</b></summary>

这是后台工具，没有常驻主窗口和托盘。使用微信输入法输入拼音即可显示浮窗；再次运行 EXE 或按 Ctrl+Alt+O 打开设置。

</details>

<details>
<summary><b>必须有 API Key 吗？</b></summary>

不是。没有 Key 时，可用内置 CC-CEDICT 查询部分中文词语的英文；完整翻译和其他语言需要服务。

</details>

<details>
<summary><b>怎么暂停、退出和卸载？</b></summary>

Ctrl+Alt+P 暂停或恢复。退出在设置 → 关于 → 退出 Translate。

卸载前关闭开机自启并保存，然后退出，删除程序目录和 `%APPDATA%\Translate`，并在 Windows 凭据管理器中删除以 `Translate:service:` 开头的条目。

</details>

## 工作原理

内置 Python 引擎通过 Frida 观察 `wetype_server.exe` 发给候选窗的消息，提取候选并跟踪窗口位置。译文来自缓存、本地词典和所选服务，界面由 Tauri + WebView2 展示。插入时取消拼音组合，通过 `SendInput` 输入 Unicode 译文。

[开发说明](docs/development.md) · [设计系统](DESIGN.md) · [通信协议](docs/protocol.md) · [发布构建](docs/release.md) · [更新记录](CHANGELOG.md)

## 从源码构建

需要 Windows 10/11 x64、Node 22+、Python 3.12 和 Rust（MSVC，含 Visual Studio Build Tools）：

```powershell
python -m pip install --target backend/vendor frida==17.23.3
cd app
npm install
python -X utf8 scripts/package.py
```

完整依赖、测试和便携版打包步骤见 [开发说明](docs/development.md)。

## 反馈

请在 [Issues](https://github.com/Rickywu05/translate/issues) 描述问题并附 Windows 和微信输入法版本。诊断日志可从设置 → 隐私打开，日志不含候选原文或译文。

## 许可证

[MIT](LICENSE) © 2026 Rickywu05

本地词典来自 [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cedict)，使用 CC BY-SA 4.0。Python、Frida、Tauri 等组件采用各自许可证，见 [第三方声明](app/build/THIRD_PARTY_NOTICES.txt)。

<div align="center"><sub>Translate 是独立项目，与腾讯或微信没有隶属、合作或官方背书关系。</sub></div>
