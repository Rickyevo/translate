<div align="center">

[English](README.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · **한국어**

<img src="assets/icons/app/app-256.png" alt="Translate 앱 아이콘" width="96" height="96">

# Translate

**WeChat 입력기와 Microsoft 병음의 후보를 실시간으로 번역합니다.**<br>
병음을 입력하면서 후보의 뜻을 확인하고 번역을 바로 입력하세요.

[![최신 버전](https://img.shields.io/github/v/release/Rickyevo/translate?label=release&color=0f7b6c)](https://github.com/Rickyevo/translate/releases/latest)
[![다운로드](https://img.shields.io/github/downloads/Rickyevo/translate/total?color=0f7b6c)](https://github.com/Rickyevo/translate/releases)
[![Windows](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20x64-0078d4)](#실행-환경)
[![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[**다운로드**](https://github.com/Rickyevo/translate/releases/latest) · [빠른 시작](#빠른-시작) · [기능](#기능) · [개인정보](#개인정보) · [자주 묻는 질문](#자주-묻는-질문)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/hero-en-dark.png">
  <img alt="후보 번역과 첫 번째 후보의 전체 번역 미리 보기" src="screenshots/readme/hero-en-light.png">
</picture>

</div>

Translate는 Windows의 **WeChat 입력기(微信输入法, WeType)** 를 위한 백그라운드 도구입니다. 병음을 입력하면 후보창 아래에 번역이 표시됩니다. **Alt+1…9** 로 채팅, 이메일, 문서 등 현재 입력란에 번역을 바로 입력할 수 있습니다.

## 기능

| 기능 | 설명 |
|---|---|
| 일반 단어 즉시 표시 | 내장 사전으로 중국어 단어를 영어로 오프라인 번역합니다. |
| 구문과 문장 번역 | 선택한 서비스에 후보를 묶어 요청하며, 반복된 번역은 캐시에서 가져옵니다. 속도는 서비스에 따라 다릅니다. |
| 입력 또는 복사 | Alt+1…9로 입력, Alt+Shift+1…9로 복사합니다. 원래 입력란의 포커스를 유지합니다. |
| 긴 번역 미리 보기 | 첫 후보가 행에 들어가지 않으면 전체 내용을 표시합니다. Alt와 백틱 키로도 전환합니다. |
| 7개 대상 언어 | 영어, 일본어, 한국어, 프랑스어, 독일어, 스페인어, 러시아어. |
| 서비스 선택 | OpenAI, Claude, Gemini, Grok, DeepSeek, OpenCode Go 및 호환 API. |
| 조용한 실행 | 상시 메인 창이나 트레이 아이콘 없이 입력 중에만 패널이 표시됩니다. 자동 시작과 감지 가능한 비밀번호 입력란 제외를 지원합니다. |
| 로컬 보호 | 키는 Windows 자격 증명 관리자에 저장하며 로그에 후보나 번역을 남기지 않습니다. |
| 다국어 UI | 영어, 간체 중국어, 일본어, 한국어 및 시스템에 맞춘 밝은/어두운 테마. |

## 빠른 시작

1. [Releases](https://github.com/Rickyevo/translate/releases/latest)에서 `Translate-<version>-win-x64.zip`을 다운로드합니다.
2. `%LOCALAPPDATA%\Programs\Translate` 등 고정된 위치에 압축을 풉니다.
3. `Translate.exe`를 실행합니다. Python, Node.js, 개발 도구나 관리자 권한이 필요하지 않습니다.

시작할 때 창이 나타나지 않습니다. WeChat 입력기로 병음을 입력하면 패널이 표시됩니다. Windows 시작 시 실행은 기본으로 켜져 있으며 설정의 General에서 끌 수 있습니다.

> [!TIP]
> 서비스를 설정하지 않아도 내장 사전으로 일부 중국어 단어를 영어로 번역할 수 있습니다. 구문, 문장, 다른 대상 언어에는 번역 서비스가 필요합니다.

**번역 서비스 설정:** EXE를 다시 실행하거나 **Ctrl+Alt+O** 로 설정을 엽니다.

1. Translation → Service에서 공급자를 선택하고 주소와 모델을 확인합니다. Load models로 사용 가능한 모델을 가져옵니다.
2. API 키를 입력하고 Test connection을 누른 뒤 Save로 저장합니다. 키는 Windows 자격 증명 관리자에 저장됩니다.
3. Overview → Translate into에서 대상 언어를 선택합니다.

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/settings-overview-dark.png">
  <img alt="설정 개요 페이지" src="screenshots/readme/settings-overview-light.png" width="680">
</picture>
</div>

<details>
<summary><b>지원 서비스</b></summary>

| 서비스 | API 형식 | 인증 |
|---|---|---|
| OpenAI | Chat Completions | API 키 |
| Claude (Anthropic) | Messages | API 키 |
| Gemini (Google) | Gemini API | API 키 |
| Grok (xAI) | OpenAI 호환 | API 키 |
| DeepSeek | OpenAI 호환 | API 키 |
| OpenCode Go | 모델별 형식 | 플랜 API 키 |
| 사용자 지정 | OpenAI, Claude, Gemini 호환 | Bearer 토큰, x-api-key, 사용자 지정 헤더, 쿼리 매개변수 또는 인증 없음 |

주소, 모델, 시간 제한을 변경할 수 있습니다. 해당 서비스가 이 용도를 허용하는지 확인하세요. OpenCode Go와 같은 일부 플랜은 코딩 도구용입니다.

</details>

## 단축키

| 키 | 동작 |
|---|---|
| <kbd>Alt</kbd>+<kbd>1</kbd> … <kbd>9</kbd> | 해당 번역 입력 |
| <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>1</kbd> … <kbd>9</kbd> | 번역 복사 |
| <kbd>Alt</kbd>+<kbd>&#96;</kbd> | 전체 번역 표시/숨기기 |
| <kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | 다른 후보 미리 보기 |
| <kbd>Alt</kbd>+<kbd>PgUp</kbd> / <kbd>PgDn</kbd> | 전체 번역 스크롤 |
| <kbd>Alt</kbd>+<kbd>0</kbd> | 패널 표시/숨기기 |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>P</kbd> | 번역 일시 중지/다시 시작 |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>O</kbd> | 설정 열기 |

후보를 오른쪽 클릭하면 입력, 복사, 재시도를 할 수 있습니다. 마우스 사용 시 **Settings → Appearance → Keep the panel clickable**을 켜세요. WeType의 투명 창이 후보 아래의 클릭을 가로채므로 패널을 그 영역 밖으로 옮깁니다.

## 개인정보

- **로컬 읽기:** 후보와 병음, 후보창 위치, 앱 제외 및 감지 가능한 비밀번호 입력란 확인에 필요한 활성 앱 정보.
- **전송:** 캐시되지 않은 후보와 대상 언어는 선택한 서비스에만 전송합니다. 사전 결과도 서비스로 보완할 수 있습니다. Local only 또는 서비스 미설정 상태에서는 번역 요청을 보내지 않습니다.
- **저장:** 설정 파일에는 키가 없습니다. 키는 Windows 자격 증명 관리자에, 조건을 충족하는 짧은 사전 단어는 암호화 캐시에 저장합니다. 긴 문장은 메모리에만 보관합니다. 로그에 후보나 번역을 남기지 않습니다.
- 계정 등록, 원격 분석, 업데이트 확인이 없습니다. 비밀번호 감지와 짧은 단어 분류에는 한계가 있습니다.

자세한 내용은 [개인정보 문서(영어)](docs/privacy.md)를 참조하세요.

## 실행 환경

| 항목 | 요구 사항 |
|---|---|
| Windows | 10 또는 11, x64 |
| 입력기 | [WeChat 입력기](https://z.weixin.qq.com/)(검증 버전 **3.0.0.34**) 또는 **Microsoft 병음**(Windows 11, 빌드 26200에서 검증) |
| 입력기 선택 | 설정 → 개요 → 입력기: WeChat 입력기와 Microsoft 병음의 준비 상태와 켜기/끄기. 둘 다 켜면 지금 입력에 쓰는 입력기를 따름 |
| 바로 가기 변경 | 설정 → 일반 → 바로 가기: 일시 중지, 설정 열기, 패널 표시/숨기기(다른 앱과 겹치는지 확인) |
| 번역 서비스 | 선택 사항. 구문, 문장, 영어 외 대상 언어에는 본인의 API 키 필요 |
| 공간 | 다운로드 약 61 MB, 압축 해제 후 약 156 MB |
| WebView2 | Windows 11과 최신 Windows 10에 기본 포함된 Microsoft Edge WebView2 런타임(없으면 Translate가 안내합니다) |

## 알려진 제한

- WeType 내부 메시지를 사용하므로 업데이트 후 작동하지 않을 수 있습니다. [Issues](https://github.com/Rickyevo/translate/issues)에 버전을 함께 알려 주세요.
- 네이티브 관찰 모듈이 입력기 프로세스에 연결하므로 일부 보안 프로그램에서 경고할 수 있습니다.
- 코드 서명이 없어 첫 실행 시 SmartScreen 경고가 나타날 수 있습니다.
- 패널 위치는 WeType 후보 바가 실제로 그려진 위치를 따릅니다(레이아웃, 배율, 화면 가장자리와 무관). 배율이 서로 다른 다중 모니터와 Windows ARM은 미검증입니다.
- 포터블 버전이며 설치 프로그램이나 시작 메뉴 항목이 없습니다. 폴더 이동 후 EXE를 한 번 실행하면 자동 시작 경로가 갱신됩니다.
- 내장 사전은 중국어에서 영어로의 번역만 지원합니다.

## 자주 묻는 질문

<details>
<summary><b>Windows가 PC를 보호했다는 메시지가 나옵니다.</b></summary>

코드 서명이 없어 경고가 나타날 수 있습니다. 다운로드 출처를 확인한 뒤 추가 정보 → 실행을 선택할 수 있습니다. 배포 페이지의 `SHA256SUMS.txt`와 비교할 수 있습니다.

```powershell
Get-FileHash .\Translate-0.2.4-win-x64.zip -Algorithm SHA256
```

</details>

<details>
<summary><b>실행해도 아무것도 보이지 않습니다.</b></summary>

백그라운드 도구이므로 정상입니다. WeType로 병음을 입력하면 패널이 나타납니다. EXE를 다시 실행하거나 Ctrl+Alt+O로 설정을 엽니다.

</details>

<details>
<summary><b>API 키가 반드시 필요한가요?</b></summary>

아닙니다. 내장 CC-CEDICT로 일부 중국어 단어를 영어로 번역할 수 있습니다. 문장과 다른 언어에는 서비스가 필요합니다.

</details>

<details>
<summary><b>일시 중지, 종료, 삭제는 어떻게 하나요?</b></summary>

Ctrl+Alt+P로 일시 중지/다시 시작합니다. 종료는 Settings → About → Quit Translate입니다.

삭제 전 Start with Windows를 끄고 저장한 다음 종료하세요. 프로그램 폴더와 `%APPDATA%\Translate`를 삭제하고 자격 증명 관리자에서 `Translate:service:`로 시작하는 항목을 삭제합니다.

</details>

## 작동 방식

동봉된 Python 엔진이 네이티브 모듈과 크기가 제한된 공유 메모리를 통해 `wetype_server.exe`에서 후보창으로 보내는 메시지를 관찰하고 후보와 창 위치를 가져옵니다. 캐시, 사전, 선택한 서비스에서 번역을 가져와 Tauri + WebView2 패널에 표시합니다. 입력 시 병음 조합을 취소하고 `SendInput`으로 Unicode 번역을 입력합니다.

[개발 가이드](docs/development.md) · [디자인 시스템](DESIGN.md) · [통신 규약](docs/protocol.md) · [배포 빌드](docs/release.md) · [변경 기록](CHANGELOG.md)

## 소스에서 빌드

Windows 10/11 x64, Node 22+, Python 3.12, Rust(MSVC, Visual Studio Build Tools)가 필요합니다.

```powershell
python -m pip install --target backend/vendor -r backend/requirements.txt
cd app
npm install
python -X utf8 scripts/package.py
```

전체 의존성, 테스트, 포터블 빌드는 [개발 가이드](docs/development.md)를 참조하세요.

## 피드백

[Issues](https://github.com/Rickyevo/translate/issues)에 Windows와 WeType 버전을 함께 적어 주세요. 진단 로그는 설정의 Privacy에서 열 수 있으며 후보나 번역을 포함하지 않습니다.

## 라이선스

[MIT](LICENSE) © 2026 Rickywu05

사전은 [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cedict)(CC BY-SA 4.0)에서 파생되었습니다. Python, MinHook, Frida(호환 모드), Tauri 등은 각각의 라이선스를 따릅니다. [타사 고지](app/build/THIRD_PARTY_NOTICES.txt)를 참조하세요.

<div align="center"><sub>Translate는 독립 프로젝트이며 Tencent 또는 WeChat의 제품, 제휴 제품 또는 공식 승인 제품이 아닙니다.</sub></div>
