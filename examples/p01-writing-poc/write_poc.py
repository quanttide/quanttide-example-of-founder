#!/usr/bin/env python3
"""
写作云 3R 引擎 PoC — 创作情境引导原型

用法:
  python write_poc.py review <file>       评审分析
  python write_poc.py reflect <file>      情境引导
  python write_poc.py rewrite <file> <new> 改写记录
  python write_poc.py session <file>      完整 3R 会话

P0 已验证: Zed + AI 手动 3R 循环
本 PoC: 将方法论自动化为 CLI 工具
"""

import argparse
import re
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple


# ─── 数据模型 ─────────────────────────────────────────────

class Gap:
    def __init__(self, type_: str, line: int, text: str, detail: str, score: int):
        self.type = type_
        self.line = line
        self.text = text
        self.detail = detail
        self.score = score  # 绿3 黄2 红1

    def __repr__(self):
        colors = {3: '🟢', 2: '🟡', 1: '🔴'}
        return f"  {colors[self.score]} L{self.line} [{self.type}] {self.detail}: {self.text[:60]}"


class StyleCheck:
    def __init__(self, name: str, score: int, detail: str, suggestion: str):
        self.name = name
        self.score = score       # 0-100
        self.detail = detail
        self.suggestion = suggestion

    def __repr__(self):
        bar = '█' * (self.score // 10) + '░' * (10 - self.score // 10)
        return f"  [{bar:>10}] {self.score:>3}%  {self.name} — {self.suggestion}"


# ─── 评审引擎 ────────────────────────────────────────────

class ReviewEngine:
    """
    基于 context/write.md 方法论的空隙检测与风格分析
    """
    TIME_JUMP_PATTERNS = [
        r'第二天(清晨|上午|中午|下午|晚上|深夜)?',
        r'过了一会儿', r'过了[一会儿很久一段时间]',
        r'[那这]天(晚上|深夜)',
        r'[几好]个小时后',
        r'不久之后',  r'次日', r'翌日',
        r'一周(后|之后)', r'一个月(后|之后)',
    ]

    NAMED_EMOTION_RE = r'(感到|觉得)\s*.{0,10}(不安|焦虑|紧张|害怕|开心|难过|沉重|孤单|温暖|幸福|痛苦|矛盾|坚定|犹豫|惊喜|失落|满足|疲惫|煎熬|慌乱)'

    EMOTION_LABELS_RE = r'(欣喜|悲伤|愤怒|尴尬|开心|难过|激动|焦虑|平静|紧张|兴奋|失望|沮丧|羞怯|沉重|胆怯|燥热)地'

    IDENTITY_LABELS_RE = r'(作为|身为|以.*的身份).{0,20}(创业者|投资人|校友|老板|员工|父亲|母亲|儿子|女儿)'

    PERSPECTIVE_CHANGE_RE = r'(他|她|我|你)(突然|终于|还是|又|也|就|已经)?\s*(感觉|觉得|想|认为|知道|明白|意识到|发现|看到|听到|心想|想起|忘不了)'

    DIALOG_LINE_RE = r'^[“"「『]|[」』"”]$'

    ACTION_VERBS = [
        '推开', '走进', '走出', '坐下', '站起', '转身', '拿起', '放下',
        '打开', '关上', '递', '接', '碰', '触', '擦', '抹',
        '伸', '拉', '走', '站', '坐', '推', '停', '低',
        '挡', '抓', '握', '敲', '放', '抬', '低',
        '探', '揽', '搂', '牵', '拽', '扶', '撑', '趴', '蹲',
        '跪', '躺', '靠', '贴', '退', '躲', '闪', '侧',
        '偏', '仰', '俯', '闭', '睁', '眯', '眨', '盯', '瞥',
        '抿', '舔', '咬', '吸', '呼', '叹', '颤', '抖',
        '拎', '挎', '披', '裹', '卷', '拧', '掰', '勾',
    ]

    TRANSITION_VERBS = [
        r'(不知不觉|不知不|恍然|猛然|突然).{0,6}(间|地)',
        r'回过神来', r'过了一会(儿|)',
    ]

    # 评分权重（可配置，适配不同体裁）
    WEIGHTS = {
        'identity_label_penalty': 20,
        'emotion_label_penalty': 15,
        'parallel_narrative_penalty': 25,
        'flashback_block_penalty': 20,
        'action_conversion_multiplier': 2,
        'perspective_shifts_per_100': 3,
        'gap_density_multiplier': 20,
    }

    BODY_WORDS = [
        '头发', '指尖', '手', '脚', '皮肤', '呼吸', '心跳', '湿', '涩', '热', '冷', '疼',
        '眼睑', '睫毛', '嘴唇', '下颌', '颈', '锁骨', '肩膀', '脊背', '胸口', '腰', '手腕',
        '掌心', '指节', '膝', '脚踝', '脉搏', '体温', '汗', '痒', '麻', '酸', '胀', '闷',
        '哽咽', '吞咽', '喉咙', '脸颊', '眼眶', '视线',
    ]

    def __init__(self, text: str, path: str = "<stdin>", dual_pov: bool = False):
        self.text = text
        self.lines = text.split('\n')
        self.path = path
        self.dual_pov = dual_pov
        self.gaps: List[Gap] = []
        self.styles: List[StyleCheck] = []
        self.stats = {
            'total_lines': len(self.lines),
            'total_chars': len(text),
            'scene_count': 0,
            'dialog_lines': 0,
            'action_lines': 0,
            'emotion_labels': 0,
            'identity_labels': 0,
            'time_jumps': 0,
            'state_endings': 0,
            'plot_endings': 0,
            'perspective_shifts': 0,
            'word_count': 0,
        }
        self._detect_scenes()

    def _detect_scenes(self):
        """用连续空行或水平线检测场景边界"""
        scenes = []
        current_start = 1
        blank_run = 0
        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped:
                blank_run += 1
                continue
            # 连续 2+ 空行 = 场景切换
            if blank_run >= 2 and not self._is_continuation(stripped):
                scenes.append((current_start, i - blank_run - 1 if i - blank_run - 1 >= current_start else current_start))
                current_start = i
            elif re.match(r'^---+', stripped):
                # 水平线分隔
                scenes.append((current_start, i - 1))
                current_start = i
            blank_run = 0
        if self.lines and current_start <= len(self.lines):
            scenes.append((current_start, len(self.lines)))
        self.scenes = scenes
        self.stats['scene_count'] = len(scenes)

    def _is_continuation(self, line: str) -> bool:
        """判断是否只是分段而非场景切换（eg. 列表项、引用、对话续行）"""
        return bool(re.match(r'^\s*[>\-*\d.]', line))

    def run(self):
        self._detect_gaps()
        self._analyze_style()
        self._compute_stats()

    def _detect_gaps(self):
        for i, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped:
                continue

            # 时间跳跃
            for pat in self.TIME_JUMP_PATTERNS:
                if re.search(pat, stripped):
                    self.gaps.append(Gap(
                        '时间跳跃', i, stripped[:50],
                        f'匹配: {pat} — 这段时间未被写',
                        2 if '第二天' in pat else 3
                    ))
                    self.stats['time_jumps'] += 1
                    break

            # 对话间隙: 对白行之间缺少动作/心理描写
            if re.search(r'[「「『""]', stripped):
                prev = self._prev_nonblank(i)
                if prev and re.search(r'[」」』""]', prev) and not self._has_action(stripped):
                    self.gaps.append(Gap(
                        '对话间隙', i, stripped[:50],
                        '对白之间缺少动作或心理描写',
                        2
                    ))

            # 动作间空隙
            if self._is_action_line(stripped):
                prev = self._prev_nonblank(i)
                if prev and self._is_action_line(prev):
                    self.gaps.append(Gap(
                        '动作间空隙', i, stripped[:50],
                        '两个连续动作之间缺少过渡',
                        3
                    ))

            # 人为过渡词标记（暗示时间被压缩了，值得展开）
            for pat in self.TRANSITION_VERBS:
                if re.search(pat, stripped):
                    self.gaps.append(Gap(
                        '过渡压缩', i, stripped[:60],
                        f'「{pat.replace("()", "")}」暗示时间被压缩',
                        2 if '不知不觉' in pat else 3
                    ))
                    break

            # 视角切换检测
            m = re.search(self.PERSPECTIVE_CHANGE_RE, stripped)
            if m:
                self.stats['perspective_shifts'] += 1
                prev = self._prev_nonblank(i)
                if prev:
                    pm = re.search(self.PERSPECTIVE_CHANGE_RE, prev)
                    if pm and pm.group(1) != m.group(1):
                        self.gaps.append(Gap(
                            '视角切换', i, stripped[:50],
                            f'从 {pm.group(1)} 到 {m.group(1)} 缺少重叠瞬间',
                            3
                        ))

    def _prev_nonblank(self, i: int) -> str:
        for j in range(i - 2, max(i - 10, -1), -1):
            prev = self.lines[j - 1].strip() if j >= 1 else ''
            if prev:
                return prev
        return ''

    def _is_action_line(self, line: str) -> bool:
        for v in self.ACTION_VERBS:
            if v in line:
                return True
        return False

    def _has_action(self, line: str) -> bool:
        return self._is_action_line(line) or bool(re.search(r'沉默|停顿|低头|抬头|深呼吸', line))

    def _analyze_style(self):
        w = self.WEIGHTS

        # 1. 对话→动作转化率
        dialog_lines = sum(1 for l in self.lines if re.search(r'[「「『""]', l))
        action_lines = sum(1 for l in self.lines if self._is_action_line(l))
        total_with_content = sum(1 for l in self.lines if l.strip())
        dialog_ratio = (dialog_lines / max(total_with_content, 1)) * 100
        action_ratio = (action_lines / max(total_with_content, 1)) * 100
        self.stats['dialog_lines'] = dialog_lines
        self.stats['action_lines'] = action_lines

        self.styles.append(StyleCheck(
            '对话 → 动作', min(100, int(action_ratio * w['action_conversion_multiplier'])),
            f'对话{int(dialog_ratio)}% / 动作{int(action_ratio)}%',
            '用身体动作替代对话，信任读者不需台词也能理解情绪'
        ))

        # 2. 身份标签→身体感知
        identity_matches = len(re.findall(self.IDENTITY_LABELS_RE, self.text))
        self.stats['identity_labels'] = identity_matches
        body_count = sum(self.text.count(w) for w in self.BODY_WORDS)
        identity_score = max(0, 100 - identity_matches * w['identity_label_penalty']) if identity_matches > 0 else 100
        self.styles.append(StyleCheck(
            '身份标签 → 身体感知', identity_score,
            f'身份标签{identity_matches}处 / 身体词汇{body_count}处',
            '通过物与身体的接触传递情绪，而非身份标签'
        ))

        # 3. 命名情绪→隐藏情绪
        emotion_matches = len(re.findall(self.EMOTION_LABELS_RE, self.text))
        named_emotions = len(re.findall(self.NAMED_EMOTION_RE, self.text))
        self.stats['emotion_labels'] = emotion_matches + named_emotions
        hidden_score = max(0, 100 - (emotion_matches + named_emotions) * w['emotion_label_penalty'])
        self.styles.append(StyleCheck(
            '命名情绪 → 隐藏情绪', hidden_score,
            f'情绪副词{emotion_matches}处 + 感到/觉得{named_emotions}处',
            '让读者自己命名情绪，删除"地"字情绪副词和"感到/觉得"句式'
        ))

        # 4. 有限第三人称紧贴（--dual-pov 时豁免）
        if not self.dual_pov:
            shift_count = self.stats['perspective_shifts']
            lines_per_100 = self.stats['total_lines'] / 100
            expected_shifts = max(w['perspective_shifts_per_100'] * lines_per_100, 1)
            overage = shift_count - expected_shifts
            perspective_score = max(0, 100 - (overage / expected_shifts) * 100) if overage > 0 else 100
            self.styles.append(StyleCheck(
                '有限第三人称紧贴', perspective_score,
                f'视角切换点{shift_count}处',
                '每个场景锁定一个角色内部视角，切换发生在物理分离后'
            ))

        # 5. 状态句 vs 情节句结尾
        last_lines = [l.strip() for l in self.lines[-5:] if l.strip()]
        state_markers = ['突然', '感觉', '—', '……', '?', '？', '不', '还没', '还']
        plot_markers = ['加了', '约定', '安排', '决定', '知道', '告诉']
        for line in last_lines:
            if any(m in line for m in state_markers):
                self.stats['state_endings'] += 1
                break
        for line in last_lines:
            if any(m in line for m in plot_markers):
                self.stats['plot_endings'] += 1
                break
        ending_score = 100 if self.stats['state_endings'] > self.stats['plot_endings'] else 30
        self.styles.append(StyleCheck(
            '状态句结尾', ending_score,
            f'状态句{self.stats["state_endings"]}处 / 情节句{self.stats["plot_endings"]}处',
            '停在最紧张的时刻，不化解冲突'
        ))

        # 6. 对称叙事→交错叙事检测
        parallel_count = self._count_parallel_narrative()
        parallel_score = max(0, 100 - parallel_count * w['parallel_narrative_penalty'])
        self.styles.append(StyleCheck(
            '对称叙事 → 交错叙事', parallel_score,
            f'对称模式{parallel_count}处',
            '从各写一段内心到动作触发反应交错叙事'
        ))

        # 7. 半秒钟密度
        gap_count = len(self.gaps)
        density = min(100, gap_count * w['gap_density_multiplier'])
        self.styles.append(StyleCheck(
            '半秒钟发现密度', density,
            f'空隙{len(self.gaps)}处 / {self.stats["total_lines"]}行',
            '在已有文本中发现两个动作之间的空隙'
        ))

        # 8. 过去闪回 vs 碎片插入
        flashback_blocks = self._count_flashback_blocks()
        flashback_score = max(0, 100 - flashback_blocks * w['flashback_block_penalty'])
        self.styles.append(StyleCheck(
            '过去闪回 → 碎片插入', flashback_score,
            f'整段闪回块{flashback_blocks}处',
            '过去只用足以解释现在的长度出现，不单独成段'
        ))

    def _count_scene_starts(self, mode: str) -> int:
        count = 0
        for s, e in self.scenes:
            first_line = self.lines[s - 1].strip() if self.lines else ''
            if mode == 'action' and self._is_action_line(first_line):
                count += 1
            elif mode == 'narrative':
                has_dialog = bool(re.search(r'[「「『""]', first_line))
                has_action = self._is_action_line(first_line)
                if not has_dialog and not has_action:
                    count += 1
        return count

    def _count_parallel_narrative(self) -> int:
        count = 0
        for i, line in enumerate(self.lines):
            if '他' in line and '她' in line and re.search(r'也|同样|各自', line):
                count += 1
        return count

    def _count_flashback_blocks(self) -> int:
        count = 0
        in_flashback = False
        for line in self.lines:
            if re.match(r'^\s*[他她]还记得|回想|记忆|那时|曾经', line):
                if not in_flashback:
                    count += 1
                    in_flashback = True
            else:
                in_flashback = False
        return count

    def _compute_stats(self):
        pass

    def print_report(self):
        print(f"\n{'='*60}")
        print(f"  3R Review — 评审报告")
        print(f"  文件: {self.path}")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"  字数: {len(self.text)} 字符, {self.stats['total_lines']} 行")
        print(f"{'='*60}")

        print(f"\n── 空隙检测 ──")
        if self.gaps:
            for g in sorted(self.gaps, key=lambda x: -x.score):
                print(g)
        else:
            print("  (未检测到明显空隙)")

        print(f"\n── 风格检查 ──")
        for s in self.styles:
            print(s)

        avg_score = sum(s.score for s in self.styles) / max(len(self.styles), 1)
        print(f"\n  风格综合评分: {avg_score:.0f}/100")

        print(f"\n── 场景结构 ──")
        print(f"  • 场景数: {self.stats['scene_count']} 个")
        scene_lens = [e - s + 1 for s, e in self.scenes]
        print(f"  • 场景长度: 最短{min(scene_lens)}行 / 最长{max(scene_lens)}行 / 平均{sum(scene_lens)//len(scene_lens)}行")
        if self.stats['scene_count'] >= 2:
            print(f"  • 进场景方式: 以动作开始 {self._count_scene_starts('action')} 个 / 以叙述开始 {self._count_scene_starts('narrative')} 个")

        print(f"\n── 评审摘要 ──")
        print(f"  • 空隙: {len(self.gaps)} 处待填补")
        print(f"  • 情绪标记: {self.stats['emotion_labels']} 处可隐藏")
        print(f"  • 身份标签: {self.stats['identity_labels']} 处可转换")
        print(f"  • 视角切换: {self.stats['perspective_shifts']} 处")

        # 生成建议
        weakest = min(self.styles, key=lambda s: s.score)
        print(f"\n── 优先改进 ──")
        print(f"  最低分项: {weakest.name} ({weakest.score}%)")
        print(f"  建议: {weakest.suggestion}")

        return avg_score


