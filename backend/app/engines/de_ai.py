# backend/app/engines/de_ai.py
"""De-AI Engine: detect and prevent AI-like writing traces.

Four-layer processing:
1. Prevention (Writer Prompt): embed fatigue word list + banned patterns
2. Detection (Auditor #26): scan for AI traces
3. Revision (Reviser anti-detect): replace fatigue words + rewrite patterns
4. Tracking (Global): track density trends
"""

from __future__ import annotations

import re
from typing import Any

# --- Fatigue words (200+) ---
# Common AI-generated Chinese writing "crutch" words/phrases
FATIGUE_WORDS: list[str] = [
    # Overused transition/emotion words
    "不禁", "缓缓", "微微", "淡淡", "竟然", "居然", "赫然", "骇然",
    "愕然", "怔然", "默然", "悚然", "凛然", "蓦然", "陡然", "豁然",
    "哑然", "悄然", "戛然", "嫣然", "释然", "茫然", "怅然", "黯然",
    "嗤然", "灼然", "潸然", "恍然", "肃然", "凄然", "欣然", "泫然",
    # Overused description clichés
    "一丝", "一抹", "一缕", "一股", "一阵", "一瞬", "一刹那",
    "不易察觉", "意味深长", "若有所思", "心中暗道",
    "嘴角上扬", "嘴角微翘", "嘴角勾起", "嘴角弧度",
    "眼中闪过", "眼底深处", "目光深邃", "目光如炬", "目光闪烁",
    "眉头微蹙", "眉头紧锁", "剑眉微挑", "眉目如画",
    "气息一窒", "呼吸一滞", "心头一跳", "心头一紧",
    "脑海中浮现", "脑海中闪过", "脑海里回荡",
    "内心深处", "心底深处", "灵魂深处",
    # Overused action descriptions
    "点了点头", "摇了摇头", "叹了口气", "深吸一口气",
    "紧握双拳", "攥紧拳头", "握紧了手中的",
    "转过身来", "转身离去", "拔腿就跑",
    "挺直腰板", "挺起胸膛", "负手而立",
    "抬起头来", "低下了头", "垂下眼帘",
    "咬了咬牙", "咬紧牙关", "牙关紧咬",
    # Overused atmosphere words
    "鸦雀无声", "落针可闻", "空气仿佛凝固",
    "气氛陷入", "气氛变得", "空气中弥漫",
    "一时间", "霎时间", "刹那间", "须臾之间",
    "与此同时", "就在此时", "就在这时", "话音刚落",
    # Filler expressions
    "说实话", "不得不说", "毫无疑问", "毋庸置疑",
    "事实上", "实际上", "说到底", "归根结底",
    "一言以蔽之", "换言之", "也就是说",
    # Overused modifiers
    "如同", "仿佛", "好似", "恍若", "宛如", "犹如",
    "渐渐地", "慢慢地", "默默地", "静静地", "悄悄地",
    "忍不住", "情不自禁", "不由自主", "下意识",
    # Overused power/combat descriptions
    "气势暴涨", "气势如虹", "杀意凛然",
    "浑身一震", "身躯一颤", "遍体生寒",
    "强大的气息", "恐怖的力量", "惊人的速度",
    "灵力涌动", "真气运转", "法力波动",
    # Emotional clichés
    "心中一动", "心中一凛", "心中暗惊",
    "面色微变", "面色一沉", "脸色大变", "脸色铁青",
    "怒火中烧", "怒不可遏", "怒发冲冠",
    "喜出望外", "喜不自禁", "欣喜若狂",
    "百感交集", "五味杂陈", "心如刀割",
    # Overused structural transitions
    "随即", "旋即", "继而", "进而", "紧接着",
    "但见", "只见", "就见", "便见",
    "正是", "恰是", "原来是", "竟是",
    # Descriptive clichés
    "散发着", "弥漫着", "洋溢着", "流露出", "透露出",
    "充斥着", "笼罩着", "蔓延着", "涌动着",
    "映入眼帘", "跃入眼帘", "闯入视线",
    "此言一出", "此话一出", "此语一出",
    # More padding words
    "显然", "自然", "当然", "果然", "固然",
    "毕竟", "终究", "终归", "到底",
    "似乎", "好像", "大概", "或许", "也许",
    "总之", "总而言之", "综上所述",
    # Body language clichés
    "挑了挑眉", "扬了扬眉", "皱了皱眉",
    "撇了撇嘴", "抿了抿唇", "舔了舔唇",
    "拍了拍肩", "搭上肩膀", "揽过肩膀",
    "摆了摆手", "挥了挥手", "伸出手来",
    # More emotion clichés
    "暗自庆幸", "暗自点头", "暗自思忖",
    "不由得", "不觉间", "不知不觉",
    "顿时", "当即", "登时", "霎时",
]

