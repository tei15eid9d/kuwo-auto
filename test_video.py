#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单次验证【14】视频红包 / 惊喜广告 能否真的领到金币。

用法:
    kwyy="手机号#密码" python3 test_video.py
或（已配置 config.json 时）:
    python3 test_video.py

只做四件事：登录 → 查金币 → 各领 1 次 → 再查金币。
不会连刷，方便你直接去酷我音乐 App 核对金币是否真的增加。
"""

import sys

import kuwo_auto as kw


def main():
    accounts = kw.get_accounts()
    if not accounts:
        print('❌ 未读取到账号。请配置 config.json 或用 kwyy 环境变量')
        return 1

    for acc in accounts:
        phone = str(acc.get('phone') or '')
        shown = phone[:3] + '****' + phone[-4:] if len(phone) > 7 else phone
        print('=' * 58)
        print('账号: %s' % shown)

        result = kw.login(phone, acc.get('password'))
        if not result:
            print('❌ 登录失败，跳过')
            continue
        loginUid, loginSid, username, appUid, encrypted_dev_id = result

        before = kw.query_user_asset(loginUid, loginSid, appUid, verbose=False)
        gold_before = before.get('score') if before.get('success') else None
        print('领取前金币: %s' % gold_before)

        # 1) 先问官方：这个账号到底有没有视频类任务
        exists = {}
        info = kw.fetch_sign_list(loginUid, loginSid, appUid, tag='任务列表')
        if info.get('success'):
            for item in (info.get('data') or {}).get('dataList') or []:
                if not isinstance(item, dict):
                    continue
                task_type = str(item.get('taskType') or '')
                if task_type in ('videoadver', 'surprise'):
                    exists[task_type] = item

        print('\n--- 官方任务列表中的视频类任务 ---')
        for kind, label in [('videoadver', '视频红包'), ('surprise', '惊喜广告')]:
            row = exists.get(kind)
            if not row:
                print('  %-6s 不存在 → 脚本会自动跳过, 不臆造' % label)
            else:
                done = row.get('isCompleted') is True or row.get('isReceived') is True
                print('  %-6s 存在 | 金币 %s | 已完成: %s' % (label, row.get('goldNum'), done))

        if not exists:
            print('\n结论: 该账号没有视频红包/惊喜广告任务, 【14】不会执行任何请求')
            continue

        # 2) 各领 1 次，验证能否真的入账
        print('\n--- 各尝试领取 1 次（不连刷）---')
        for kind, label in [('videoadver', '视频红包'), ('surprise', '惊喜广告')]:
            row = exists.get(kind)
            if not row:
                continue
            if row.get('isCompleted') is True or row.get('isReceived') is True:
                print('  %s: 今日已完成, 跳过' % label)
                continue
            # 实测: 必须提交固定金币数(视频红包 58 / 惊喜广告 68),
            # 用任务列表里的 goldNum(累计总额)会被判「金币奖励区间校验失败」。
            gold = kw.VIDEO_AD_GOLD if kind == 'videoadver' else kw.SURPRISE_AD_GOLD
            r = kw.run_everyday_do_listen_task(
                label, loginUid, loginSid, appUid,
                {'from': kind, 'goldNum': str(gold)}, verbose=False)
            desc = str(r.get('description') or '')
            if r.get('success') and not r.get('done'):
                # 成功时接口返回 obtain=0, 实际按 gold 入账
                print('  ✅ %s: +%s 金币 (%s)' % (label, gold, desc))
            else:
                print('  ⏭️ %s: %s' % (label, desc or '领取失败'))

        # 3) 再查一次金币，看是否真的入账
        after = kw.query_user_asset(loginUid, loginSid, appUid, verbose=False)
        gold_after = after.get('score') if after.get('success') else None
        print('\n领取后金币: %s' % gold_after)
        if gold_before is not None and gold_after is not None:
            print('实际变化  : %+d' % (gold_after - gold_before))
        print('\n请去酷我音乐 App 核对金币是否真的增加（接口有数秒延迟，稍等再刷新）')

    return 0


if __name__ == '__main__':
    sys.exit(main())
