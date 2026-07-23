"""行文习惯学习模块。

从用户历史文档中分析行文特征，生成习惯画像，支持增量更新。
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── 内置停用词表 ────────────────────────────────────────────────────────────────

_CHINESE_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
    "看", "好", "自己", "这", "他", "她", "它", "们", "那", "把", "被", "从",
    "让", "用", "对", "可以", "这个", "那个", "吗", "呢", "吧", "啊", "么",
    "所以", "但是", "而且", "如果", "因为", "什么", "怎么", "哪", "谁",
    "多", "少", "大", "小", "又", "还", "能", "得", "地", "过", "做",
    "来", "与", "及", "或", "等", "之", "其", "为", "以", "于", "中",
}

_ENGLISH_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "although", "this",
    "that", "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "it", "its", "they", "them", "their",
    "what", "which", "who", "whom", "whose", "about", "also", "up",
}

_ALL_STOPWORDS = _CHINESE_STOPWORDS | _ENGLISH_STOPWORDS

# 中文标点列表
_CN_PUNCTUATION = "，。！？；：、""''（）【】《》——…～"
_SENTENCE_DELIMITERS = re.compile(r"[。！？.!?\n]+")
_PARAGRAPH_SEPARATOR = re.compile(r"\n\s*\n")


class HabitAnalyzer:
    """行文习惯分析器。

    从文档集合中分析用户行文习惯，生成可注入 Prompt 的习惯画像。
    """

    def __init__(self, profile_path: Optional[Path] = None) -> None:
        """初始化 HabitAnalyzer。

        Args:
            profile_path: 习惯画像保存路径，默认 ~/.doc-agent/habit_profile.json。
        """
        if profile_path is not None:
            self.profile_path = Path(profile_path)
        else:
            self.profile_path = Path.home() / ".doc-agent" / "habit_profile.json"

    def learn_from_documents(self, doc_paths: list[Path]) -> dict:
        """从文档列表学习行文习惯，返回习惯画像。

        Args:
            doc_paths: 文档文件路径列表。

        Returns:
            习惯画像字典。
        """
        all_text = []
        for path in doc_paths:
            p = Path(path)
            if p.exists() and p.is_file():
                try:
                    content = p.read_text(encoding="utf-8")
                    if content.strip():
                        all_text.append(content)
                except (OSError, UnicodeDecodeError) as e:
                    logger.warning("读取文件失败 '%s': %s", p, e)

        if not all_text:
            logger.warning("没有有效的文档内容可供分析")
            return {}

        return self._analyze_texts(all_text)

    def learn_from_directory(self, dir_path: Path, extensions: Optional[list[str]] = None) -> dict:
        """从目录中扫描所有文档学习。

        Args:
            dir_path: 目录路径。
            extensions: 要扫描的文件扩展名列表，默认 [".md", ".txt", ".rst"]。

        Returns:
            习惯画像字典。
        """
        if extensions is None:
            extensions = [".md", ".txt", ".rst"]

        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            logger.warning("目录不存在: %s", dir_path)
            return {}

        doc_paths: list[Path] = []
        for ext in extensions:
            ext_with_dot = ext if ext.startswith(".") else f".{ext}"
            doc_paths.extend(dir_path.rglob(f"*{ext_with_dot}"))

        if not doc_paths:
            logger.warning("目录 '%s' 中没有找到匹配的文档", dir_path)
            return {}

        logger.info("从目录 '%s' 发现 %d 个文档", dir_path, len(doc_paths))
        return self.learn_from_documents(doc_paths)

    def save_profile(self, profile: dict) -> None:
        """保存习惯画像到 JSON 文件。

        Args:
            profile: 习惯画像字典。
        """
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        logger.info("习惯画像已保存: %s", self.profile_path)

    def load_profile(self) -> Optional[dict]:
        """加载已有画像。

        Returns:
            习惯画像字典，或 None（文件不存在时）。
        """
        if not self.profile_path.exists():
            return None

        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("加载习惯画像失败: %s", e)
            return None

    def format_for_prompt(self, profile: dict) -> str:
        """格式化为 Prompt 注入文本。

        Args:
            profile: 习惯画像字典。

        Returns:
            格式化后的纯文本字符串。
        """
        if not profile:
            return ""

        lines: list[str] = ["## 用户行文习惯"]

        # 段落长度
        avg_para_len = profile.get("paragraph_avg_length")
        if avg_para_len is not None:
            lines.append(f"- 段落通常约{int(avg_para_len)}字")

        # 句子长度
        avg_sent_len = profile.get("sentence_avg_length")
        if avg_sent_len is not None:
            if avg_sent_len <= 15:
                desc = "偏短"
            elif avg_sent_len <= 30:
                desc = "中等"
            else:
                desc = "偏长"
            lines.append(f"- 句子{desc}（平均{int(avg_sent_len)}字）")

        # 高频词
        top_words = profile.get("top_words")
        if top_words:
            words_display = top_words[:10] if isinstance(top_words, list) else list(top_words)[:10]
            lines.append(f"- 常用词汇：{'、'.join(words_display)}")

        # 标点习惯
        punct_habits = profile.get("punctuation_habits")
        if punct_habits:
            # 取频率最高的几个标点
            top_puncts = sorted(punct_habits.items(), key=lambda x: x[1], reverse=True)[:5]
            punct_desc = []
            for p, _ in top_puncts:
                punct_name = _PUNCT_NAMES.get(p, p)
                punct_desc.append(punct_name)
            if punct_desc:
                lines.append(f"- 偏好使用{'和'.join(punct_desc)}")

        # 句首词
        sentence_starters = profile.get("sentence_starters")
        if sentence_starters:
            starters_display = sentence_starters[:8] if isinstance(sentence_starters, list) else list(sentence_starters)[:8]
            starters_str = "\u3001".join(f'"{s}"' for s in starters_display)
            lines.append(f"- 句首常用：{starters_str}")

        # 段首模式
        paragraph_starters = profile.get("paragraph_starters")
        if paragraph_starters:
            para_starters_display = paragraph_starters[:6] if isinstance(paragraph_starters, list) else list(paragraph_starters)[:6]
            para_starters_str = "\u3001".join(f'"{s}"' for s in para_starters_display)
            lines.append(f"- 段落开头常用：{para_starters_str}")

        # 连接词偏好
        connectors = profile.get("preferred_connectors")
        if connectors:
            conn_display = connectors[:8] if isinstance(connectors, list) else list(connectors)[:8]
            lines.append(f"- 偏好连接词：{'、'.join(conn_display)}")

        # 平均段落数
        avg_paras = profile.get("avg_paragraphs_per_doc")
        if avg_paras is not None:
            lines.append(f"- 每篇文档平均{int(avg_paras)}个段落")

        return "\n".join(lines)

    def update_profile(self, new_doc_path: Path) -> dict:
        """增量更新：用新文档更新已有画像。

        使用加权平均方式合并新旧画像（旧画像权重 0.7，新文档权重 0.3）。

        Args:
            new_doc_path: 新文档路径。

        Returns:
            更新后的习惯画像字典。
        """
        existing = self.load_profile()
        new_profile = self.learn_from_documents([Path(new_doc_path)])

        if not new_profile:
            return existing or {}

        if not existing:
            self.save_profile(new_profile)
            return new_profile

        merged = self._merge_profiles(existing, new_profile, old_weight=0.7, new_weight=0.3)
        self.save_profile(merged)
        return merged

    # ─── 私有分析方法 ─────────────────────────────────────────────────────────────

    def _analyze_texts(self, texts: list[str]) -> dict:
        """分析多篇文本，生成习惯画像。"""
        all_paragraphs: list[str] = []
        all_sentences: list[str] = []
        all_words: list[str] = []
        punctuation_counter: Counter = Counter()
        sentence_starter_counter: Counter = Counter()
        paragraph_starter_counter: Counter = Counter()
        doc_paragraph_counts: list[int] = []

        for text in texts:
            # 分段
            paragraphs = [p.strip() for p in _PARAGRAPH_SEPARATOR.split(text) if p.strip()]
            all_paragraphs.extend(paragraphs)
            doc_paragraph_counts.append(len(paragraphs))

            # 段首模式
            for para in paragraphs:
                starter = self._extract_paragraph_starter(para)
                if starter:
                    paragraph_starter_counter[starter] += 1

            # 分句
            for para in paragraphs:
                sentences = [s.strip() for s in _SENTENCE_DELIMITERS.split(para) if s.strip()]
                all_sentences.extend(sentences)

                # 句首词
                for sent in sentences:
                    starter = self._extract_sentence_starter(sent)
                    if starter:
                        sentence_starter_counter[starter] += 1

            # 标点统计
            for char in text:
                if char in _CN_PUNCTUATION or char in ",.;:!?-()[]{}\"'":
                    punctuation_counter[char] += 1

            # 分词（简单按标点和空格分割）
            words = self._simple_tokenize(text)
            all_words.extend(words)

        # 构建画像
        profile: dict = {}

        # 段落平均字数
        if all_paragraphs:
            para_lengths = [len(p) for p in all_paragraphs]
            profile["paragraph_avg_length"] = round(sum(para_lengths) / len(para_lengths), 1)

        # 句子平均字数
        if all_sentences:
            sent_lengths = [len(s) for s in all_sentences]
            profile["sentence_avg_length"] = round(sum(sent_lengths) / len(sent_lengths), 1)

        # 高频词 Top-50（排除停用词）
        word_counter = Counter(all_words)
        filtered_words = {
            w: c for w, c in word_counter.items()
            if w not in _ALL_STOPWORDS and len(w) > 1
        }
        top_words = [w for w, _ in Counter(filtered_words).most_common(50)]
        profile["top_words"] = top_words

        # 标点使用频率（归一化）
        total_punct = sum(punctuation_counter.values())
        if total_punct > 0:
            profile["punctuation_habits"] = {
                p: round(c / total_punct, 4)
                for p, c in punctuation_counter.most_common(20)
            }

        # 常用句首词 Top-20
        profile["sentence_starters"] = [
            w for w, _ in sentence_starter_counter.most_common(20)
        ]

        # 常用段首模式
        profile["paragraph_starters"] = [
            w for w, _ in paragraph_starter_counter.most_common(15)
        ]

        # 偏好连接词
        connectors = self._extract_connectors(all_sentences)
        profile["preferred_connectors"] = connectors

        # 平均段落数
        if doc_paragraph_counts:
            profile["avg_paragraphs_per_doc"] = round(
                sum(doc_paragraph_counts) / len(doc_paragraph_counts), 1
            )

        return profile

    def _simple_tokenize(self, text: str) -> list[str]:
        """简单分词：按标点、空格和常见分隔符切分。"""
        # 先按标点、空格和各种分隔符分割
        tokens = re.split(
            r"[\s\u3000"
            r"\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001"
            r"\u201c\u201d\u2018\u2019\uff08\uff09"
            r"\u3010\u3011\u300a\u300b\u2026\uff5e"
            r",.;:!?()\[\]{}\"'/\\\-]+",
            text,
        )
        # 对中文文本，进一步按2-4字切分
        result: list[str] = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            # 如果是纯英文单词
            if re.match(r"^[a-zA-Z]+$", token):
                result.append(token.lower())
            # 中文文本：按2字和3字切分（简易 n-gram）
            elif re.search(r"[\u4e00-\u9fff]", token):
                for i in range(len(token) - 1):
                    bigram = token[i:i + 2]
                    if re.match(r"^[\u4e00-\u9fff]{2}$", bigram):
                        result.append(bigram)
            else:
                if len(token) > 1:
                    result.append(token.lower())
        return result

    def _extract_sentence_starter(self, sentence: str) -> Optional[str]:
        """提取句首词（前2-4个字）。"""
        sentence = sentence.strip()
        if len(sentence) < 2:
            return None

        # 中文：取前2-4字
        if re.match(r"[\u4e00-\u9fff]", sentence):
            # 尝试匹配常见模式
            patterns = [
                r"^(首先|其次|然后|最后|此外|另外|同时|因此|所以|但是|然而|不过|总之|综上)",
                r"^(需要注意的是|值得一提的是|换句话说|也就是说)",
                r"^(为了|通过|根据|基于|针对|关于|对于|由于)",
            ]
            for p in patterns:
                m = re.match(p, sentence)
                if m:
                    return m.group(1)
            # 默认取前2字
            return sentence[:2]

        # 英文：取第一个单词
        words = sentence.split()
        if words:
            return words[0].capitalize()
        return None

    def _extract_paragraph_starter(self, paragraph: str) -> Optional[str]:
        """提取段首模式。"""
        paragraph = paragraph.strip()
        if len(paragraph) < 2:
            return None

        # 中文段首
        patterns = [
            r"^(首先|其次|然后|最后|此外|另外|总之|综上所述)",
            r"^(需要注意的是|值得一提的是|具体来说|换言之)",
            r"^(为了|通过|根据|基于|针对|关于|对于|由于)",
            r"^(在此基础上|从.*角度|就.*而言)",
        ]
        for p in patterns:
            m = re.match(p, paragraph)
            if m:
                return m.group(1)

        # 返回前3字作为段首模式
        if re.match(r"[\u4e00-\u9fff]", paragraph):
            return paragraph[:3] if len(paragraph) >= 3 else paragraph[:2]

        # 英文：返回前两个词
        words = paragraph.split()[:2]
        return " ".join(words) if words else None

    def _extract_connectors(self, sentences: list[str]) -> list[str]:
        """提取偏好的连接词。"""
        connector_patterns = [
            "因此", "所以", "但是", "然而", "不过", "而且", "并且", "同时",
            "此外", "另外", "否则", "虽然", "尽管", "即使", "只要", "除非",
            "于是", "接着", "随后", "总之", "总而言之", "换句话说",
            "也就是说", "具体来说", "换言之", "反之", "相反",
            "therefore", "however", "moreover", "furthermore", "meanwhile",
            "nevertheless", "otherwise", "although", "besides", "consequently",
        ]

        connector_counter: Counter = Counter()
        for sent in sentences:
            for conn in connector_patterns:
                if conn in sent.lower():
                    connector_counter[conn] += 1

        return [c for c, _ in connector_counter.most_common(15)]

    def _merge_profiles(self, old: dict, new: dict, old_weight: float, new_weight: float) -> dict:
        """加权合并两个画像。"""
        merged: dict = {}

        # 数值字段：加权平均
        numeric_keys = ["paragraph_avg_length", "sentence_avg_length", "avg_paragraphs_per_doc"]
        for key in numeric_keys:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val is not None and new_val is not None:
                merged[key] = round(old_val * old_weight + new_val * new_weight, 1)
            elif new_val is not None:
                merged[key] = new_val
            elif old_val is not None:
                merged[key] = old_val

        # 列表字段：合并去重，保持频率排序
        list_keys = ["top_words", "sentence_starters", "paragraph_starters", "preferred_connectors"]
        for key in list_keys:
            old_list = old.get(key, [])
            new_list = new.get(key, [])
            # 旧列表中的项权重更高（排前面），合并去重
            seen: set = set()
            merged_list: list = []
            for item in old_list + new_list:
                if item not in seen:
                    merged_list.append(item)
                    seen.add(item)
            # 限制长度
            max_len = 50 if key == "top_words" else 20
            merged[key] = merged_list[:max_len]

        # 字典字段（punctuation_habits）：加权合并
        old_punct = old.get("punctuation_habits", {})
        new_punct = new.get("punctuation_habits", {})
        if old_punct or new_punct:
            all_keys = set(list(old_punct.keys()) + list(new_punct.keys()))
            merged_punct = {}
            for k in all_keys:
                ov = old_punct.get(k, 0)
                nv = new_punct.get(k, 0)
                merged_punct[k] = round(ov * old_weight + nv * new_weight, 4)
            # 归一化
            total = sum(merged_punct.values())
            if total > 0:
                merged_punct = {k: round(v / total, 4) for k, v in merged_punct.items()}
            merged["punctuation_habits"] = dict(
                sorted(merged_punct.items(), key=lambda x: x[1], reverse=True)[:20]
            )

        return merged


# ─── 标点名称映射 ─────────────────────────────────────────────────────────────────

_PUNCT_NAMES = {
    "，": "逗号",
    "。": "句号",
    "！": "感叹号",
    "？": "问号",
    "；": "分号",
    "：": "冒号",
    "、": "顿号",
    """: "左引号",
    """: "右引号",
    "（": "括号",
    "）": "括号",
    "——": "破折号",
    "…": "省略号",
    ",": "英文逗号",
    ".": "英文句号",
    ";": "英文分号",
    ":": "英文冒号",
    "-": "连字符",
}


# 向后兼容别名
HabitTracker = HabitAnalyzer
