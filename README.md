# Portfolio

長門石直彦のポートフォリオサイト + Oura Ring 健康レポート自動送信システム

---

## Oura Ring 日次ヘルスレポート

Oura Ring API v2 から睡眠・準備度・活動量データを取得し、  
毎朝7時（JST）に Gmail でHTMLメールを自動送信する仕組みです。

### レポートに含まれるデータ

| カテゴリ | 内容 |
|---|---|
| 睡眠スコア | Oura の総合睡眠スコア（0〜100） |
| 準備度スコア | 当日のコンディション指標 |
| 活動量スコア | 前日の活動達成度 |
| 睡眠時間の内訳 | 深睡眠・REM・浅い睡眠・総睡眠時間 |
| 睡眠効率 | ベッド内で眠れていた割合 |
| 身体状態 | HRVバランス・安静時心拍数・体温偏差 |
| 活動量 | 歩数・アクティブ消費カロリー・総消費カロリー |

---

### セットアップ手順

#### 1. Oura API アクセストークンの取得

1. [Oura Cloud](https://cloud.ouraring.com/personal-access-tokens) にログイン
2. **「Personal Access Token」** を新規作成
3. 生成されたトークンをコピー（後で GitHub Secrets に登録）

#### 2. Gmail アプリパスワードの取得

> 通常のGmailパスワードは使用できません。Googleアカウントの「アプリパスワード」が必要です。

1. Googleアカウント → **[セキュリティ]** → **[2段階認証プロセス]** を有効化
2. **[アプリパスワード]** → アプリ名を入力（例: `oura-report`）→ **[作成]**
3. 生成された16桁のパスワードをコピー

#### 3. GitHub Secrets の設定

リポジトリの **Settings → Secrets and variables → Actions → New repository secret** で以下を登録：

| Secret名 | 値 |
|---|---|
| `OURA_ACCESS_TOKEN` | Oura のPersonal Access Token |
| `GMAIL_ADDRESS` | 送信元＆送信先のGmailアドレス（例: `you@gmail.com`） |
| `GMAIL_APP_PASSWORD` | Googleのアプリパスワード（16桁） |

#### 4. GitHub Actions の有効化確認

リポジトリの **Actions タブ** → 「Oura Daily Health Report」ワークフローが表示されていればOK。

以下の2回、自動実行されます。

| 実行時刻（JST） | UTC | レポート種別 |
|---|---|---|
| 04:00 | 19:00 | 前日確定レポート（睡眠データが確定した後） |
| 08:00 | 23:00 | 当日朝レポート（起床後の最新データ） |

#### 5. 動作テスト（手動実行）

Actions タブ → 「Oura Daily Health Report」→ **「Run workflow」** で即時実行してメールを確認できます。

---

### ファイル構成

```
portfolio/
├── oura_daily_report.py              # メイン Python スクリプト
├── .github/
│   └── workflows/
│       └── oura-daily-report.yml    # GitHub Actions ワークフロー
└── README.md                        # このファイル
```

### ローカル実行

```bash
pip install requests

export OURA_ACCESS_TOKEN="your_token"
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"

python oura_daily_report.py
```

### トラブルシューティング

| エラー | 原因と対処 |
|---|---|
| `535 Authentication failed` | アプリパスワードが誤っている。スペースなしの16文字で登録する |
| `401 Unauthorized` | Oura トークンが無効。Cloud で再発行する |
| スコアが「—」表示 | 前日のデータがまだ同期されていない。数時間後に再実行 |
| `SMTPAuthenticationError` | Googleアカウントの2段階認証が無効。有効化してアプリパスワードを再取得 |
