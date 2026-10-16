<div align="center">

[English](README.md) · [简体中文](README.zh-CN.md) · **日本語** · [한국어](README.ko.md)

<img src="assets/icons/app/app-256.png" alt="Translate アプリアイコン" width="96" height="96">

# Translate

**WeChat Input Method の変換候補をリアルタイムに翻訳。**<br>
ピンイン入力中に候補の意味を確認し、翻訳をそのまま入力できます。

[![最新リリース](https://img.shields.io/github/v/release/Rickywu05/wetype-translate?label=release&color=0f7b6c)](https://github.com/Rickywu05/wetype-translate/releases/latest)
[![ダウンロード](https://img.shields.io/github/downloads/Rickywu05/wetype-translate/total?color=0f7b6c)](https://github.com/Rickywu05/wetype-translate/releases)
[![Windows](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20x64-0078d4)](#動作環境)
[![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

[**ダウンロード**](https://github.com/Rickywu05/wetype-translate/releases/latest) · [クイックスタート](#クイックスタート) · [機能](#機能) · [プライバシー](#プライバシー) · [よくある質問](#よくある質問)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/hero-ja-dark.png">
  <img alt="日本語の候補翻訳と全文プレビュー" src="screenshots/readme/hero-ja-light.png">
</picture>

</div>

Translate は Windows の **WeChat Input Method（微信输入法・WeType）** を補助する常駐ツールです。ピンイン入力中、候補ウィンドウの下に翻訳を表示します。**Alt+1…9** で、チャット、メール、文書など、現在の入力欄に翻訳を挿入できます。

## 機能

| 機能 | 内容 |
|---|---|
| よく使う単語を即座に表示 | 内蔵辞書による中国語から英語へのオフライン検索。 |
| フレーズと文章の翻訳 | 選択したサービスへ候補をまとめて送信し、繰り返しはキャッシュから取得。速度はサービスに依存します。 |
| 挿入とコピー | Alt+1…9 で挿入、Alt+Shift+1…9 でコピー。入力欄のフォーカスを維持します。 |
| 長文プレビュー | 最初の候補が収まらない場合に全文を表示。Alt とバッククォートでも切り替え可能。 |
| 7つの翻訳先 | 英語、日本語、韓国語、フランス語、ドイツ語、スペイン語、ロシア語。 |
| サービスを選択 | OpenAI、Claude、Gemini、Grok、DeepSeek、OpenCode Go、互換 API。 |
| 控えめな動作 | 常設のメインウィンドウやトレイアイコンなし。入力中に表示し、Windows 起動時の実行に対応。検出可能なパスワード欄を除外します。 |
| ローカルで保護 | キーは Windows 資格情報マネージャーに保存。ログに候補や翻訳を記録しません。 |
| 多言語 UI | 英語、簡体字中国語、日本語、韓国語。システムに合わせたライト／ダークテーマ。 |

## クイックスタート

1. [Releases](https://github.com/Rickywu05/wetype-translate/releases/latest) から `Translate-<version>-win-x64.zip` をダウンロードします。
2. `%LOCALAPPDATA%\Programs\Translate` など、固定の場所に展開します。
3. `Translate.exe` を実行します。Python、Node.js、開発ツール、管理者権限は不要です。

起動時にメインウィンドウは表示されません。WeChat Input Method でピンインを入力するとパネルが現れます。自動起動は既定で有効で、設定の General から変更できます。

> [!TIP]
> サービス未設定でも、一部の中国語単語を英語へオフライン翻訳できます。フレーズ、文章、その他の言語には翻訳サービスが必要です。

**サービスの設定：** EXE をもう一度実行するか **Ctrl+Alt+O** で設定を開きます。

1. Translation → Service でプロバイダーを選択し、エンドポイントとモデルを確認します。Load models で利用可能なモデルを取得できます。
2. API キーを入力し、Test connection、Save の順に押します。キーは Windows 資格情報マネージャーへ保存されます。
3. Overview → Translate into で翻訳先を選びます。

<div align="center">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="screenshots/readme/settings-overview-dark.png">
  <img alt="設定の概要画面" src="screenshots/readme/settings-overview-light.png" width="680">
</picture>
</div>

<details>
<summary><b>対応サービス</b></summary>

| サービス | API 形式 | 認証 |
|---|---|---|
| OpenAI | Chat Completions | API キー |
| Claude（Anthropic） | Messages | API キー |
| Gemini（Google） | Gemini API | API キー |
| Grok（xAI） | OpenAI 互換 | API キー |
| DeepSeek | OpenAI 互換 | API キー |
| OpenCode Go | モデルに応じた形式 | プラン API キー |
| カスタム | OpenAI・Claude・Gemini 互換 | Bearer token、x-api-key、カスタムヘッダー、クエリーパラメーター、認証なし |

エンドポイント、モデル、タイムアウトを変更できます。利用するサービスがこの用途を許可しているか確認してください。OpenCode Go など、一部のプランはコーディングツール向けです。

</details>

## ショートカット

| キー | 操作 |
|---|---|
| <kbd>Alt</kbd>+<kbd>1</kbd> … <kbd>9</kbd> | 対応する翻訳を挿入 |
| <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>1</kbd> … <kbd>9</kbd> | 翻訳をコピー |
| <kbd>Alt</kbd>+<kbd>&#96;</kbd> | 全文プレビューの表示／非表示 |
| <kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | 別の候補をプレビュー |
| <kbd>Alt</kbd>+<kbd>PgUp</kbd> / <kbd>PgDn</kbd> | 全文をスクロール |
| <kbd>Alt</kbd>+<kbd>0</kbd> | パネルの表示／非表示 |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>P</kbd> | 翻訳の一時停止／再開 |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>O</kbd> | 設定を開く |

候補の右クリックから挿入、コピー、再試行ができます。マウスを使う場合は **Settings → Appearance → Keep the panel clickable** を有効にしてください。WeType の透明なウィンドウによるクリックの遮断を避けるため、パネルをその範囲外に移動します。

## プライバシー

- **ローカルで読む情報：** 候補とピンイン、候補ウィンドウの位置、アプリ除外や検出可能なパスワード欄の判定に必要な前面アプリ情報。
- **送信：** キャッシュにない候補と翻訳先を、選択したサービスだけに送ります。辞書の訳もサービスで改善する場合があります。Local only またはサービス未設定時は翻訳リクエストを送りません。
- **保存：** 設定ファイルにキーは含みません。キーは Windows 資格情報マネージャー、対象となる短い辞書語は暗号化ディスクキャッシュに保存します。長文はメモリのみです。ログに候補や翻訳は含みません。
- アカウント登録、テレメトリー、更新確認はありません。パスワード検出と短語の判定には限界があります。

詳細は [Privacy（英語）](docs/privacy.md) を参照してください。

## 動作環境

| 項目 | 要件 |
|---|---|
| Windows | 10 または 11、x64 |
| 入力メソッド | [WeType for Windows](https://z.weixin.qq.com/)、検証済み **3.0.0.34** |
| 翻訳サービス | 任意。フレーズ、文章、英語以外の翻訳先には自分の API キーが必要 |
| 容量 | 現行公開版はダウンロード約 200 MB、展開後約 475 MB |

## 既知の制限

- WeType の内部メッセージを使用するため、更新によって動作しなくなる場合があります。[Issues](https://github.com/Rickywu05/wetype-translate/issues) にバージョンを添えて報告してください。
- Frida が入力メソッドのプロセスに接続するため、セキュリティソフトが警告する場合があります。
- コード署名は未対応です。初回起動時に SmartScreen が警告する場合があります。
- 主に Windows 11、1画面、100% スケーリングの1台で検証しています。複数画面、他の倍率、Windows ARM は未検証です。
- ポータブル版のみで、インストーラーとスタートメニュー項目はありません。移動後は EXE を一度実行して自動起動パスを更新してください。
- 内蔵辞書は中国語から英語のみです。

## よくある質問

<details>
<summary><b>「Windows によって PC が保護されました」と表示されます。</b></summary>

コード署名がないため警告される場合があります。配布元を確認したうえで「詳細情報 → 実行」を選べます。配布ページの `SHA256SUMS.txt` と比較できます。

```powershell
Get-FileHash .\Translate-0.1.0-win-x64.zip -Algorithm SHA256
```

</details>

<details>
<summary><b>起動しても何も表示されません。</b></summary>

バックグラウンドツールのため通常は何も表示しません。WeType でピンインを入力するとパネルが現れます。EXE の再実行または Ctrl+Alt+O で設定を開けます。

</details>

<details>
<summary><b>API キーは必須ですか？</b></summary>

必須ではありません。内蔵 CC-CEDICT で一部の単語を英語へ翻訳できます。文章や他の言語にはサービスが必要です。

</details>

<details>
<summary><b>一時停止、終了、削除の方法は？</b></summary>

Ctrl+Alt+P で一時停止／再開します。終了は Settings → About → Quit Translate です。

削除する前に Start with Windows を無効にして保存し、終了します。アプリのフォルダーと `%APPDATA%\Translate` を削除し、資格情報マネージャー内の `Translate:service:` で始まる項目を削除してください。

</details>

## 仕組み

同梱 Python エンジンが Frida を通じて `wetype_server.exe` から候補ウィンドウへのメッセージを観察し、候補とウィンドウ位置を取得します。キャッシュ、辞書、選択したサービスから翻訳を取得し、Electron のパネルに表示します。挿入時はピンイン変換を解除して `SendInput` で Unicode テキストを入力します。

[開発ガイド](docs/development.md) · [デザイン](DESIGN.md) · [通信仕様](docs/protocol.md) · [リリース構築](docs/release.md) · [変更履歴](CHANGELOG.md)

## ソースからビルド

Windows 10/11 x64、Node 22+、Python 3.12 が必要です。

```powershell
python -m pip install --target backend/vendor frida==17.23.3
cd app
npm install
node node_modules/electron/install.js
npm run build
node scripts/package.mjs
```

依存関係、テスト、ポータブル配布の構築は [開発ガイド](docs/development.md) を参照してください。

## フィードバック

[Issues](https://github.com/Rickywu05/wetype-translate/issues) に Windows と WeType のバージョンを添えて報告してください。診断ログは設定の Privacy から開けます。候補や翻訳は記録しません。

## ライセンス

[MIT](LICENSE) © 2026 Rickywu05

辞書は [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cedict)（CC BY-SA 4.0）由来です。Electron、Python、Frida などのライセンスは [第三者ライセンス](app/build/THIRD_PARTY_NOTICES.txt) を参照してください。

<div align="center"><sub>Translate は独立プロジェクトであり、Tencent または WeChat による製品、提携製品、公認製品ではありません。</sub></div>
