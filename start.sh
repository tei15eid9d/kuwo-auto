#!/usr/bin/env bash
# 酷我自动签到 · 一键启动脚本（Linux 服务器）
set -e
cd "$(dirname "$0")"

echo "==> 安装依赖"
pip3 install -r requirements.txt

if [ ! -f config.json ]; then
  echo "==> 未找到 config.json，已复制模板，请编辑后重跑本脚本"
  cp config.example.json config.json
  echo "    编辑命令: vi config.json   (填入 appuid / devid / q / phone)"
  exit 0
fi

echo "==> 启动 Web 面板 + 每日定时 (默认 09:00)"
echo "    访问: http://<本机IP>:8080"
python3 kuwo_auto.py --server
