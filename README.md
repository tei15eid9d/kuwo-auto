# 酷我音乐自动签到 · 去毒服务器版

从闲鱼购买的加密 EXE 中还原出酷我官方任务逻辑，**移除所有第三方上报（原 EXE 把账号发往私有后台）**，并补齐原软件功能：多账号、内置定时任务、Web 面板。

## 已还原功能（对照原 EXE）
- 登录 / 每日签到 / 创意视频·听歌 / 每日音乐 / 开宝箱 / 抽奖 / 免费听歌开关
- 多账号、每日去重、随机延时防风控、失败重试
- **内置定时任务**：默认每天 09:00（可改 `every2h` 间隔模式）
- **Web 面板**：仪表盘状态 / 立即运行 / 网页增删账号 / 运行日志 / 可选推送
- ❌ 已剔除：向第三方平台上报账号、自动提现（请到官方 App 操作）

## 安装
```bash
pip install -r requirements.txt
cp config.example.json config.json   # 填入你的 appuid / devid / q / phone
```

## 运行
```bash
# 1) 启动 Web 面板 + 每日定时（推荐服务器用）
python3 kuwo_auto.py --server
#   浏览器打开 http://服务器IP:8080

# 2) 单次执行（配合系统 cron 最稳）
python3 kuwo_auto.py --once

# 3) 常驻每 2 小时一轮（旧模式）
python3 kuwo_auto.py --loop

# 强制重跑（忽略今日去重）
python3 kuwo_auto.py --once --force
```

## 参数获取
安卓酷我音乐 App 内用抓包工具（HttpCanary / Charles）抓取
`ar.i.kuwo.cn/US_NEW/kuwo/login_kw` 请求，取其中的 `appuid` / `devid` / `q` / `phone`。

## 安全建议
- 用**不重要小号**跑，别绑主账号手机号；仅作自用，风险自担。
- Web 面板务必设置 `settings.web_password`，并放在反代 / 内网后（默认 0.0.0.0 仅方便局域网）。
- 推送（push）仅发往你自己的 webhook / TG / Bark 地址，不内置任何第三方 SaaS。
- 自查：服务器跑脚本时用 `tcpdump -n 'host not *.kuwo.cn'` 监听，确认除酷我官方域名外无任何出站连接。

## 部署到服务器（Linux 示例）
```bash
# 1. 上传 kuwo_auto.py / config.json / requirements.txt 到 /opt/kuwo/
# 2. 安装依赖
pip3 install -r /opt/kuwo/requirements.txt
# 3. 用 systemd 守护（示例 /etc/systemd/system/kuwo.service）
#    [Service]
#    WorkingDirectory=/opt/kuwo
#    ExecStart=/usr/bin/python3 /opt/kuwo/kuwo_auto.py --server
#    Restart=always
# 4. 或直接 nohup
nohup python3 /opt/kuwo/kuwo_auto.py --server > /opt/kuwo/run.log 2>&1 &
```
