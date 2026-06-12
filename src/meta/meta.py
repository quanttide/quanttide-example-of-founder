#!/usr/bin/env python3
"""
meta — 编排层

journal 变更后自动触发 think → health → execute 完整链路。

producer: 检测新日志 → 发布消息到 RabbitMQ
consumer: 接收消息 → 单篇 think → 情绪检测 → 增量 execute
"""

import os
import sys
import json
import subprocess
import time
import pika
from pathlib import Path
from datetime import datetime
from openai import OpenAI

EXTRACT_PROMPT = """从以下日记段落中提取结构化认知要素。

输出 JSON：
{{
  "situation": {{
    "time": {{"raw": "时间表述或null", "inferred_date": "推断日期或null"}},
    "location": "地点或null",
    "participants": ["参与者列表"],
    "activity": "活动概括（15字）",
    "mood": {{"raw": "情绪词或null", "valence": -3~3, "arousal": 0~5}}
  }},
  "intentions": [
    {{"type": "goal/motive/plan/commitment", "content": "意图原文"}}
  ],
  "ideas": [
    {{"type": "insight/hypothesis/question/analogy", "content": "想法原文"}}
  ]
}}
纯 JSON。"""

MOOD_PROMPT = """从以下日记内容判断情绪状态。
输出 JSON：{{"mood": "主导情绪", "valence": -3~3, "arousal": 0~5, "needs": ["情绪需求"]}}
纯 JSON。"""

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_QUEUE = "journal.new"


def get_mq_connection():
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600)
    return pika.BlockingConnection(params)


def get_last_processed():
    marker = Path(os.path.dirname(__file__)) / ".last_journal"
    if marker.exists():
        return marker.read_text().strip()
    return ""


def save_last_processed(hash_val):
    Path(os.path.dirname(__file__) / ".last_journal").write_text(hash_val)


def get_latest_journal(repo_path):
    result = subprocess.run(
        ["git", "-C", repo_path, "-c", "core.quotepath=false",
         "log", "--max-count=20", "--name-only", "--format=%H"],
        capture_output=True, text=True
    )
    journal_files = []
    current_hash = None
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if len(line) == 40:
            current_hash = line
        elif line.endswith(".md") and "journal" in line and current_hash:
            journal_files.append((current_hash, line))

    if not journal_files:
        return None, None
    latest_hash, latest_file = journal_files[0]
    r = subprocess.run(
        ["git", "-C", repo_path, "show", f"HEAD:{latest_file}"],
        capture_output=True, text=True, timeout=5
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None, None
    return latest_hash, r.stdout[:3000]


def process(content, model="deepseek-chat"):
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com"
    )
    r1 = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": EXTRACT_PROMPT},
                  {"role": "user", "content": content}],
        response_format={"type": "json_object"},
        temperature=0.1, max_tokens=1024,
    )
    cognition = json.loads(r1.choices[0].message.content.strip())
    r2 = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": MOOD_PROMPT},
                  {"role": "user", "content": content}],
        response_format={"type": "json_object"},
        temperature=0.1, max_tokens=256,
    )
    mood = json.loads(r2.choices[0].message.content.strip())
    return cognition, mood


# ── producer ──

def publish(repo_path):
    latest_hash, content = get_latest_journal(repo_path)
    if not latest_hash or not content:
        print("未找到 journal 文件"); return

    last = get_last_processed()
    if latest_hash == last:
        print("无新日志"); return

    message = json.dumps({"hash": latest_hash, "content": content[:2000]})
    conn = get_mq_connection()
    channel = conn.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=RABBITMQ_QUEUE,
        body=message.encode(),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conn.close()
    print(f"已发布: {latest_hash[:8]}")


# ── consumer ──

def callback(ch, method, properties, body, model="deepseek-chat"):
    msg = json.loads(body.decode())
    content = msg.get("content", "")
    hash_val = msg.get("hash", "")
    print(f"\n收到: {hash_val[:8]}")

    cognition, mood = process(content, model)
    mood_text = f"{mood.get('mood','?')} (愉悦度 {mood.get('valence',0)})"
    print(f"情绪: {mood_text}")

    plans = [i.get("content","") for i in cognition.get("intentions",[])
             if i.get("type") in ("plan","commitment")]
    if plans:
        print(f"新计划 ({len(plans)} 条):")
        for p in plans[:5]:
            print(f"  [ ] {p}")
    else:
        print("无可执行计划")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def consume(model="deepseek-chat"):
    conn = get_mq_connection()
    channel = conn.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(
        queue=RABBITMQ_QUEUE,
        on_message_callback=lambda ch, method, properties, body: callback(ch, method, properties, body, model)
    )
    print(f"监听 {RABBITMQ_QUEUE} (Ctrl+C 退出)")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        conn.close()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-path", default=os.path.join(os.path.dirname(__file__),
                        "../../../../docs/memory"))
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--publish", action="store_true", help="检测并发布新日志")
    parser.add_argument("--consume", action="store_true", help="启动消费者")
    args = parser.parse_args()

    if args.publish:
        publish(args.memory_path)
    elif args.consume:
        consume(args.model)
    else:
        print("请指定 --publish 或 --consume")


if __name__ == "__main__":
    main()
