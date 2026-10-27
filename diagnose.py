#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
酷我任务诊断工具
================
用途：拉取酷我官方任务列表的真实返回，确认「到底有哪些任务是真实存在的」，
     以及每个任务的准确参数(taskType / goldNum / subTitle 等)。

隐私说明：输出会自动把手机号、loginUid、loginSid、appUid 打码，
          可安全地把 diagnose_result.json 或终端输出发给别人分析。

用法：
    方式1(推荐)  不改配置，直接用环境变量：
        kwyy="手机号#密码" python3 diagnose.py

    方式2  和主程序共用 config.json：
        python3 diagnose.py
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kuwo_auto as k

OUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'diagnose_result.json')


def mask(v, keep=4):
    """敏感值打码，只留前 keep 位"""
    if v is None:
        return None
    s = str(v)
    if len(s) <= keep:
        return '*' * len(s)
    return s[:keep] + '*' * (len(s) - keep)


def main():
    print('=' * 66)
    print('酷我音乐 · 任务列表诊断')
    print('=' * 66)

    # 取账号：环境变量优先，其次 config.json
    accounts = k.get_accounts()
    if not accounts:
        print('\n❌ 未读取到账号')
        print('   请用: kwyy="手机号#密码" python3 diagnose.py')
        print('   或先配置同目录下的 config.json')
        return

    acc = accounts[0]
    phone = acc['phone']
    print('\n📱 账号: ' + mask(phone) + ' (共 ' + str(len(accounts)) + ' 个, 仅诊断第 1 个)')

    print('\n[1/3] 登录中...')
    result = k.login(phone, acc['password'])
    if not result:
        print('❌ 登录失败 —— 请确认手机号和密码是否正确')
        return
    loginUid, loginSid, username, appUid, encrypted_dev_id = result
    print('✅ 登录成功')
    print('   loginUid  = ' + mask(loginUid))
    print('   appUid    = ' + mask(appUid))

    print('\n[2/3] 查询账户金币...')
    asset = k.query_user_asset(loginUid, loginSid, appUid, verbose=False)
    print('   ' + (('✅ 剩余金币: ' + str(asset.get('score'))) if asset.get('success') else '❌ 查询失败'))

    print('\n[3/3] 拉取官方任务列表 (这是诊断的核心)...')
    info = k.fetch_sign_list(loginUid, loginSid, appUid, tag='任务列表')
    if not info.get('success'):
        print('❌ 任务列表拉取失败')
        return

    payload = info.get('data', {}) or {}
    print('✅ 拉取成功\n')

    # 顶层字段概览
    print('--- 顶层字段 ---')
    top = {kk: (mask(vv) if kk in ('loginUid', 'loginSid', 'appUid', 'devId') else vv)
           for kk, vv in payload.items() if kk != 'dataList'}
    for kk in sorted(top):
        print('   %-18s %s' % (kk, str(top[kk])[:70]))

    data_list = payload.get('dataList') or []
    print('\n--- 任务清单: 共 %d 个 ---' % len(data_list))

    tasks = []
    for i, item in enumerate(data_list, 1):
        if not isinstance(item, dict):
            continue
        title = str(item.get('title') or '')
        task_type = str(item.get('taskType') or '')
        sub = str(item.get('subTitle') or '')
        gold = item.get('goldNum')
        task = {
            'idx': i,
            'title': title,
            'taskType': task_type,
            'subTitle': sub,
            'goldNum': gold,
            'extraGoldNum': item.get('extraGoldNum'),
            'isFinished': item.get('isFinished'),
            'isSign': item.get('isSign'),
            'hasListenList': isinstance(item.get('listenList'), list),
            'listenListLen': len(item.get('listenList') or []),
            'allKeys': sorted(item.keys()),
        }
        tasks.append(task)
        flag = '✅' if str(item.get('isFinished')) in ('1', 'True', 'true') else '  '
        print('  %s[%2d] %-22s type=%-16s gold=%-6s extra=%-5s listen=%d' % (
            flag, i, title[:22], task_type[:16], str(gold),
            str(item.get('extraGoldNum')), task['listenListLen']))
        if sub:
            print('        subTitle: ' + sub[:60])

    # 统计：到底有哪些 taskType
    print('\n--- 任务类型汇总 ---')
    seen = {}
    for t in tasks:
        seen[t['taskType']] = seen.get(t['taskType'], 0) + 1
    for tp, cnt in sorted(seen.items(), key=lambda x: -x[1]):
        print('   %-20s x%d' % (tp or '(空)', cnt))

    # 判定闲鱼卖家所谓「臆造任务」是否真的存在于官方列表
    print('\n--- 关键判定: 争议任务是否存在于官方列表 ---')
    joined = json.dumps(data_list, ensure_ascii=False)
    checks = [
        ('哒哒广告', ['哒哒', 'videofix', '20130401']),
        ('惊喜广告', ['surprise', '惊喜', '20130702']),
        ('友情打卡', ['friendship', '打卡', '携程', '京东金融', '快手']),
        ('整点领金币', ['clock', '打卡领金币', '整点']),
    ]
    for name, kws in checks:
        hit = [kw for kw in kws if kw in joined]
        print('   %-12s %s' % (name, ('命中关键词: ' + ', '.join(hit)) if hit else '未出现 ❌'))

    # 落盘
    out = {
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'note': '敏感字段已打码，可安全外发',
        'asset': asset,
        'task_count': len(tasks),
        'tasks': tasks,
        'raw_dataList_keys': sorted(payload.keys()),
    }
    try:
        with open(OUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('\n💾 完整结果已保存: ' + OUT_FILE)
        print('   (手机号/凭证均已打码，可直接发给他人分析)')
    except Exception as e:
        print('⚠️  保存失败: ' + str(e))

    print('\n' + '=' * 66)
    print('诊断结束 —— 把上面的输出或 diagnose_result.json 发来即可分析')
    print('=' * 66)


if __name__ == '__main__':
    main()
