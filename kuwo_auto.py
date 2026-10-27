#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
酷我音乐自动签到 / 每日任务 —— 去毒 · 服务器 · Web 面板版
========================================================
本程序从你购买的加密 EXE 中还原出酷我官方任务逻辑，并做减法：
  ✓ 仅调用酷我官方接口（*.kuwo.cn），无任何第三方外发
  ✗ 已物理移除所有发往第三方平台的请求（原 EXE 中的上报地址）
  ✗ 不实现自动提现（需手机验证码，请到官方 App 操作）

功能对照原闲鱼 EXE：
  登录 / 每日签到 / 创意视频·听歌 / 每日音乐 /
  开宝箱 / 抽奖 / 免费听歌开关 / 多账号 /
  内置定时任务(默认每天 09:00) / Web 面板 / 可选推送

【网络行为（全部为酷我官方域名，绝无其他）】
  - ar.i.kuwo.cn           登录
  - integralapi.kuwo.cn    签到 / 创意视频 / 开宝箱 / 抽奖 / 每日音乐
  - wapi.kuwo.cn           免费听歌开关

【运行】
  pip install flask requests
  python3 kuwo_auto.py --server            # 启动 Web 面板 + 每日定时
  python3 kuwo_auto.py --once              # 立即执行一次后退出
  python3 kuwo_auto.py --loop              # 常驻，每 2 小时一轮（旧模式）

【参数获取】
  安卓酷我 App 内用抓包工具抓取 ar.i.kuwo.cn/US_NEW/kuwo/login_kw 请求，取：
    appuid / devid / q(登录票据) / phone(绑定手机号)
