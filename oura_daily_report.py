#!/usr/bin/env python3
"""Oura Ring daily health report via Gmail SMTP."""

import json
import os
import smtplib
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
    if not resp.ok:
        print(f"[ERROR] {endpoint}: HTTP {resp.status_code} - {resp.text}")
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


def avg(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def trend_arrow(current: int | None, week_avg: float | None) -> str:
    if current is None or week_avg is None:
        return ""
    diff = current - week_avg
    if diff >= 3:
        return " ↑"
    if diff <= -3:
        return " ↓"
    return " →"


def generate_insights(
    sleep: dict,
    readiness: dict,
    activity: dict,
    sleep_detail: dict,
    week_sleep: list[dict],
    week_readiness: list[dict],
    week_activity: list[dict],
) -> list[dict]:
    insights = []

    sleep_score = sleep.get("score")
    readiness_score = readiness.get("score")
    deep_secs = sleep_detail.get("deep_sleep_duration")
    total_secs = sleep_detail.get("total_sleep_duration")
    readiness_contrib = readiness.get("contributors", {})
    hrv = readiness_contrib.get("hrv_balance")

    sorted_sleep = sorted(week_sleep, key=lambda x: x.get("day", ""))
    sorted_act = sorted(week_activity, key=lambda x: x.get("day", ""))

    recent_sleep_scores = [d.get("score") for d in sorted_sleep[-3:] if d.get("score")]
    recent_act_scores = [d.get("score") for d in sorted_act[-3:] if d.get("score")]

    week_sleep_avg = avg([d.get("score") for d in week_sleep])
    week_ready_avg = avg([d.get("score") for d in week_readiness])

    if sleep_score is not None:
        if sleep_score >= 85:
            insights.append({"type": "good", "text": f"睡眠スコア {sleep_score} は最適レベルです。この調子を維持しましょう。"})
        elif sleep_score < 70:
            insights.append({"type": "warn", "text": f"睡眠スコア {sleep_score} はやや低調です。就寝時間を〰6分早めるか、寝室の温度・光環境を見直してみてください。"})

    if len(recent_sleep_scores) >= 3:
        if recent_sleep_scores[-1] > recent_sleep_scores[0] + 5:
            insights.append({"type": "good", "text": "直近3日で睡眠スコアが改善傾向にあります。良い習慣が続いています。"})
        elif recent_sleep_scores[-1] < recent_sleep_scores[0] - 5:
            insights.append({"type": "warn", "text": "直近3日で睡眠スコアが下降傾向です。就寝前のスマホ使用や飲酒を控えると改善しやすいです。"})

    if deep_secs is not None:
        if deep_secs < 45 * 60:
            insights.append({"type": "warn", "text": f"深睡眠が{seconds_to_hm(deep_secs)}と少なめです。就寝2時間前のカフェイン・アルコール・激しい運動を避けると深睡眠が増えやすくなります。"})
        elif deep_secs >= 90 * 60:
            insights.append({"type": "good", "text": f"深睡眠が{seconds_to_hm(deep_secs)}と十分確保できています。身体の回復・記憶定着に効果的です。"})

    if total_secs is not None and total_secs < 6 * 3600:
        insights.append({"type": "warn", "text": f"総睡眠時間が{seconds_to_hm(total_secs)}と6時間を下回っています。\u6んな性的な睡眠不足は集中力・免疫力の低下につながります。"})

    if readiness_score is not None:
        if readiness_score >= 85:
            insights.append({"type": "good", "text": f"準備度 {readiness_score} は絶好調です。今日はトレーニングや集中作業に最適な日です。"})
        elif readiness_score < 70:
            insights.append({"type": "warn", "text": f"準備度 {readiness_score} はやや低め。高強度トレーニングは避け、ウォーキングや軽いストレッチ程度にとどめましょう。"})

    if hrv is not None:
        if hrv >= 90:
            insights.append({"type": "good", "text": f"HRVバランス {hrv}点 は非常に高く、自律神経が整っています。"})
        elif hrv < 60:
            insights.append({"type": "warn", "text": f"HRVバランスが {hrv}点 と低下しています。ストレスや疲労が蓄積している可能性があります。深呼吸・瑞想・入浴が効果的です。"})

    if len(recent_act_scores) >= 3:
        if sum(1 for s in recent_act_scores if s < 70) >= 2:
            insights.append({"type": "tip", "text": "直近3日のうち活動量スコアが低い日が続いています。通勤でひと駅歩く・昜休みに10分散歩するなど小さな積み重ねが効果的です。"})

    if sleep_score and week_sleep_avg and sleep_score >= week_sleep_avg + 5:
        insights.append({"type": "good", "text": f"昨日の睡眠スコアは週平均（{week_sleep_avg:.0f}）より {sleep_score - week_sleep_avg:.0f}点 上回っています。"})

    if readiness_score and week_ready_avg and readiness_score < week_ready_avg - 5:
        insights.append({"type": "tip", "text": f"準備度が週平均（{week_ready_avg:.0f}）より低下しています。今日は回復優先で過ごすのが賢明です。"})

    if not insights:
        insights.append({"type": "good", "text": "全体的に安定したコンディションです。この生活リズムを継続しましょう。"})

    return insights


def generate_claude_analysis(
    week_sleep: list[dict],
    week_readiness: list[dict],
    week_activity: list[dict],
    sleep_sessions: list[dict],
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return ""
    try:
        import anthropic

        sorted_sleep = sorted(week_sleep, key=lambda x: x.get("day", ""))[-3:]
        sorted_ready = sorted(week_readiness, key=lambda x: x.get("day", ""))[-3:]
        sorted_act = sorted(week_activity, key=lambda x: x.get("day", ""))[-3:]
        sorted_sess = sorted(sleep_sessions, key=lambda x: x.get("day", ""))[-3:]

        payload = {
            "sleep_scores": [{"day": d.get("day"), "score": d.get("score")} for d in sorted_sleep],
            "readiness_scores": [{"day": d.get("day"), "score": d.get("score")} for d in sorted_ready],
            "activity_scores": [{"day": d.get("day"), "score": d.get("score")} for d in sorted_act],
            "sleep_detail": [
                {
                    "day": s.get("day"),
                    "total_sleep_min": (s.get("total_sleep_duration") or 0) // 60,
                    "deep_sleep_min": (s.get("deep_sleep_duration") or 0) // 60,
                    "rem_sleep_min": (s.get("rem_sleep_duration") or 0) // 60,
                    "efficiency": s.get("efficiency"),
                }
                for s in sorted_sess
            ],
        }

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=[
                {
                    "type": "text",
                    "text": (
                        "あなたはOura Ringデータをもとに睡眠・健康改善を提案する専門家です。"
                        "データを分析し、具体的で実行しやすい改善提案を3点、日本語で簡潔に述べてください。"
                        "各提案は「・」で始め、2〜3文以内にまとめてください。"
                        "データがない場合は一般的な睡眠改善アドバイスを述べてください。"
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"直近3日間の健康データ:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\nこのデータに基づいて改善提案を3点述べてください。",
                }
            ],
        )
        return message.content[0].text
    except Exception as e:
        print(f"[WARN] Claude API error: {e}")
        return ""


def build_html(
    report_date: date,
    sleep: dict,
    readiness: dict,
    activity: dict,
    sleep_detail: dict,
    week_sleep: list[dict],
    week_readiness: list[dict],
    week_activity: list[dict],
    claude_analysis: str = "",
) -> str:
    target = report_date.strftime("%Y年%-m月%-d日")

    sleep_score = sleep.get("score")
    readiness_score = readiness.get("score")
    activity_score = activity.get("score")

    w_sleep_avg = avg([d.get("score") for d in week_sleep])
    w_ready_avg = avg([d.get("score") for d in week_readiness])
    w_act_avg = avg([d.get("score") for d in week_activity])

    s_arrow = trend_arrow(sleep_score, w_sleep_avg)
    r_arrow = trend_arrow(readiness_score, w_ready_avg)
    a_arrow = trend_arrow(activity_score, w_act_avg)

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

    w_sleep_str = f"{w_sleep_avg:.0f}" if w_sleep_avg is not None else "—"
    w_ready_str = f"{w_ready_avg:.0f}" if w_ready_avg is not None else "—"
    w_act_str = f"{w_act_avg:.0f}" if w_act_avg is not None else "—"

    def score_bar(score):
        if score is None:
            return "<span style='color:#ccc;font-size:13px;'>—</span>"
        color = score_color(score)
        bar_w = max(4, score)
        return f"<span style='display:inline-block;width:{bar_w}px;height:10px;background:{color};border-radius:2px;vertical-align:middle;margin-right:6px;'></span><span style='color:{color};font-weight:700;font-size:13px;'>{score}</span>"

    all_days = sorted(set(
        [d.get("day") for d in week_sleep if d.get("day")] +
        [d.get("day") for d in week_readiness if d.get("day")] +
        [d.get("day") for d in week_activity if d.get("day")]
    ), reverse=True)[:7]

    sleep_by_day = {d.get("day"): d.get("score") for d in week_sleep}
    ready_by_day = {d.get("day"): d.get("score") for d in week_readiness}
    act_by_day = {d.get("day"): d.get("score") for d in week_activity}

    trend_rows = ""
    for day in all_days:
        try:
            d = date.fromisoformat(day)
            day_label = d.strftime("%-m/%-d")
            weekday = ["月", "火", "水", "木", "金", "土", "日"][d.weekday()]
        except Exception:
            day_label = day
            weekday = ""
        bg = "#fffbeb" if day == report_date.isoformat() else "transparent"
        s = score_bar(sleep_by_day.get(day))
        r = score_bar(ready_by_day.get(day))
        a = score_bar(act_by_day.get(day))
        trend_rows += f"""
        <tr style="background:{bg};">
          <td style="padding:7px 8px;color:#718096;font-size:13px;white-space:nowrap;">{day_label}({weekday})</td>
          <td style="padding:7px 8px;">{s}</td>
          <td style="padding:7px 8px;">{r}</td>
          <td style="padding:7px 8px;">{a}</td>
        </tr>"""

    insights = generate_insights(sleep, readiness, activity, sleep_detail, week_sleep, week_readiness, week_activity)
    insight_rows = ""
    type_config = {
        "good": ("#f0fff4", "#276749", "✅"),
        "warn": ("#fffaf0", "#c05621", "⚠️"),
        "tip":  ("#ebf8ff", "#2b6cb0", "\U0001f4a1"),
    }
    for ins in insights:
        bg_c, text_c, icon = type_config.get(ins["type"], ("#f8fafc", "#4a5568", "ℹ️"))
        insight_rows += f"""
        <tr>
          <td style="padding:10px 12px;background:{bg_c};border-radius:8px;display:block;">
            <span style="font-size:14px;">{icon} </span>
            <span style="color:{text_c};font-size:14px;line-height:1.6;">{ins["text"]}</span>
          </td>
        </tr>
        <tr><td style="height:6px;"></td></tr>"""

    claude_section = ""
    if claude_analysis:
        claude_section = f"""<tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">\U0001f916 3日間の傾向と改善提案（AI分析）</h2>
        <div style="background:#f0f4ff;border-radius:8px;padding:16px 18px;color:#2d3748;font-size:14px;line-height:1.8;white-space:pre-wrap;">{claude_analysis}</div>
      </td>
    </tr>"""

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

    <tr>
      <td style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);border-radius:12px 12px 0 0;padding:32px 32px 24px;text-align:center;">
        <div style="font-size:28px;margin-bottom:4px;">\U0001f48d</div>
        <h1 style="margin:0;color:#e0e0e0;font-size:20px;font-weight:700;letter-spacing:1px;">Oura Ring 日次ヘルスレポート</h1>
        <p style="margin:8px 0 0;color:#a0aec0;font-size:14px;">{target}</p>
      </td>
    </tr>

    <tr>
      <td style="background:#ffffff;padding:28px 32px 20px;">
        <h2 style="margin:0 0 20px;color:#2d3748;font-size:15px;font-weight:700;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">\U0001f4ca 昨日のスコア</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="31%" style="text-align:center;padding:16px 8px;background:#f8fafc;border-radius:10px;">
              <div style="font-size:13px;color:#718096;margin-bottom:8px;">\U0001f634 睡眠</div>
              <div style="font-size:42px;font-weight:900;color:{s_color};line-height:1;">{sleep_score if sleep_score is not None else '—'}<span style="font-size:16px;">{s_arrow}</span></div>
              <div style="margin-top:6px;font-size:11px;color:#a0aec0;">週平均 {w_sleep_str}</div>
              <div style="margin-top:4px;display:inline-block;background:{s_color};color:#fff;font-size:11px;padding:2px 10px;border-radius:20px;">{s_label}</div>
            </td>
            <td width="4%"></td>
            <td width="31%" style="text-align:center;padding:16px 8px;background:#f8fafc;border-radius:10px;">
              <div style="font-size:13px;color:#718096;margin-bottom:8px;">⚡ 準備度</div>
              <div style="font-size:42px;font-weight:900;color:{r_color};line-height:1;">{readiness_score if readiness_score is not None else '—'}<span style="font-size:16px;">{r_arrow}</span></div>
              <div style="margin-top:6px;font-size:11px;color:#a0aec0;">週平均 {w_ready_str}</div>
              <div style="margin-top:4px;display:inline-block;background:{r_color};color:#fff;font-size:11px;padding:2px 10px;border-radius:20px;">{r_label}</div>
            </td>
            <td width="4%"></td>
            <td width="31%" style="text-align:center;padding:16px 8px;background:#f8fafc;border-radius:10px;">
              <div style="font-size:13px;color:#718096;margin-bottom:8px;">\U0001f3c3 活動量</div>
              <div style="font-size:42px;font-weight:900;color:{a_color};line-height:1;">{activity_score if activity_score is not None else '—'}<span style="font-size:16px;">{a_arrow}</span></div>
              <div style="margin-top:6px;font-size:11px;color:#a0aec0;">週平均 {w_act_str}</div>
              <div style="margin-top:4px;display:inline-block;background:{a_color};color:#fff;font-size:11px;padding:2px 10px;border-radius:20px;">{a_label}</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">\U0001f9e0 今日のポイントと提案</h2>
        <table width="100%" cellpadding="0" cellspacing="0">{insight_rows}</table>
      </td>
    </tr>

    <tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">\U0001f4c8 過去7日のトレンド</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr style="background:#f8fafc;">
            <th style="padding:8px;text-align:left;font-size:12px;color:#a0aec0;font-weight:600;">日付</th>
            <th style="padding:8px;text-align:left;font-size:12px;color:#a0aec0;font-weight:600;">睡眠</th>
            <th style="padding:8px;text-align:left;font-size:12px;color:#a0aec0;font-weight:600;">準備度</th>
            <th style="padding:8px;text-align:left;font-size:12px;color:#a0aec0;font-weight:600;">活動量</th>
          </tr>
          {trend_rows}
        </table>
      </td>
    </tr>

    <tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">\U0001f319 睡眠詳細</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#718096;font-size:14px;">総睡眠時間</span><span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{total_sleep}</span></td></tr>
          <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#718096;font-size:14px;">\U0001f7e3 深睡眠（ノンレム深部）</span><span style="float:right;font-weight:700;color:#6b46c1;font-size:14px;">{deep_sleep}</span></td></tr>
          <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#718096;font-size:14px;">\U0001f535 REMスリープ</span><span style="float:right;font-weight:700;color:#3182ce;font-size:14px;">{rem_sleep}</span></td></tr>
          <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#718096;font-size:14px;">⚪ 浅い睡眠</span><span style="float:right;font-weight:700;color:#718096;font-size:14px;">{light_sleep}</span></td></tr>
          <tr><td style="padding:10px 0;"><span style="color:#718096;font-size:14px;">睡眠効率</span><span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{efficiency_str}</span></td></tr>
        </table>
      </td>
    </tr>

    <tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">\U0001f493 身体状態（準備度の内訳）</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#718096;font-size:14px;">HRVバランス</span><span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{f'{hrv}点' if hrv is not None else '—'}</span></td></tr>
          <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#718096;font-size:14px;">安静時心拍数</span><span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{f'{rhr}点' if rhr is not None else '—'}</span></td></tr>
          <tr><td style="padding:10px 0;"><span style="color:#718096;font-size:14px;">体温偏差</span><span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{f'{body_temp}点' if body_temp is not None else '—'}</span></td></tr>
        </table>
      </td>
    </tr>

    <tr>
      <td style="background:#ffffff;padding:8px 32px 24px;">
        <h2 style="margin:0 0 16px;color:#2d3748;font-size:15px;font-weight:700;letter-spacing:1px;border-bottom:2px solid #e2e8f0;padding-bottom:10px;">\U0001f3c3 活動量（昨日）</h2>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#718096;font-size:14px;">歩数</span><span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{steps_str} 歩</span></td></tr>
          <tr><td style="padding:10px 0;border-bottom:1px solid #f0f0f0;"><span style="color:#718096;font-size:14px;">アクティブ消費カロリー</span><span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{active_cal_str}</span></td></tr>
          <tr><td style="padding:10px 0;"><span style="color:#718096;font-size:14px;">総消費カロリー</span><span style="float:right;font-weight:700;color:#2d3748;font-size:14px;">{total_cal_str}</span></td></tr>
        </table>
      </td>
    </tr>

    {claude_section}

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
    report_mode = os.environ.get("REPORT_MODE", "morning")
    today = date.today()
    yesterday = today - timedelta(days=1)
    start = yesterday.isoformat()
    end = yesterday.isoformat()
    four_days_ago = (today - timedelta(days=4)).isoformat()
    week_start = (today - timedelta(days=8)).isoformat()

    print(f"対象日付: {start} / mode: {report_mode}")

    week_sleep = fetch("daily_sleep", week_start, end)
    week_readiness = fetch("daily_readiness", week_start, end)
    week_activity = fetch("daily_activity", week_start, end)

    sleep = next((d for d in week_sleep if d.get("day") == start), {})
    readiness = next((d for d in week_readiness if d.get("day") == start), {})
    activity = next((d for d in week_activity if d.get("day") == start), {})

    sleep_sessions = fetch("sleep", four_days_ago, end)
    sleep_detail_data = [s for s in sleep_sessions if s.get("day") == start]
    sleep_detail: dict = {}
    if sleep_detail_data:
        keys = ["total_sleep_duration", "deep_sleep_duration", "rem_sleep_duration", "light_sleep_duration"]
        for k in keys:
            total = sum(s.get(k) or 0 for s in sleep_detail_data)
            sleep_detail[k] = total if total > 0 else None
        efficiencies = [s.get("efficiency") for s in sleep_detail_data if s.get("efficiency") is not None]
        sleep_detail["efficiency"] = round(sum(efficiencies) / len(efficiencies)) if efficiencies else None

    claude_analysis = generate_claude_analysis(week_sleep, week_readiness, week_activity, sleep_sessions)

    html = build_html(yesterday, sleep, readiness, activity, sleep_detail, week_sleep, week_readiness, week_activity, claude_analysis)

    date_str = yesterday.strftime("%Y/%m/%d")
    s_score = sleep.get("score", "?")
    r_score = readiness.get("score", "?")
    if report_mode == "confirmed":
        prefix = "[Oura 確定]"
        title = "前日確定レポート"
    else:
        prefix = "[Oura 朱]"
        title = "当日朝レポート"
    subject = f"{prefix} {date_str} {title}｜睡眠{s_score}・準備度{r_score}"

    send_email(subject, html)
    print("メール送信完了")


if __name__ == "__main__":
    main()
