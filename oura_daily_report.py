#!/usr/bin/env python3
"""Oura Ring daily health report via Gmail SMTP."""

import os
import smtplib
import sys
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

OURA_BASE_URL = "https://api.ouraring.com/v2/usercollection"


def get_headers():
    token = os.environ["OURA_ACCESS_TOKEN"]
    return {"Authorization": f"Bearer {token}"}


def fetch(endpoint: str, start: str, end: str) -> list[dict]:
    url = f"{OURA_BASE_URL}/{endpoint}"
    resp = requests.get(url, headers=get_headers(), params={"start_date": start, "end_date": end}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def seconds_to_hm(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    h, m = divmod(seconds // 60, 60)
    return f"{h}時間{m:02d}分"


def score_color(score: int | None) -> str:
    if score is None:
        return "#888888"
    if score >= 85:
        return "#4CAF50"
    if score >= 70:
        return "#FF9800"
    return "#F44336"


def score_label(score: int | None) -> str:
    if score is None:
        return "データなし"
    if score >= 85:
        return "最適"
    if score >= 70:
        return "良好"
    return "注意"


def build_html(report_date: date, sleep: dict, readiness: dict, activity: dict, sleep_detail: dict) -> str:
    target = report_date.strftime("%Y年%-m月%-d日")

    sleep_score = sleep.get("score")
    readiness_score = readiness.get("score")
    activity_score = activity.get("score")

    total_sleep = seconds_to_hm(sleep_detail.get("total_sleep_duration"))
    deep_sleep = seconds_to_hm(sleep_detail.get("deep_sleep_duration"))
    rem_sleep = seconds_to_hm(sleep_detail.get("rem_sleep_duration"))
    light_sleep = seconds_to_hm(sleep_detail.get("light_sleep_duration"))
    efficiency = sleep_detail.get("efficiency")
    efficiency_str = f"{efficiency}%" if efficiency is not None else "—"

    steps = activity.get("steps")
    steps_str = f"{steps:,}" if steps is not None else "—"
    active_cal = activity.get("active_calories")
    active_cal_str = f"{active_cal} kcal" if active_cal is not None else "—"
    total_cal = activity.get("total_calories")
    total_cal_str = f"{total_cal} kcal" if total_cal is not None else "—"

    s_color = score_color(sleep_score)
    r_color = score_color(readiness_score)
    a_color = score_color(activity_score)

    s_label = score_label(sleep_score)
    r_label = score_label(readiness_score)
    a_label = score_label(activity_score)

    readiness_contrib = readiness.get("contributors", {})
    hrv = readiness_contrib.get("hrv_balance")
    rhr = readiness_contrib.get("resting_heart_rate")
    body_temp = readiness_contrib.get("body_temperature")

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Oura 日次レポート {target}</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:'Helvetica Neue',Arial,'Hiragino Kaku Gothic ProN',sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:24px 0;">
<tr><td align="center">

  <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

    <!-- ヘッダー -->
    <tr>
      <td style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);border-radius:12px 12px 0 0;padding:32px 32px 24px;text-align:center;">
        <div style="font-size:28px;margin-bottom:4px;">💍</div>
        <h1 style="margin:0;color:#e0e0e0;font-size:20px;font-weight:700;letter-spacing:1px;">Oura Ring 日次ヘルスレポート</h1>
        <p style="margin:8px 0 0;color:#a0aec0;font-size:14px;">{target}</p>
      </td>
    </tr>

    <!-- スコアカード -->
    <tr>
      <td style="background:#ffffff;padding:28px 32px 20px;">
        <h2 style="margin:0 0 20px;color:#2d3748;font-size:15px;font-weight:700;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">📊 本日のスコア</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <!-- 睡眠スコア -->
            <td width="31%" style="text-align:center;padding:16px 8px;background:#f8fafc;border-radius:10px;margin:4px;">
              <div style="font-size:13px;color:#718096;margin-bottom:8px;">😴 睡眠</div>
              <div style="font-size:42px;font-weight:900;color:{s_color};line-height:1;">{sleep_score if sleep_score is not None else '—'}</div>
              <div style="margin-top:6px;display:inline-block;background:{s_color};color:#fff;font-size:11px;padding:2px 10px;border-radius:20px;">{s_label}</div>
            </td>
            <td width="4%"></td>
            <!-- 準備スコア -->
            <td width="31%" style="text-align:center;padding:16px 8px;background:#f8fafc;border-radius:10px;">
              <div style="font-size:13px;color:#718096;margin-bottom:8px;">⚡ 準備度</div>
              <div style="font-size:42px;font-weight:900;color:{r_color};line-height:1;">{readiness_score if readiness_score is not None else '—'}</div>
              <div style="margin-top:6px;display:inline-block;background:{r_color};color:#fff;font-size:11px;padding:2px 10px;border-radius:20px;">{r_label}</div>
            </td>
            <td width="4%"></td>
            <!-- アクティビティスコア -->
            <td width="31%" style="text-align:center;padding:16px 8px;background:#f8fafc;border-radius:10px;">
              <div style="font-size:13px;color:#718096;margin-bottom:8px;">🏃 活動量</div>
              <div style="font-size:42px;font-weight:900;color:{a_color};line-height:1;">{activity_score if activity_score is not None else '—'}</div>
              <div style="margin-top:6px;display:inline-block;background:{a_color};color:#fff;font-size:11px;padding:2px 10px;border-radius:20px;">{a_label}</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- 睡眠詳細 -->
    <tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">🌙 睡眠詳細</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="color:#718096;font-size:14px;">総睡眠時間</span>
              <span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{total_sleep}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="color:#718096;font-size:14px;">🟣 深睡眠（ノンレム深部）</span>
              <span style="float:right;font-weight:700;color:#6b46c1;font-size:14px;">{deep_sleep}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="color:#718096;font-size:14px;">🔵 REMスリープ</span>
              <span style="float:right;font-weight:700;color:#3182ce;font-size:14px;">{rem_sleep}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="color:#718096;font-size:14px;">⚪ 浅い睡眠</span>
              <span style="float:right;font-weight:700;color:#718096;font-size:14px;">{light_sleep}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;">
              <span style="color:#718096;font-size:14px;">睡眠効率</span>
              <span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{efficiency_str}</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- 身体状態 -->
    <tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">💓 身体状態（準備度の内訳）</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="color:#718096;font-size:14px;">HRVバランス</span>
              <span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{f'{hrv}点' if hrv is not None else '—'}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="color:#718096;font-size:14px;">安静時心拍数</span>
              <span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{f'{rhr}点' if rhr is not None else '—'}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;">
              <span style="color:#718096;font-size:14px;">体温偏差</span>
              <span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{f'{body_temp}点' if body_temp is not None else '—'}</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- アクティビティ -->
    <tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;text-transform:uppercase;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">🏃 活動量（昨日）</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="color:#718096;font-size:14px;">歩数</span>
              <span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{steps_str} 歩</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;border-bottom:1px solid #f0f0f0;">
              <span style="color:#718096;font-size:14px;">アクティブ消費カロリー</span>
              <span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{active_cal_str}</span>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 0;">
              <span style="color:#718096;font-size:14px;">総消費カロリー</span>
              <span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{total_cal_str}</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- フッター -->
    <tr>
      <td style="background:#f8fafc;border-radius:0 0 12px 12px;padding:20px 32px;text-align:center;border-top:1px solid #e2e8f0;">
        <p style="margin:0;color:#a0aec0;font-size:12px;">このメールはOura Ring APIから自動生成されました</p>
        <p style="margin:6px 0 0;color:#a0aec0;font-size:12px;">Powered by GitHub Actions + Oura API v2</p>
      </td>
    </tr>

  </table>
</td></tr>
</table>
</body>
</html>"""


def send_email(subject: str, html_body: str) -> None:
    gmail_address = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(gmail_address, app_password)
        smtp.sendmail(gmail_address, gmail_address, msg.as_string())


def main() -> None:
    today = date.today()
    yesterday = today - timedelta(days=1)
    start = yesterday.isoformat()
    end = yesterday.isoformat()

    print(f"対象日付: {start}")

    # daily_sleep: スコアと集計値
    sleep_data = fetch("daily_sleep", start, end)
    sleep = sleep_data[0] if sleep_data else {}

    # daily_readiness: スコアと内訳
    readiness_data = fetch("daily_readiness", start, end)
    readiness = readiness_data[0] if readiness_data else {}

    # daily_activity: 歩数・カロリー
    activity_data = fetch("daily_activity", start, end)
    activity = activity_data[0] if activity_data else {}

    # sleep (詳細): 深睡眠・REM・効率
    sleep_detail_data = fetch("sleep", start, end)
    # 複数セッションある場合は合算
    sleep_detail: dict = {}
    if sleep_detail_data:
        keys = ["total_sleep_duration", "deep_sleep_duration", "rem_sleep_duration", "light_sleep_duration"]
        for k in keys:
            total = sum(s.get(k) or 0 for s in sleep_detail_data)
            sleep_detail[k] = total if total > 0 else None
        efficiencies = [s.get("efficiency") for s in sleep_detail_data if s.get("efficiency") is not None]
        sleep_detail["efficiency"] = round(sum(efficiencies) / len(efficiencies)) if efficiencies else None

    html = build_html(yesterday, sleep, readiness, activity, sleep_detail)

    date_str = yesterday.strftime("%Y/%m/%d")
    s_score = sleep.get("score", "?")
    r_score = readiness.get("score", "?")
    subject = f"[Oura] {date_str} 日次レポート｜睡眠{s_score}・準備度{r_score}"

    send_email(subject, html)
    print("メール送信完了")


if __name__ == "__main__":
    main()