# ─── 反思引擎 ────────────────────────────────────────────

class ReflectionEngine:
    def __init__(self, review: ReviewEngine):
        self.review = review
        self.situations: List[str] = []

    def generate(self) -> List[str]:
        lines = self.review.lines
        self.situations = []

        # 基于空隙生成情境引导
        for g in self.review.gaps:
            if g.score >= 2:
                prompt = self._situation_for_gap(g, lines)
                if prompt:
                    self.situations.append(prompt)

        # 默认情境
        if not self.situations:
            self.situations.append(
            '这段文本里发生了什么？试着找到两个句子之间的空气——\n'
            '角色在说话前后做了什么？在动作之间有没有未被写的半秒钟？'
        )

        return self.situations

    def _situation_for_gap(self, gap: Gap, lines: List[str]) -> str:
        if gap.type == '时间跳跃':
            return (
                f"在 L{max(1, gap.line-2)} 附近，文本跳过了「{gap.text[:30]}」这段时间。\n"
                f"这段时间里——房间里有什么声音？光线有变化吗？\n"
                f"角色在这段时间里做了什么？即使只是坐着，也有一具身体在时间里。"
            )
        elif gap.type == '对话间隙':
            return (
                f"L{gap.line} 的对白之间有一段沉默未被写。\n"
                f"说话的人在开口前做了什么？吞咽了一下？看向了别处？\n"
                f"沉默不是空白——它是角色正在处理情绪的物理时间。"
            )
        elif gap.type == '视角切换':
            return (
                f"在 L{gap.line} 附近发生了视角切换。\n"
                f"切换前的最后一个瞬间——那个角色看到了什么？感受到了什么？\n"
                f"视角切换不是剪辑，是接力：一个人的感知结束在另一个人的感知开始之前。"
            )
        elif gap.type == '动作间空隙':
            return (
                f"L{gap.line} 的两个动作之间缺少过渡。\n"
                f"第一个动作结束时，角色的手在哪？呼吸节奏是怎样的？\n"
                f"半秒钟——够一个人改变主意，也够一个人下定决心。"
            )
        return ""


