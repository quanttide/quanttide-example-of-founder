#!/usr/bin/env python3
"""
故事可视化渲染：story.yaml → index.html

用法:
  ./render.py story.yaml -o index.html
"""

import argparse
import sys
from pathlib import Path
import yaml

HTML_TPL = """<!DOCTYPE html>
<meta charset="utf-8">
<title>{title}</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #222; }}
h1 {{ font-size: 1.4rem; font-weight: 600; margin-bottom: .25rem; }}
.source {{ font-size: .8rem; color: #888; margin-bottom: 1.5rem; }}

.row {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; }}
.col {{ flex: 1; min-width: 0; }}
.col-header {{ font-size: .75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #aaa; margin-bottom: .4rem; }}
.card {{ background: #f9f9f9; border-radius: 6px; padding: .75rem; margin-bottom: .5rem; }}
.card:last-child {{ margin-bottom: 0; }}
h3 {{ font-size: .9rem; font-weight: 600; margin: 0 0 .4rem; }}
p {{ font-size: .85rem; line-height: 1.5; margin: .2rem 0; }}
.tag {{ display: inline-block; font-size: .75rem; padding: .1rem .45rem; border-radius: 3px; margin: .1rem; }}
.tag-green {{ background: #e8f5e9; color: #2e7d32; }}
.tag-blue {{ background: #e3f2fd; color: #1565c0; }}
.tag-orange {{ background: #fff3e0; color: #e65100; }}
.tag-purple {{ background: #f3e5f5; color: #7b1fa2; }}
.tag-red {{ background: #fbe9e7; color: #bf360c; }}
.tag-gray {{ background: #eceff1; color: #546e7a; }}
.arrow {{ color: #ccc; margin: 0 .3rem; }}
.sub {{ font-size: .8rem; color: #666; }}
</style>

<h1>{title}</h1>
<p class="source">来源：{source}</p>

{rows}
"""


def tag(text: str, css_class: str) -> str:
    return f'<span class="tag tag-{css_class}">{text}</span>'


def row(left_header: str, left_cards: list[str],
        right_header: str, right_cards: list[str]) -> str:
    def col(header, cards):
        inner = "\n".join(f'<div class="card">{c}</div>' for c in cards)
        return f'<div class="col"><p class="col-header">{header}</p>\n{inner}\n</div>'
    return f'<div class="row">{col(left_header, left_cards)}{col(right_header, right_cards)}</div>'


def render_characters(data: dict):
    chars = data.get("characters", [])
    left = []
    right = []
    for c in chars:
        name = c.get("name", "")
        role = c.get("role", "")
        personality = c.get("personality", "")
        motivation = c.get("motivation", "")
        arc = c.get("arc", "")

        left.append(
            f'<h3>{name}</h3>\n'
            f'<p>{tag(role, "green")} {tag(personality, "blue")}</p>\n'
            f'<p class="sub"><strong>动机：</strong>{motivation}</p>'
        )
        right.append(
            f'<h3>{name}</h3>\n'
            f'<p>{tag("起点", "orange")} <span class="arrow">→</span> {tag("终点", "green")}</p>\n'
            f'<p class="sub">{arc}</p>'
        )
    return row("直取 · 人物", left, "分析 · 人物弧光", right)


def render_setting(data: dict):
    settings = data.get("setting", [])
    eg = data.get("emotional_geography", [])

    if not settings:
        return ""

    left = []
    for s in settings:
        loc = s.get("location", "")
        atm = s.get("atmosphere", "")
        sig = s.get("significance", "")
        left.append(
            f'<h3>{loc}</h3>\n'
            f'<p>{tag(atm, "orange")}</p>\n'
            f'<p class="sub">{sig}</p>'
        )

    right_entries = []
    for e in eg:
        place = e.get("place", "")
        emotion = e.get("emotion", "")
        memory = e.get("memory", "")
        right_entries.append(
            f'<p><strong>{place}</strong> <span class="arrow">→</span> {emotion}</p>\n'
            f'<p class="sub">{memory}</p>'
        )
    right = [f'<hr style="border:none;border-top:1px solid #e0e0e0;margin:.4rem 0">'.join(right_entries)] if right_entries else []

    return row("直取 · 场景", left, "分析 · 情感地理", right)


def render_timeline(data: dict):
    tl = data.get("timeline", [])
    tensions = data.get("tensions", [])

    if not tl and not tensions:
        return ""

    left = []
    for t in tl:
        period = t.get("period", "")
        event = t.get("event", "")
        impact = t.get("impact", "")
        ptag = tag(period, "green") if period == "现在" else tag(period, "blue")
        left.append(
            f'<p>{ptag} {event}</p>\n'
            f'<p class="sub">{impact}</p>'
        )

    right = []
    for te in tensions:
        axis = te.get("axis", "")
        desc = te.get("description", "")
        resolution = te.get("resolution", "")
        right.append(
            f'<p><strong>{axis}</strong></p>\n'
            f'<p class="sub">{desc}</p>\n'
            f'<p class="sub"><span style="color:#888">{resolution}</span></p>'
        )

    return row("直取 · 时间线", left, "分析 · 核心张力", right)


def render_motifs(data: dict):
    themes = data.get("themes", [])
    motifs = data.get("motifs", [])

    if not themes and not motifs:
        return ""

    left = []
    for th in themes:
        name = th.get("theme", "")
        manifest = th.get("manifestation", "")
        left.append(
            f'<p><strong>{name}</strong></p>\n'
            f'<p class="sub">{manifest}</p>'
        )

    type_colors = {"image": "orange", "character": "blue", "plot": "green", "theme": "purple"}
    right = []
    for m in motifs:
        name = m.get("name", "")
        mtype = m.get("type", "")
        desc = m.get("description", "")
        excerpt = m.get("excerpt", "")
        color = type_colors.get(mtype, "gray")
        right.append(
            f'<p>{tag(mtype, color)} <strong>{name}</strong></p>\n'
            f'<p class="sub">{desc}</p>'
        )

    return row("直取 · 主题", left, "分析 · 母题", right)


def main():
    parser = argparse.ArgumentParser(description="故事可视化渲染")
    parser.add_argument("input", type=Path, help="story.yaml 文件")
    parser.add_argument("--output", "-o", type=Path, default=Path("index.html"), help="输出 HTML 文件")
    args = parser.parse_args()

    data = yaml.safe_load(args.input.read_text())
    source = data.get("source", args.input.name)
    title = "📖 故事抽取结果"

    rows = "\n".join(filter(None, [
        render_characters(data),
        render_setting(data),
        render_timeline(data),
        render_motifs(data),
    ]))

    html = HTML_TPL.format(title=title, source=source, rows=rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(f"渲染完成: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
