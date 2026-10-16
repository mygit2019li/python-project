"""
本地文本审核（开源方案，零额外依赖）
====================================
基于 Aho-Corasick 多模式匹配（DFA）的敏感词检测，
用于替代微信 msgSecCheck：彻底移除网络往返，检测在本地瞬时完成（亚毫秒级）。

词库：hivision/data/sensitive_words.txt
- 每行一个词条；可用 Tab 分隔「类别 / 标签」，例如：
      赌博\t违禁违法\t220
      傻逼\t辱骂\t200
- 省略类别/标签时，默认归类为「违禁违法」(label 220)。
- 以 # 开头的行为注释。

严重级别（决定 suggest）：
- 高危（色情低俗 / 违禁违法 / 暴恐）→ suggest='risky'，直接拦截
- 中危（辱骂 / 广告引流）          → suggest='review'，同样按「不通过」处理

如需语义级识别（变体/谐音/上下文），可在此模块后接一个轻量 ML 模型，
当前版本聚焦「快、稳、零依赖」，覆盖绝大多数明文违规。
"""

import os
import threading
from collections import deque

DEFAULT_WORDLIST = os.path.join(os.path.dirname(__file__), "data", "sensitive_words.txt")

# 标签 -> (中文类别, suggest)
SEVERITY = {
    200: ("辱骂", "review"),
    210: ("广告引流", "review"),
    220: ("违禁违法", "risky"),
    230: ("色情低俗", "risky"),
    240: ("暴恐", "risky"),
}

# 归一化时剔除的分隔符，用于拦截「敏 感 词」「敏-感-词」式规避
_SEP_CHARS = set(" \t\r\n\\-_・·*•~=")


class _AhoCorasick:
    """极简 Aho-Corasick 自动机，支持失败指针与多模式匹配。"""

    def __init__(self):
        self.goto = [{}]   # 状态转移：list[dict[char->state]]
        self.fail = [0]    # 失败指针
        self.out = [[]]    # 每个状态命中的 (word, label, category)

    def add(self, word, label, category):
        state = 0
        for ch in word:
            if ch not in self.goto[state]:
                self.goto[state][ch] = len(self.goto)
                self.goto.append({})
                self.fail.append(0)
                self.out.append([])
            state = self.goto[state][ch]
        self.out[state].append((word, label, category))

    def build(self):
        q = deque()
        for _ch, nxt in self.goto[0].items():
            self.fail[nxt] = 0
            q.append(nxt)
        while q:
            r = q.popleft()
            for ch, nxt in self.goto[r].items():
                q.append(nxt)
                f = self.fail[r]
                while f and ch not in self.goto[f]:
                    f = self.fail[f]
                self.fail[nxt] = self.goto[f].get(ch, 0)
                # 继承失败状态的输出
                self.out[nxt].extend(self.out[self.fail[nxt]])

    def search(self, text):
        """返回 [(word, label, category, start, end)]。"""
        hits = []
        state = 0
        for i, ch in enumerate(text):
            while state and ch not in self.goto[state]:
                state = self.fail[state]
            state = self.goto[state].get(ch, 0)
            if self.out[state]:
                for (word, label, category) in self.out[state]:
                    start = i - len(word) + 1
                    hits.append((word, label, category, start, i + 1))
        return hits


class TextModerator:
    def __init__(self, wordlist_path=DEFAULT_WORDLIST):
        self._ac = _AhoCorasick()
        self._word_count = 0
        self.load(wordlist_path)

    def load(self, path):
        ac = _AhoCorasick()
        count = 0
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n")
                    if not line or line.lstrip().startswith("#"):
                        continue
                    parts = line.split("\t")
                    word = parts[0].strip()
                    if not word:
                        continue
                    category = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "违禁违法"
                    label = int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else 220
                    ac.add(word, label, category)
                    count += 1
        ac.build()
        self._ac = ac
        self._word_count = count
        if count == 0:
            print("[text_moderation] 警告：词库为空或未找到，所有文本将直接放行。")
        else:
            print(f"[text_moderation] 已加载敏感词 {count} 条。")

    def moderate(self, content):
        """
        检测文本。返回 dict：
          suggest: 'pass' / 'review' / 'risky'
          label:   命中的最高危标签（无命中为 100）
          hits:    命中词列表（去重）
          detail:  [{word, label, category, start, end}]
        """
        if not content or not content.strip():
            return {"suggest": "pass", "label": 100, "hits": [], "detail": []}

        # 轻量归一化：去除空格与常见分隔符，拦截插字规避
        normalized = "".join(ch for ch in content if ch not in _SEP_CHARS)

        raw_hits = self._ac.search(content)
        norm_hits = self._ac.search(normalized) if normalized != content else []

        seen = set()
        hits = []
        for (word, label, category, start, end) in raw_hits:
            if word in seen:
                continue
            seen.add(word)
            hits.append({"word": word, "label": label, "category": category, "start": start, "end": end})
        for (word, label, category, _s, _e) in norm_hits:
            if word in seen:
                continue
            seen.add(word)
            pos = content.find(word)
            start = pos if pos >= 0 else -1
            end = start + len(word) if start >= 0 else -1
            hits.append({"word": word, "label": label, "category": category, "start": start, "end": end})

        if not hits:
            return {"suggest": "pass", "label": 100, "hits": [], "detail": []}

        worst = max(hits, key=lambda x: x["label"])
        label = worst["label"]
        suggest = SEVERITY.get(label, ("违禁违法", "risky"))[1]
        return {"suggest": suggest, "label": label, "hits": [h["word"] for h in hits], "detail": hits}


_moderator = None
_moderator_lock = threading.Lock()


def get_text_moderator() -> TextModerator:
    """进程内单例，首次调用时构建自动机。"""
    global _moderator
    if _moderator is None:
        with _moderator_lock:
            if _moderator is None:
                _moderator = TextModerator()
    return _moderator
