#!/usr/bin/env python3
"""
meta — 消息层

模块间通过 RabbitMQ 通信，不共享文件路径。

队列：
  journal.new      → 新 journal 内容（meta 发布，think 消费）
  cognition.ready  → 结构化认知数据（think 发布，execute/health 消费）
"""

import os
import sys
import json
import pika
from pathlib import Path

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")

QUEUES = ["journal.new", "cognition.ready"]


def connect():
    return pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=600))


def publish(queue, data):
    conn = connect()
    ch = conn.channel()
    ch.queue_declare(queue=queue, durable=True)
    ch.basic_publish(
        exchange="", routing_key=queue,
        body=json.dumps(data).encode(),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    conn.close()


def declare_all():
    conn = connect()
    ch = conn.channel()
    for q in QUEUES:
        ch.queue_declare(queue=q, durable=True)
    conn.close()


# ── 模块入口 ──

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", help="发布消息到指定队列")
    parser.add_argument("--data", help="消息内容（JSON）")
    parser.add_argument("--declare", action="store_true", help="声明所有队列")
    args = parser.parse_args()

    if args.declare:
        declare_all()
        print("队列已声明:", QUEUES)
    elif args.publish and args.data:
        publish(args.publish, json.loads(args.data))
        print(f"已发布到 {args.publish}")
    else:
        parser.print_help()
