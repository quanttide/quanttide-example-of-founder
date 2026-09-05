"""任务看板固定测试：锁定读写、状态与清单生成行为。

运行：python3 -m unittest discover -s tests
不依赖图形界面；修改 src/task_board.py 前后都应保持全绿。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import task_board  # noqa: E402

FIXTURE = REPO / "data" / "write" / "2026-09-06-任务扫描.json"


FOLDERS = {"职场言情", "重生言情", "校园言情", "草稿箱"}


def sample_data():
    return {
        "title": "测试",
        "sub": "",
        "tasks": [
            {"type": "补写", "folder": "职场言情", "rec": True,
             "title": "任务甲", "hint": "甲的提示", "meta": "m"},
            {"type": "定稿", "folder": "草稿箱", "rec": False,
             "title": "任务乙", "hint": "乙的提示", "meta": "m"},
        ],
        "state": {"selected": [], "feedback": {}},
    }


class FixtureTest(unittest.TestCase):
    """固定数据契约：看板依赖的字段结构不被无意破坏。"""

    def setUp(self):
        self.data = task_board.load(FIXTURE)

    def test_task_count(self):
        self.assertEqual(len(self.data["tasks"]), 10)

    def test_required_keys(self):
        for t in self.data["tasks"]:
            for key in ("type", "folder", "title", "hint", "meta"):
                self.assertIn(key, t, f"任务缺少字段 {key}：{t.get('title')}")

    def test_rec_optional_bool(self):
        for t in self.data["tasks"]:
            self.assertIsInstance(t.get("rec", False), bool)

    def test_folder_is_real(self):
        """分类严格对应仓库文件夹，不得出现自造分组。"""
        for t in self.data["tasks"]:
            self.assertIn(t["folder"], FOLDERS,
                          f"分类不是真实文件夹：{t['folder']}（{t['title']}）")

    def test_titles_unique(self):
        titles = [t["title"] for t in self.data["tasks"]]
        self.assertEqual(len(titles), len(set(titles)))

    def test_state_defaults(self):
        self.assertIn("selected", self.data["state"])
        self.assertIn("feedback", self.data["state"])


class RoundtripTest(unittest.TestCase):
    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            data = sample_data()
            data["state"] = {"selected": [1],
                             "feedback": {"任务甲": {"tag": "先做", "text": "意见"}}}
            task_board.save(p, data)
            loaded = task_board.load(p)
            self.assertEqual(loaded["tasks"][1]["title"], "任务乙")
            self.assertEqual(loaded["state"]["feedback"]["任务甲"]["tag"], "先做")
            self.assertNotIn("任务甲", [t["title"] for t in loaded["tasks"] if False])

    def test_save_leaves_no_tmp(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.json"
            task_board.save(p, sample_data())
            self.assertEqual(list(Path(d).glob("*.tmp")), [])
            self.assertEqual(list(Path(d).glob("*.json")), [p])


class PruneFeedbackTest(unittest.TestCase):
    def test_empty_entries_dropped(self):
        state = {"selected": [], "feedback": {
            "甲": {"tag": "", "text": ""},
            "乙": {"tag": "先做", "text": ""},
            "丙": {"tag": "", "text": "理由"},
        }}
        pruned = task_board.prune_feedback(state)
        self.assertIn("乙", pruned["feedback"])
        self.assertIn("丙", pruned["feedback"])
        self.assertNotIn("甲", pruned["feedback"])

    def test_history_only_kept(self):
        state = {"selected": [], "feedback": {
            "甲": {"tag": "", "text": "", "history": [{"time": "09-06 10:00", "tag": "不做", "text": ""}]},
        }}
        self.assertIn("甲", task_board.prune_feedback(state)["feedback"])

    def test_all_empty_gives_empty(self):
        state = {"selected": [], "feedback": {"甲": {"tag": "", "text": ""}}}
        self.assertEqual(task_board.prune_feedback(state)["feedback"], {})


class RecordTest(unittest.TestCase):
    def test_record_updates_and_appends(self):
        entry = {}
        task_board.record(entry, "先做", "趁热打铁", "09-06 10:00")
        self.assertEqual(entry["tag"], "先做")
        self.assertEqual(entry["text"], "趁热打铁")
        self.assertEqual(entry["history"], [{"time": "09-06 10:00", "tag": "先做", "text": "趁热打铁"}])

    def test_record_keeps_previous_tag(self):
        entry = {"tag": "先做"}
        task_board.record(entry, "", "补充理由", "09-06 10:01")
        self.assertEqual(entry["tag"], "先做")
        self.assertEqual(entry["history"][0]["tag"], "先做")

    def test_record_twice_gives_two_history(self):
        entry = {}
        task_board.record(entry, "先做", "一", "09-06 10:00")
        task_board.record(entry, "缓做", "改主意了", "09-06 10:05")
        self.assertEqual(entry["tag"], "缓做")
        self.assertEqual(len(entry["history"]), 2)


class DataFileTest(unittest.TestCase):
    """数据目录与默认路径行为。"""

    def test_default_dir_has_json(self):
        self.assertTrue(list(task_board.DEFAULT_DIR.glob("*.json")),
                        f"{task_board.DEFAULT_DIR} 下应有数据文件")

    def test_fixture_is_valid_json(self):
        with open(FIXTURE, encoding="utf-8") as f:
            json.load(f)


if __name__ == "__main__":
    unittest.main()