# --- Banned sentence patterns (30+) ---
# Regex patterns for AI-typical sentence structures
BANNED_PATTERNS_RAW: list[tuple[str, str]] = [
    (r"眼[中神]闪过一[丝抹缕].*?[的地]光[芒彩]", "眼中闪光芒模板"),
    (r"嘴角.*?[上微].*?[扬翘勾].*?[露出浮现].*?[一个].*?[微淡意].*?笑", "嘴角微笑模板"),
    (r"[他她]的.*?[目眼]光.*?[变得闪].*?[深复柔锐]", "目光变化模板"),
    (r"空气.*?[仿似好].*?[佛乎像].*?凝[固结]", "空气凝固模板"),
    (r"[一]时[间]?.*?[所有全场].*?[人的].*?[目目]光.*?[都齐].*?[投聚落]", "众人目光聚焦模板"),
    (r"心[中底头].*?[不暗].*?[由禁自].*?[涌浮升].*?一[股丝阵]", "心中涌起模板"),
    (r"[不]?禁.*?[想回]起.*?[了那当]", "不禁回想模板"),
    (r"[声音话语].*?[带透充].*?[着满].*?[不一].*?[可丝容].*?[置疑抗]", "声音带着不容置疑模板"),
    (r"[他她].*?深[深深]?[吸呼].*?[一了]口气", "深呼吸模板"),
    (r"整个[人身].*?[仿好宛].*?[佛像如].*?被.*?[抽掏]空", "被抽空模板"),
    (r"[气势力量压力].*?[如仿犹宛].*?[山海潮]", "力量如山模板"),
    (r"[他她]的[声嗓]音.*?[低沉带].*?[着了].*?[一丝几分些许].*?[沙哑疲惫磁性]", "声音沙哑模板"),
    (r"[他她].*?[缓轻]缓?[地的].*?[闭睁合].*?[上开了].*?眼", "缓缓闭眼模板"),
    (r"[仿佛好像似乎].*?[有一].*?[道股只].*?[无形无名无声].*?[的力]", "无形力量模板"),
    (r"[一]瞬[间]?.*?[他她].*?[的脑]海.*?[中里].*?闪过.*?[无数许多千万]", "脑海闪过模板"),
    (r"[他她]的心.*?[猛陡忽].*?[地然的].*?[沉一]", "心猛然一沉模板"),
    (r"周围的[空气温度气氛].*?[似仿].*?[乎佛].*?[都也].*?[降变]", "氛围变化模板"),
    (r"如同.*?[一只头道].*?[受困被].*?[伤惊]的.*?[野兽猛兽]", "受伤猛兽比喻"),
    (r"[就在正当].*?[此这]时.*?[一道一声一个]", "就在此时转折模板"),
    (r"[他她].*?[不]?由.*?[自得].*?[主]?.*?[握攥捏]紧.*?[了双]", "握紧拳头模板"),
    (r"[那这]双.*?[眼眸].*?[中里].*?[闪燃跳].*?[烁动跃].*?[着了].*?[某一种]", "眼眸闪烁模板"),
    (r"[所有在场].*?[人的].*?[脸面].*?[上色].*?[都纷].*?[露浮]出.*?[震惊骇难]", "众人震惊模板"),
    (r"[他她].*?[淡平微]淡?[地的].*?[说道开口吐出].*?[了两三一]个字", "淡淡地说模板"),
    (r"[这那]一[刻瞬刹].*?[他她时].*?[仿恍].*?[佛然].*?[看明悟]", "那一刻领悟模板"),
    (r"[他她]的.*?[身躯体身].*?[微猛不].*?[微然由].*?[一]?[颤震]", "身躯一颤模板"),
    (r"[一道股阵].*?[强巨恐].*?[大烈怖].*?[的气].*?[息势压].*?[从自].*?[体身内].*?[涌爆冲]", "气息涌出模板"),
    (r"[说话]到.*?[这此]里?.*?[他她].*?[顿停].*?[了一].*?[下顿]", "说到这里顿了模板"),
    (r"此[言话语]一出.*?[众全四].*?[人场周].*?[一俱皆].*?[静惊]", "此言一出众人模板"),
    (r"[他她].*?[嘴唇].*?[动蠕]了[动蠕].*?[终最].*?[究于].*?没有.*?[说开]", "嘴唇蠕动没说模板"),
    (r"[这那].*?[个一].*?[名字词声音].*?[如仿犹].*?[同佛如].*?[一].*?[道记颗].*?[惊闷响]?[雷雨]", "名字如雷模板"),
]


class DeAIEngine:
    """De-AI Engine for detecting and preventing AI-like writing traces."""

    def __init__(self) -> None:
        self._fatigue_words = FATIGUE_WORDS
        self._banned_patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(pattern), name)
            for pattern, name in BANNED_PATTERNS_RAW
        ]

    def get_fatigue_words(self) -> list[str]:
        """Return the full fatigue word list."""
        return list(self._fatigue_words)

    def get_banned_patterns(self) -> list[tuple[re.Pattern, str]]:
        """Return compiled banned patterns with their names."""
        return list(self._banned_patterns)

    def detect(self, text: str) -> list[dict[str, Any]]:
        """Detect AI traces in text. Returns list of trace dicts."""
        traces: list[dict[str, Any]] = []

        # Check fatigue words
        for word in self._fatigue_words:
            start = 0
            while True:
                idx = text.find(word, start)
                if idx == -1:
                    break
                traces.append({
                    "type": "fatigue_word",
                    "matched": word,
                    "start": idx,
                    "end": idx + len(word),
                })
                start = idx + 1

        # Check banned patterns
        for pattern, name in self._banned_patterns:
            for m in pattern.finditer(text):
                traces.append({
                    "type": "banned_pattern",
                    "matched": m.group(),
                    "pattern_name": name,
                    "start": m.start(),
                    "end": m.end(),
                })

        # Sort by position
        traces.sort(key=lambda t: t["start"])
        return traces

    def get_fatigue_density(self, text: str) -> float:
        """Calculate fatigue word density per 1000 characters."""
        if not text:
            return 0.0
        traces = [t for t in self.detect(text) if t["type"] == "fatigue_word"]
        return len(traces) / len(text) * 1000

    def format_for_prompt(
        self, top_words: int = 100, top_patterns: int = 30
    ) -> str:
        """Format fatigue words and banned patterns for LLM prompt injection."""
        lines = ["## 禁止\n"]
        lines.append(f"- 不使用以下词语：{'、'.join(self._fatigue_words[:top_words])}")
        lines.append(f"- 不使用以下句式模板：")
        for _, name in self._banned_patterns[:top_patterns]:
            lines.append(f"  - {name}")
        return "\n".join(lines)
