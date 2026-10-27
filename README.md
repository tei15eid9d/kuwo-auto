# 酷我音乐自动任务 · 服务器 / Web 面板版

本工具用**手机号 + 密码**直接登录酷我音乐，自动完成每日签到、任务与收益统计。
代码全部来自开源脚本库（345yun.cn），**仅调用酷我官方接口**，无任何第三方上报、无私有后台。

## 功能
- **手机号 + 密码登录**：无需抓包，填手机号密码即可（内部走酷我官方 `login_kw` 接口）
- 自动任务：签到、听歌、开宝箱、看广告、整点领、抽奖、免费听歌等
- **开宝箱自动补领**：开宝箱约每 10 分钟冷却一次，后台会按倒计时自动领下一个；整点那一轮顺带补领整点金币/时段宝箱（轮询间隔可用 `settings.box_interval` 调整，单位秒，默认 600）
- **多账号**：`config.json` 或环境变量 `kwyy`（格式 `手机号#密码`，多账号用 `&` 分隔）
- **Web 面板**：浏览器里看状态、手动运行、增删账号、看日志
- **内置定时**：默认每天 09:00 自动运行（可在 `config.json` 改时间）
- 本地收益统计（当日累计金币写在本机 `daily_gold_data.json`）

## 接口参数（重要）
所有领金币接口的调用参数（`apiversion` / `dynamicVer` / `q36` / `version` / `source` / `prod` / `adApiversion`）已**集中提取为 `kuwo_auto.py` 顶部的命名常量**，对齐官方 App 最新抓包版本（`12.2.2.0`）：

```python
APP_VERSION = '12.2.2.0'          # version
APP_SOURCE = 'kwplayer_ar_12.2.2.0_40.apk'
APP_PROD   = 'kwplayer_ar_12.2.2.0'
API_VERSION = '52'                # apiversion
DYNAMIC_VER = '52'                # dynamicVer
AD_API_VERSION = '59'             # adApiversion
Q36 = '65561028073f439f925c75fd10001541a90b'
APIV_LIST = '11'                  # 列表类接口 apiv
APIV_ACTION = '10'                # 动作类(newDoListen) apiv
```

若日后接口返回异常（如大面积提示过期/版本过低），优先重新抓包核对这几个值，**改顶部常量即可全局生效**，无需逐函数修改。
覆盖接口：`newDoListen`（签到/整点/听歌/累计奖励/友情打卡/广告）、`newDoListen` 分支 `everydaymusic/doListen`、`newBoxFinish`（开宝箱）、`newBoxList`/`boxRenew`（活动宝箱/时段宝箱）、`newUserSignList`（任务列表）、`loterry/getLucky`（抽奖）。

## 安装
```bash
pip install -r requirements.txt
cp config.example.json config.json   # 填入你的手机号与密码
```

## 配置（config.json）
```json
{
  "settings": { "schedule": "09:00", "box_interval": 600, "web_host": "0.0.0.0", "web_port": 8080, "web_password": "", "push": { "type": "none" } },
  "accounts": [ { "phone": "13800000000", "password": "你的酷我密码" } ]
}
```
账号也支持环境变量：`export kwyy="13800000000#密码&13900000000#密码2"`

## 运行
```bash
# 1) Web 面板 + 每日定时（推荐服务器）
python3 kuwo_auto.py --server
#   浏览器打开 http://服务器IP:8080

# 2) 单次执行（适合配合系统 cron）
python3 kuwo_auto.py --once

# 3) 常驻每 2 小时一轮
python3 kuwo_auto.py --loop
```

## 安全建议
- 用**不重要小号**跑，别绑主账号手机号；不要投入真实资金。
- Web 面板设置 `settings.web_password`，并放在反代 / 内网后访问。
- 自查：运行时用 `tcpdump -n 'host not *.kuwo.cn'` 监听，确认除酷我官方域名外无任何出站连接。

## 部署到服务器（Linux）
```bash
# 上传本目录到 /opt/kuwo/，安装依赖后：
nohup python3 /opt/kuwo/kuwo_auto.py --server > /opt/kuwo/run.log 2>&1 &

# 或用 systemd（/etc/systemd/system/kuwo.service）
#   [Service]
#   WorkingDirectory=/opt/kuwo
#   ExecStart=/usr/bin/python3 /opt/kuwo/kuwo_auto.py --server
#   Restart=always
```

> 仅供学习与技术研究，请在法律法规允许范围内使用，并自行承担相关风险。
