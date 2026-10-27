#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送自检工具
============
用途：一步步检查为什么"没收到推送"，最后 optionally 发一条真实测试消息。

用法：
    python3 push_test.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuwo_auto as k


def mask(v, keep=6):
    if not v:
        return '(空)'
    s = str(v)
    if len(s) <= keep:
        return s[0] + '*' * max(0, len(s) - 1)
    return s[:keep] + '*' * (len(s) - keep)


def main():
    print('=' * 62)
    print('WxPusher 推送自检')
    print('=' * 62)

    cfg = k.load_config()
    settings = cfg.get('settings') or {}
    push = settings.get('push') or {}

    ok = True

    # 1) 推送类型
    ptype = os.getenv('PUSH_TYPE') or push.get('type') or 'none'
    print('\n[1/5] 推送类型 (settings.push.type)')
    print('      当前值: %s' % ptype)
    if str(ptype).strip().lower() != 'wxpusher':
        print('      ❌ 不是 wxpusher → 脚本不会推送任何东西')
        print('         请改成: "push": { "type": "wxpusher", "wxpusher": { ... } }')
        ok = False
    else:
        print('      ✅ wxpusher')

    # 2) appToken
    wx = push.get('wxpusher') or {}
    token = (os.getenv('WXPUSHER_APP_TOKEN') or wx.get('app_token') or '').strip()
    print('\n[2/5] appToken')
    print('      当前值: %s' % mask(token))
    if not token:
        print('      ❌ 未配置 appToken')
        ok = False
    else:
        print('      ✅ 已配置')

    # 3) 推送目标
    topics = k._split_target_ids(os.getenv('WXPUSHER_TOPIC_IDS') or wx.get('topic_ids'))
    uids = k._split_target_ids(os.getenv('WXPUSHER_UIDS') or wx.get('uids'))
    print('\n[3/5] 推送目标')
    print('      主题 topic_ids: %s' % (topics if topics else '(空)'))
    print('      用户 uids     : %s' % (uids if uids else '(空)'))
    if not topics and not uids:
        print('      ❌ 没有任何推送目标')
        ok = False
    else:
        print('      ✅ 已配置')

    # 4) 推送时间窗口 —— 最常见的"没推送"原因
    print('\n[4/5] 推送时间窗口')
    print('      规则: 仅 12:00-12:15 与 23:55-23:59 推送')
    print('           或用 FORCE_PUSH=1 强制推送')
    print('      当前时间: %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    in_window = k.should_push()
    print('      当前是否在窗口内: %s' % ('✅ 是' if in_window else '❌ 否 → 这是没收到推送的最常见原因'))
    if os.getenv('FORCE_PUSH') == '1':
        print('      (检测到 FORCE_PUSH=1, 已强制开启)')

    # 5) 立即实测
    print('\n[5/5] 实测推送')
    if not ok:
        print('      ⏭️  前面配置有缺失, 先修好上面的项再测')
        print('         修好后重跑本工具即可发送测试消息')
        return

    print('      准备发送测试消息...')
    ok_send = k.push_notify(
        '酷我音乐 · 推送自检',
        '【推送自检】配置正常 ✅\n\n'
        '收到这条说明 WxPusher 已接通。\n'
        'appToken: %s\n'
        '目标: topic=%s uid=%s\n'
        '当前窗口状态: %s\n\n'
        '自检时间：%s'
        % (mask(token), topics or '无', [mask(u, 8) for u in uids] or '无',
           '窗口内' if in_window else '窗口外(仅因本次手动触发)',
           time.strftime('%Y-%m-%d %H:%M:%S'))
    )
    print('\n      结果: %s' % ('✅ 推送成功, 请查看微信' if ok_send else '❌ 推送失败, 看上面的报错'))

    print('\n' + '=' * 62)
    if not in_window and ok:
        print('提示: 现在是推送窗口之外, 日常要靠以下方式收汇总')
        print('  - 等 12:00-12:15 或 23:55-23:59 的自动推送')
        print('  - 或用 FORCE_PUSH=1 python3 kuwo_auto.py --once 强制推一次')
    print('=' * 62)


if __name__ == '__main__':
    main()