# ─── 3R 会话 ─────────────────────────────────────────────

class ThreeRSession:
    """交互式 3R 会话向导"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        with open(filepath, 'r', encoding='utf-8') as f:
            self.original_text = f.read()
        self.current_text = self.original_text
        self.cycle = 0
        self.log: List[Dict] = []

    def run(self):
        print(f"\n{'='*60}")
        print(f"  3R 创作会话")
        print(f"  文件: {self.filepath}")
        print(f"  字数: {len(self.current_text)}")
        print(f"{'='*60}")

        while True:
            self.cycle += 1
            print(f"\n── 第 {self.cycle} 轮 3R 循环 ──")

            # Review
            print("\n[Review] 正在评审...")
            engine = ReviewEngine(self.current_text, self.filepath)
            engine.run()
            engine.print_report()

            # Reflect
            print(f"\n── 反思 ──")
            reflector = ReflectionEngine(engine)
            situations = reflector.generate()
            for i, s in enumerate(situations[:3], 1):
                print(f"\n情境引导 #{i}:")
                print(f"  {s}")

            # Rewrite prompt
            print(f"\n── 改写 ──")
            print("  请在编辑器中修改文本，保存后输入 'y' 继续下一轮")
            print("  或输入 'q' 结束会话")
            choice = input("\n> ").strip().lower()

            if choice == 'q':
                break
            elif choice == 'y':
                # re-read the file
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    new_text = f.read()
                delta = len(new_text) - len(self.current_text)
                self.log.append({
                    'cycle': self.cycle,
                    'delta_chars': delta,
                    'score': int(sum(s.score for s in engine.styles) / max(len(engine.styles), 1)),
                })
                self.current_text = new_text
                print(f"  本轮修改: {delta:+d} 字符")

        # Session report
        print(f"\n{'='*60}")
        print(f"  会话结束 — 共 {self.cycle} 轮")
        for entry in self.log:
            print(f"  第{entry['cycle']}轮 | 修改{entry['delta_chars']:+d}字 | 风格评分:{entry['score']}")
        print(f"{'='*60}\n")


# ─── CLI ──────────────────────────────────────────────────

def cmd_review(args):
    text = sys.stdin.read() if args.file == '-' else open(args.file, 'r', encoding='utf-8').read()
    engine = ReviewEngine(text, args.file, dual_pov=args.dual_pov)
    engine.run()
    engine.print_report()

def cmd_reflect(args):
    text = sys.stdin.read() if args.file == '-' else open(args.file, 'r', encoding='utf-8').read()
    engine = ReviewEngine(text, args.file, dual_pov=args.dual_pov)
    engine.run()
    reflector = ReflectionEngine(engine)
    situations = reflector.generate()
    print(f"\n{'='*60}")
    print(f"  创作情境引导")
    print(f"{'='*60}")
    for i, s in enumerate(situations, 1):
        print(f"\n#{i}")
        print(f"{s}")
    print()

def cmd_rewrite(args):
    old = open(args.old, 'r', encoding='utf-8').read()
    new = open(args.new, 'r', encoding='utf-8').read()

    engine_old = ReviewEngine(old, args.old, dual_pov=args.dual_pov)
    engine_old.run()
    score_old = sum(s.score for s in engine_old.styles) / max(len(engine_old.styles), 1)

    engine_new = ReviewEngine(new, args.new, dual_pov=args.dual_pov)
    engine_new.run()
    score_new = sum(s.score for s in engine_new.styles) / max(len(engine_new.styles), 1)

    print(f"\n{'='*60}")
    print(f"  改写对比")
    print(f"{'='*60}")
    print(f"  旧版: {len(old)} 字, 风格评分 {score_old:.0f}/100")
    print(f"  新版: {len(new)} 字, 风格评分 {score_new:.0f}/100")
    print(f"  差异: {len(new) - len(old):+d} 字, 风格 {score_new - score_old:+.0f} 分")

    # Show changed areas
    old_lines = old.split('\n')
    new_lines = new.split('\n')
    import difflib
    diff = list(difflib.unified_diff(old_lines, new_lines, n=1))
    print(f"\n  改动的行: {len([d for d in diff if d.startswith('@@')])} 处")

def cmd_session(args):
    session = ThreeRSession(args.file)
    session.run()


def main():
    parser = argparse.ArgumentParser(
        description='写作云 3R 引擎 PoC — 创作情境引导原型',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    sub = parser.add_subparsers(dest='command')

    p_review = sub.add_parser('review', help='评审分析')
    p_review.add_argument('file', help='Markdown 文件路径 (或 - 表示 stdin)')
    p_review.add_argument('--dual-pov', action='store_true', help='声明式豁免：交替双视角不扣分')

    p_reflect = sub.add_parser('reflect', help='生成情境引导')
    p_reflect.add_argument('file', help='Markdown 文件路径 (或 - 表示 stdin)')
    p_reflect.add_argument('--dual-pov', action='store_true', help='声明式豁免：交替双视角不扣分')

    p_rewrite = sub.add_parser('rewrite', help='改写对比记录')
    p_rewrite.add_argument('old', help='旧版文件')
    p_rewrite.add_argument('new', help='新版文件')
    p_rewrite.add_argument('--dual-pov', action='store_true', help='声明式豁免：交替双视角不扣分')

    p_session = sub.add_parser('session', help='完整 3R 会话向导')
    p_session.add_argument('file', help='Markdown 文件路径')
    p_session.add_argument('--dual-pov', action='store_true', help='声明式豁免：交替双视角不扣分')

    args = parser.parse_args()
    if args.command == 'review':
        cmd_review(args)
    elif args.command == 'reflect':
        cmd_reflect(args)
    elif args.command == 'rewrite':
        cmd_rewrite(args)
    elif args.command == 'session':
        cmd_session(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
