# Portfolio

長門石直彦のポートフォリオサイト + Oura Ring 健康レポート自動送信システム

---

## Oura Ring 日次ヘルスレポート

Oura Ring API v2 から睡眠・準備度・活動量データを取得し、  
1日2回（JST 04:00 / 08:00）Gmail で HTML メールを自動送信する仕組みです。

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
| 過去7日トレンド | 睡眠・準備度・活動量のスコア推移 |

---

### 実行スケジュール

| 実行時刻（JST） | UTC | レポート種別 | 件名プレフィックス |
|---|---|---|---|
| 04:00 | 19:00 | 前日確定レポート | `[Oura 確定]` |
| 08:00 | 23:00 | 当日朝レポート | `[Oura 朝]` |

---

### エラー時の挙動

| 状況 | 挙動 |
|---|---|
| Timeout / 通信エラー | 最大3回リトライ（2s → 4s 指数バックオフ）後に失敗 |
| `daily_sleep` 取得失敗 | メール本文に警告バナーを表示してメール送信は継続 |
| その他のエンドポイント失敗 | ワークフロー全体が失敗し、失敗通知メールを送信 |

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

#### 5. 動作テスト（手動実行）

Actions タブ → 「Oura Daily Health Report」→ **「Run workflow」** でレポートモードを選択して即時実行できます。

| 選択肢 | 送信される件名 |
|---|---|
| `morning`（デフォルト） | `[Oura 朝] YYYY/MM/DD 当日朝レポート` |
| `confirmed` | `[Oura 確定] YYYY/MM/DD 前日確定レポート` |

---

### ファイル構成

```
portfolio/
├── oura_daily_report.py              # メイン Python スクリプト
├── requirements.txt                  # 依存パッケージ（requests）
├── .github/
│   └── workflows/
│       └── oura-daily-report.yml    # GitHub Actions ワークフロー
└── README.md                        # このファイル
```

### ローカル実行

```bash
pip install -r requirements.txt

export OURA_ACCESS_TOKEN="your_token"
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export REPORT_MODE="morning"  # または confirmed

python oura_daily_report.py
```

### トラブルシューティング

| エラー | 原因と対処 |
|---|---|
| `535 Authentication failed` | アプリパスワードが誤っている。スペースなしの16文字で登録する |
| `401 Unauthorized` | Oura トークンが無効。Cloud で再発行する |
| スコアが「—」表示 | 前日のデータがまだ同期されていない。数時間後に再実行 |
| `SMTPAuthenticationError` | Googleアカウントの2段階認証が無効。有効化してアプリパスワードを再取得 |
| メールに警告バナーが表示される | 睡眠データの取得に失敗（同期遅延が多い）。翌実行で自動回復する |
