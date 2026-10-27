# 酷我音乐自动任务 · 服务器 / Web 面板版

本工具用**手机号 + 密码**直接登录酷我音乐，自动完成每日签到、任务与收益统计。
代码全部来自开源脚本库（345yun.cn），**仅调用酷我官方接口**，无任何第三方上报、无私有后台。

## 功能
- **手机号 + 密码登录**：无需抓包，填手机号密码即可（内部走酷我官方 `login_kw` 接口）
- 自动任务（**均为实测可用**，无效任务已删除，详见文末「已移除的任务」）：

  | 编号 | 任务 | 编号 | 任务 |
  |---|---|---|---|
  | 【1】 | 资产查询 | 【6】 | 整点领金币 |
  | 【2】 | 签到听歌任务链 | 【8】 | 免费抽奖 |
  | 【3】 | 累计奖励任务 | 【9】 | 广告抽奖（9 轮） |
  | 【4】 | 开宝箱 | 【11】 | 免费听歌时长任务 |
  | 【4.1】 | 活动宝箱 | 【12】 | 友情打卡（携程/京东金融/快手等） |
  | 【4.2】 | 时段宝箱补领 | | |
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

## 消息推送（WxPusher / PushPlus）

每日金币统计会按**时间窗口**（12:00–12:15、23:55–23:59）自动推送，也可以用
`FORCE_PUSH=1` 强制推送（适合测试）。

### WxPusher（推荐，微信直接收）

```json
{
  "settings": {
    "push": {
      "type": "wxpusher",
      "wxpusher": {
        "app_token": "AT_你的应用Token",
        "topic_ids": [48125]
      }
    }
  }
}
```

也可用环境变量：`PUSH_TYPE=wxpusher`、`WXPUSHER_APP_TOKEN=AT_xxx`、`WXPUSHER_TOPIC_IDS=48125`。

> ⚠️ **最常见的坑：appToken 和主题必须属于同一个应用。**
> 主题（Topic）是隶属于应用的，用 A 应用的 token 去推 B 应用的主题，服务端会返回：
> `code=1001 你没有权限给topic【xxx】发送消息`
>
> 排查方法：到 [WxPusher 后台](https://wxpusher.zjiecode.com/admin/) 打开**你自己的应用**，
> 在「主题管理」里复制该应用名下的主题 ID，和这个应用的 appToken 配套使用。
>
> 如果你只有主题 ID 却没有它的 token，最省事的办法是改用**极简推送（SPT）**：
> 微信扫码拿 SPT，消息只发给你自己，无需创建应用、也不用配对 token 与 topic。

### PushPlus

```json
{ "settings": { "push": { "type": "pushplus" } } }
```
配合环境变量 `PUSH_PLUS_TOKEN=你的token`。

### 关闭推送

```json
{ "settings": { "push": { "type": "none" } } }
```

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

## 已移除的任务（为什么脚本里没有它们）

本着「只保留真实可用」的原则，以下任务已从代码里**彻底删除**（不再占流程、不再发无效请求）：

| 原编号 | 任务 | 移除原因 |
|---|---|---|
| 【5】 | 看视频拆红包 | 需广告 SDK 凭证 `verifyStr`，见下方实测 |
| 【7】 | 哒哒广告 | 官方任务列表中不存在，属臆造（且原本就是从未被调用的死代码） |
| 【10】 | 观看惊喜广告 | 官方任务列表中不存在，`from=surprise` 从未出现在抓包中 |

### 看视频拆红包为什么做不了（实测依据）

该任务要过服务端「金币奖励校验」，必须带 `verifyStr` / `token`，格式：
`1,2,20130101,<loginUid>,<576 字符凭证>`。凭证由腾讯音乐广告 SDK 从
`ad.tencentmusic.com/maproxy/getPbCompressAd` 颁发，**绑定时间戳与设备**。

| 检查项 | 实测结果 |
|---|---|
| `ad.tencentmusic.com` 可达性 | IPv4 `101.226.142.110` / IPv6 均有，**TCP 443 可连通** |
| TLS 握手 | ✅ 成功（腾讯深圳签发 `*.stream.qqmusic.qq.com`，DigiCert，有效期至 2027-03-02） |
| HTTP 请求响应 | ❌ **全部超时**——对任何非 SDK 请求一律**静默挂起不返回**（4 组参数探测均超时） |
| 能否在本机跑安卓 App 取凭证 | ❌ 沙箱无 `/dev/kvm`、CPU 虚拟化标记为 0，安卓容器起不来 |

即凭证只能由**真机 App 内的 SDK 现场生成**，纯脚本无法构造也难以重放。
若将来用 HttpCanary 抓到有效凭证，可从 git 历史（`bcb8c98` 及之前）恢复
`open_guanggao()` 与 `video_verify` 配置重新启用。

### 想确认哪些任务真实存在？

用同目录的 `diagnose.py` 拉取官方任务列表验证（不依赖任何人的经验判断，敏感信息自动打码）：

```bash
kwyy="手机号#密码" python3 diagnose.py
```

> 仅供学习与技术研究，请在法律法规允许范围内使用，并自行承担相关风险。
