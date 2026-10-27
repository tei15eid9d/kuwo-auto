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

## 【5】看视频拆红包 —— 为什么默认跳过，以及怎样才真能领

这是唯一**默认关闭**的任务（注意：不是漏做，是做不了）。实测结论与根因：

| 检查项 | 实测结果 |
|---|---|
| `ad.tencentmusic.com` 可达性 | IPv4 `101.226.142.110` / IPv6 均有，**TCP 443 可连通** |
| TLS 握手 | ✅ 成功（腾讯深圳签发 `*.stream.qqmusic.qq.com`，DigiCert，有效期至 2027-03-02） |
| HTTP 请求响应 | ❌ **全部超时**——对任何非 SDK 请求一律**静默挂起不返回**（4 组参数探测均超时） |

即网关采用私有二进制协议（protobuf + SDK 签名），不是普通 HTTP 接口。

**根因**：该任务要过服务端「金币奖励校验」，必须带 `verifyStr` / `token`，其格式为
`1,2,20130101,<loginUid>,<576 字符凭证>`。这段凭证由腾讯音乐广告 SDK 从
`ad.tencentmusic.com/maproxy/getPbCompressAd` 预加载缓存中颁发，**绑定时间戳与设备**。
卖家源码注释也承认：「签名绑定时间，构造不出也重放不了」，因此他自己的软件同样默认跳过此任务。

不传凭证时每轮必报错`金币奖励校验失败`，硬刷 30 轮只是浪费请求、徒增风控概率。

### 若你仍想领，三条可行路径

1. **抓包取证一次，填凭证用（可半自动）**
   手机装抓包工具（安卓 HttpCanary / iOS Stream），进酷我「看视频拆红包」完整看一次广告，
   把上报到 `integralapi.kuwo.cn/.../newDoListen` 的请求里 `verifyStr` 的完整值复制出来，
   填到下面配置并把 `video_enabled` 设为 `true`。**注意凭证有时效**，过期需重抓。
2. **在能跑真实 App 的环境里自动化（唯一真正全自动）**
   服务器跑安卓容器（如 ReDroid / docker-android）+ Appium / uiautomator 驱动酷我 App，
   让 App 自己走完广告流程拿到凭证。代价是部署重、占用高，且存在平台风控风险。
3. **直接放弃（推荐）**
   该任务单位收益虽高，但需要逆向私有协议 + 维护时效性凭证，投入产出比低。

### 配置（开启后方可运行）

```json
{
  "settings": {
    "video_enabled": true,
    "video_verify": "1,2,20130101,<你的loginUid>,<576字符凭证>",
    "video_rounds": 5
  }
}
```

等价于环境变量：`KUWO_VIDEO=1`、`KWYY_VIDEO_VERIFY=<凭证>`、`KUWO_VIDEO_LOOP=5`。
`video_rounds` 上限 30，**建议保持个位数**，避免短时间大量请求触发风控。

> 仅供学习与技术研究，请在法律法规允许范围内使用，并自行承担相关风险。