"""

import os
import re
import sys
import json
import time
import random
import datetime
import logging
import threading

import requests

# ===================== 路径 =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.environ.get("KUWO_CONFIG", os.path.join(BASE_DIR, "config.json"))
LOG_PATH = os.path.join(BASE_DIR, "kuwo_sign.log")
STATE_PATH = os.path.join(BASE_DIR, "kuwo_state.json")
HISTORY_PATH = os.path.join(BASE_DIR, "kuwo_history.json")

# ===================== 日志（仅写文件+控制台，不外发） =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("kuwo")

# ===================== 默认设置 =====================
DEFAULT_SETTINGS = {
    "schedule": "09:00",       # 每天运行时间（daily 模式）
    "interval_mode": "daily",  # daily / interval
    "interval_minutes": 120,   # interval 模式下的间隔
    "min_delay": 15,           # 任务间随机延时下限（秒）
    "max_delay": 25,           # 上限
    "max_retry": 1,            # 单任务失败重试次数
    "web_host": "0.0.0.0",
    "web_port": 8080,
    "web_password": "",        # 建议设置，API/页面统一用 ?token= 或 X-Token
    "push": {                  # 可选推送，仅发往你自己的地址
        "type": "none",        # none / webhook / bark / tg
        "url": "",
        "token": "",
    },
}

# 运行时可变设置 / 账号
SETTINGS = dict(DEFAULT_SETTINGS)
ACCOUNTS = []
HISTORY = {}          # phone -> {last_run, status, username, reward, tasks:[...]}
run_lock = threading.Lock()
stop_event = threading.Event()


# ===================== 配置读写 =====================
def load_config():
    global SETTINGS, ACCOUNTS
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit(
            "未找到 config.json，请参考 config.example.json 创建：\n"
            '{"accounts":[{"appuid":"..","devid":"..","q":"..","phone":".."}]}'
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    SETTINGS.update({k: v for k, v in cfg.get("settings", {}).items() if k in DEFAULT_SETTINGS})
    if "push" in cfg.get("settings", {}):
        SETTINGS["push"].update(cfg["settings"]["push"])
    ACCOUNTS = cfg.get("accounts", [])
    if not ACCOUNTS:
        log.warning("config.json 中未配置任何 accounts")


def save_config():
    """把当前 ACCOUNTS / SETTINGS 写回 config.json（Web 面板增删账号用）。"""
    cfg = {"settings": SETTINGS, "accounts": ACCOUNTS}
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)


def load_history():
    global HISTORY
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                HISTORY = json.load(f)
        except Exception:
            HISTORY = {}


def save_history():
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(HISTORY, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.error("写入历史失败: %s", e)


# ===================== 请求头（模拟酷我 App WebView） =====================
def headers():
    return {
        "Connection": "keep-alive",
        "Accept": "application/json, text/plain, */*",
        "sec-ch-ua-mobile": "?1",
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 14; POCO F2 Pro Build/UQ1A.240105.004; wv) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/121.0.6167.101 "
            "Mobile Safari/537.36/ kuwopage"
        ),
        "sec-ch-ua-platform": '"Android"',
        "Origin": "https://h5app.kuwo.cn",
        "X-Requested-With": "cn.kuwo.player",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    }


# ===================== 登录 =====================
def login(q):
    """调用酷我登录接口，从 Set-Cookie 解析 uid/sid。"""
    url = "http://ar.i.kuwo.cn/US_NEW/kuwo/login_kw"
    h = {"Accept": "*/*", "Host": "ar.i.kuwo.cn", "Connection": "Keep-Alive"}
    try:
        r = requests.get(url, params={"f": "ar", "q": q}, headers=h, timeout=15)
        sc = r.headers.get("Set-Cookie", "")
        u = re.search(r"uname3=([^;]+)", sc)
        sid = re.search(r"websid=([^;]+)", sc)
        uid = re.search(r"userid=([^;]+)", sc)
        if not (u and sid and uid):
            log.warning("登录失败：无法从 Cookie 解析 uid/sid，请检查 q 参数")
            return None
        return {"username": u.group(1), "loginSid": sid.group(1), "loginUid": uid.group(1)}
    except Exception as e:
        log.error("登录异常: %s", e)
        return None


# ===================== 任务请求封装 =====================
def _call(url, params, tag):
    try:
        r = requests.get(url, params=params, headers=headers(), timeout=15)
        try:
            j = r.json()
        except Exception:
            return f"{tag}>>>非JSON响应: {r.text[:60]}"
        msg = j.get("msg") or j.get("message") or ""
        data = j.get("data") or {}
        obtain = data.get("obtain") or data.get("goldNum") or data.get("description") or ""
        text = (str(msg) + " " + str(obtain)).strip()
        return f"{tag}>>>{text or r.text[:60]}"
    except Exception as e:
        return f"{tag}>>>异常: {e}"


def do_sign(uid, sid, appuid):
    return _call(
        "https://integralapi.kuwo.cn/api/v1/online/sign/v1/earningSignIn/newDoListen",
        {"loginUid": uid, "loginSid": sid, "appUid": appuid, "terminal": "ar",
         "from": "sign", "adverId": "20130802-13379713291", "token": "",
         "extraGoldNum": "88", "clickExtraGoldNum": "0",
         "surpriseType": "", "verificationId": "", "mobile": ""},
        "签到",
    )


def do_listen(uid, sid, appuid):
    return _call(
        "https://integralapi.kuwo.cn/api/v1/online/sign/v1/earningSignIn/newDoListen",
        {"loginUid": uid, "loginSid": sid, "appUid": appuid, "terminal": "ar",
         "from": "videoadver", "goldNum": "58", "adverId": "", "token": "",
         "extraGoldNum": "0", "clickExtraGoldNum": "0",
         "surpriseType": "", "verificationId": "", "mobile": ""},
        "创意视频",
    )


def do_everyday_music(uid, sid, appuid):
    return _call(
        "https://integralapi.kuwo.cn/api/v1/online/sign/v1/earningSignIn/everydaymusic/doListen",
        {"loginUid": uid, "loginSid": sid, "appUid": appuid, "terminal": "ar",
         "from": "everyday", "token": "", "mobile": ""},
        "每日音乐",
    )


def do_box(uid, sid, devid, appuid):
    hour = datetime.datetime.now().hour
    ranges = {0: "00-08", 8: "08-10", 10: "10-12", 12: "12-14",
              14: "14-16", 16: "16-18", 18: "18-20", 20: "20-24"}
    tr = next((v for k, v in ranges.items() if k <= hour < k + 2), "20-24")
    return _call(
        "https://integralapi.kuwo.cn/api/v1/online/sign/new/newBoxFinish",
        {"loginUid": uid, "loginSid": sid, "devId": devid, "appUid": appuid,
         "source": "kwplayer_ar_10.7.6.2_qq.apk", "version": "kwplayer_ar_10.7.6.2",
         "r": f"{random.random()}", "action": "new", "time": tr,
         "goldNum": "23", "extraGoldnum": "0", "clickExtraGoldNum": "0"},
        f"开宝箱[{tr}]",
    )


def do_lottery(uid, sid, appuid, ltype):
    return _call(
        "https://integralapi.kuwo.cn/api/v1/online/sign/loterry/getLucky",
        {"loginUid": uid, "loginSid": sid, "appUid": appuid,
         "source": "kwplayer_ar_10.7.6.2_qq.apk", "type": ltype},
        "抽奖" if ltype == "free" else "看视频抽奖",
    )


def do_freemium(uid, sid, appuid):
    return _call(
        "https://wapi.kuwo.cn/openapi/v1/user/freemium/h5/switches",
        {"loginUid": uid, "loginSid": sid, "appUid": appuid, "terminal": "ar"},
        "免费听歌",
    )


# ===================== 每日去重 =====================
def already_done_today(phone):
    if not os.path.exists(STATE_PATH):
        return False
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state.get(phone) == datetime.date.today().isoformat()
    except Exception:
        return False


def mark_done(phone):
    state = {}
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
    state[phone] = datetime.date.today().isoformat()
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ===================== 单账号主流程 =====================
def run_account(acc, force=False):
    phone = acc.get("phone", "?")
    res = {"phone": phone, "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "status": "running", "username": "", "reward": 0, "tasks": [], "note": ""}
    if not force and already_done_today(phone):
        res["status"] = "skipped"
        res["note"] = "今日已执行（强制重跑请用 --force 或 Web 面板强制）"
        log.info("账号 %s 今日已执行，跳过", phone)
        return res

    info = login(acc.get("q", ""))
    if not info:
        res["status"] = "login_failed"
        res["note"] = "登录失败"
        log.warning("账号 %s 登录失败", phone)
        return res
    log.info("账号 %s 登录成功：%s", phone, info["username"])
    res["username"] = info["username"]
    uid, sid = info["loginUid"], info["loginSid"]
    appuid, devid = acc["appuid"], acc["devid"]

    tasks = [
        ("签到", lambda: do_sign(uid, sid, appuid)),
        ("创意视频", lambda: do_listen(uid, sid, appuid)),
        ("每日音乐", lambda: do_everyday_music(uid, sid, appuid)),
        ("开宝箱", lambda: do_box(uid, sid, devid, appuid)),
        ("免费抽奖", lambda: do_lottery(uid, sid, appuid, "free")),
        ("看视频抽奖", lambda: do_lottery(uid, sid, appuid, "video")),
        ("免费听歌", lambda: do_freemium(uid, sid, appuid)),
    ]
    for name, fn in tasks:
        ok = False
        msg = ""
        for attempt in range(1 + SETTINGS.get("max_retry", 1)):
            try:
                msg = fn()
                ok = True
                break
            except Exception as e:
                msg = f"异常: {e}"
                time.sleep(3)
        res["tasks"].append({"name": name, "msg": msg, "ok": ok})
        log.info("  %s %s", name, msg)
        time.sleep(random.randint(SETTINGS["min_delay"], SETTINGS["max_delay"]))

    res["status"] = "done"
    mark_done(phone)
    HISTORY[phone] = res
    save_history()
    return res


def run_all(force=False):
    with run_lock:
        log.info("====== 开始执行全部账号 (force=%s) ======", force)
        results = []
        for acc in ACCOUNTS:
            if not all(k in acc for k in ("appuid", "devid", "q")):
                log.warning("跳过不完整账号: %s", acc)
                continue
            try:
                results.append(run_account(acc, force=force))
            except Exception as e:
                log.error("账号执行出错: %s", e)
        # 汇总推送
        summary = "酷我签到完成：\n" + "\n".join(
            f"· {r['phone']} [{r['status']}] " + " / ".join(t['name'] for t in r['tasks']) for r in results
        )
        log.info("====== 本轮结束 ======")
        if results:
            push_text(summary)
        return results


# ===================== 可选推送（仅发往你自己的地址） =====================
def push_text(text):
    p = SETTINGS.get("push") or {}
    t = p.get("type")
    try:
        if t == "webhook" and p.get("url"):
            requests.post(p["url"], json={"text": text}, timeout=10)
        elif t == "bark" and p.get("url"):
            requests.get(p["url"] + requests.utils.quote(text), timeout=10)
        elif t == "tg" and p.get("url"):
            requests.post(p["url"], json={"chat_id": p.get("token", ""), "text": text}, timeout=10)
        else:
            return
        log.info("推送已发送(%s)", t)
    except Exception as e:
        log.error("推送失败: %s", e)


# ===================== 内置调度器 =====================
def scheduler_loop():
    while not stop_event.is_set():
        mode = SETTINGS.get("interval_mode", "daily")
        if mode == "interval":
            secs = SETTINGS.get("interval_minutes", 120) * 60
            log.info("调度器(interval)：每 %d 分钟运行一次", SETTINGS.get("interval_minutes", 120))
            time.sleep(secs)
            if not stop_event.is_set():
                run_all()
        else:
            now = datetime.datetime.now()
            hh, mm = (int(x) for x in str(SETTINGS.get("schedule", "09:00")).split(":"))
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if target <= now:
                target += datetime.timedelta(days=1)
            secs = (target - now).total_seconds()
            log.info("调度器(daily)：下次运行 %s", target.strftime("%Y-%m-%d %H:%M"))
            if stop_event.wait(secs):
                break
            run_all()


# ===================== Web 面板 =====================
def make_app():
    from flask import Flask, request, jsonify, render_template_string

    app = Flask(__name__)
    PW = SETTINGS.get("web_password", "")

    def check_auth():
        if not PW:
            return True
        return request.args.get("token") == PW or request.headers.get("X-Token") == PW

    DASH = """
    <!doctype html><html lang="zh"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>酷我自动签到 · 面板</title>
    <style>
    :root{--bg:#0f1115;--card:#1a1d24;--fg:#e6e6e6;--m:#3b82f6;--ok:#22c55e;--bad:#ef4444;--mut:#9ca3af}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
    font:14px/1.6 -apple-system,Segoe UI,Roboto,Helvetica,Arial;padding:24px}
    h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:24px 0 8px;color:var(--mut)}
    .wrap{max-width:960px;margin:0 auto}
    .bar{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}
    button{background:var(--m);color:#fff;border:0;padding:9px 16px;border-radius:8px;
    cursor:pointer;font-size:14px}button.sec{background:#374151}
    .card{background:var(--card);border-radius:12px;padding:16px;margin-bottom:14px}
    table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px 10px;
    border-bottom:1px solid #2a2e37}th{color:var(--mut);font-weight:600}
    .tag{display:inline-block;padding:2px 8px;border-radius:6px;font-size:12px}
    .ok{background:rgba(34,197,94,.15);color:var(--ok)}
    .bad{background:rgba(239,68,68,.15);color:var(--bad)}
    .skip{background:rgba(156,163,175,.15);color:var(--mut)}
    .tasks{font-size:12px;color:var(--mut);margin-top:4px}
    input{background:#0b0d11;border:1px solid #2a2e37;color:var(--fg);
    border-radius:8px;padding:8px;width:100%;margin:4px 0}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    pre{background:#0b0d11;border-radius:10px;padding:14px;max-height:320px;overflow:auto;
    font-size:12px;color:#a5b4fc}
    a{color:var(--m)}
    </style></head><body><div class="wrap">
    <h1>酷我音乐自动签到 · 面板</h1>
    <div style="color:var(--mut)">仅调用酷我官方接口，无第三方外发 · 下次运行：<span id="next"></span></div>
    <div class="bar">
      <button onclick="api('/api/run','POST')">立即运行全部</button>
      <button class="sec" onclick="location.reload()">刷新</button>
    </div>
    <h2>账号状态</h2><div id="accounts"></div>
    <h2>新增 / 修改账号</h2>
    <div class="card"><div class="grid">
      <input id="appuid" placeholder="appuid">
      <input id="devid" placeholder="devid">
      <input id="q" placeholder="q（登录票据）">
      <input id="phone" placeholder="phone（绑定手机号）">
    </div><button onclick="addAccount()">保存账号</button></div>
    <h2>运行日志（最近 200 行）</h2>
    <pre id="logs"></pre>
    <script>
    const tk='{{ token }}';
    function auth(u){return u.includes('?')?u+'&token='+tk:u+'?token='+tk;}
    async function api(u,m){try{const r=await fetch(auth(u),{method:m});
      const j=await r.json().catch(()=>({msg:r.statusText}));
      alert((j.detail||j.msg||JSON.stringify(j)).toString());location.reload();
    }catch(e){alert('请求失败:'+e)}}
    async function load(){
      const [s,l]=await Promise.all([fetch(auth('/api/status')).then(r=>r.json()),
        fetch(auth('/api/logs')).then(r=>r.text())]);
      document.getElementById('next').textContent=s.next_run||'-';
      let h='<table><tr><th>手机号</th><th>用户</th><th>状态</th><th>时间</th><th>任务</th></tr>';
      (s.accounts||[]).forEach(a=>{
        const st=a.status==='done'?'ok':(a.status==='skipped'?'skip':'bad');
        const label={done:'已完成',skipped:'今日跳过',login_failed:'登录失败',running:'运行中'}[a.status]||a.status;
        const ts=(a.tasks||[]).map(t=>t.name+(t.ok?'✓':'✗')).join(' ');
        h+=`<tr><td>${a.phone}</td><td>${a.username||'-'}</td>
        <td><span class="tag ${st}">${label}</span></td><td>${a.time||'-'}</td>
        <td class="tasks">${ts||'-'}</td></tr>`;
      });
      h+='</table>';document.getElementById('accounts').innerHTML=h;
      document.getElementById('logs').textContent=l;
    }
    async function addAccount(){
      const b={appuid:appuid.value,devid:devid.value,q:q.value,phone:phone.value};
      if(!b.appuid||!b.devid||!b.q){alert('请填 appuid/devid/q');return;}
      const r=await fetch(auth('/api/accounts'),{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
      alert((await r.json()).msg||'ok');location.reload();
    }
    load();
    </script></div></body></html>
    """

    @app.before_request
    def _auth():
        if request.path.startswith("/api/") and not check_auth():
            from flask import abort
            abort(401)

    @app.route("/")
    def index():
        return render_template_string(DASH, token=request.args.get("token", PW))

    @app.route("/api/status")
    def api_status():
        accs = [HISTORY.get(a.get("phone", "?"), {"phone": a.get("phone", "?")}) for a in ACCOUNTS]
        mode = SETTINGS.get("interval_mode", "daily")
        if mode == "interval":
            nxt = f"每 {SETTINGS.get('interval_minutes',120)} 分钟"
        else:
            nxt = f"每天 {SETTINGS.get('schedule','09:00')}"
        return jsonify({"accounts": accs, "next_run": nxt, "running": run_lock.locked()})

    @app.route("/api/run", methods=["POST"])
    def api_run():
        force = request.args.get("force") == "1" or (request.get_json(silent=True) or {}).get("force")
        threading.Thread(target=lambda: run_all(force=bool(force)), daemon=True).start()
        return jsonify({"msg": "已触发运行" + ("(强制)" if force else "")})

    @app.route("/api/accounts", methods=["GET", "POST", "DELETE"])
    def api_accounts():
        global ACCOUNTS
        if request.method == "GET":
            return jsonify({"accounts": ACCOUNTS})
        if request.method == "POST":
            b = request.get_json(silent=True) or {}
            if not all(k in b for k in ("appuid", "devid", "q")):
                return jsonify({"msg": "缺少 appuid/devid/q"}), 400
            ACCOUNTS.append({"appuid": b["appuid"], "devid": b["devid"],
                             "q": b["q"], "phone": b.get("phone", "?")})
            save_config()
            return jsonify({"msg": "账号已添加"})
        if request.method == "DELETE":
            phone = (request.get_json(silent=True) or {}).get("phone")
            ACCOUNTS = [a for a in ACCOUNTS if a.get("phone") != phone]
            save_config()
            return jsonify({"msg": "账号已删除"})

    @app.route("/api/logs")
    def api_logs():
        try:
            with open(LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()[-200:]
            return "".join(lines)
        except Exception:
            return ""

    return app


# ===================== 入口 =====================
def main():
    import argparse
    p = argparse.ArgumentParser(description="酷我音乐自动签到（去毒·服务器·Web 面板版）")
    p.add_argument("--server", action="store_true", help="启动 Web 面板 + 每日定时调度")
    p.add_argument("--once", action="store_true", help="立即执行一次后退出")
    p.add_argument("--loop", action="store_true", help="常驻，每 2 小时一轮（旧模式）")
    p.add_argument("--force", action="store_true", help="忽略今日去重强制重跑")
    p.add_argument("--host", default=None, help="Web 监听地址（覆盖配置）")
    p.add_argument("--port", type=int, default=None, help="Web 端口（覆盖配置）")
    p.add_argument("--schedule", default=None, help="每天运行时间，如 09:00")
    args = p.parse_args()

    load_config()
    load_history()
    if args.schedule:
        SETTINGS["schedule"] = args.schedule
        SETTINGS["interval_mode"] = "daily"

    if not (args.server or args.once or args.loop):
        args.once = True

    if args.server:
        host = args.host or SETTINGS.get("web_host", "0.0.0.0")
        port = args.port or SETTINGS.get("web_port", 8080)
        log.info("启动 Web 面板：http://%s:%s  (token=%s)", host, port,
                 SETTINGS.get("web_password") or "无")
        t = threading.Thread(target=scheduler_loop, daemon=True)
        t.start()
        app = make_app()
        app.run(host=host, port=port, threaded=True)
    elif args.loop:
        log.info("常驻模式：每 2 小时一轮（按 --force 可忽略去重）")
        while True:
            run_all(force=args.force)
            time.sleep(2 * 3600)
    else:  # --once
        run_all(force=args.force)


if __name__ == "__main__":
    main()
