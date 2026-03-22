# backend/app/engines/rules_engine.py
"""Three-layer rules engine for web novel quality control.

Layer 1: BASE_GUARDRAILS (~25 universal rules)
Layer 2: GENRE_PROFILES (xuanhuan/xianxia/urban presets)
Layer 3: Book-specific custom rules (from DB)
"""

from __future__ import annotations

from typing import Any

# --- Layer 1: Base Guardrails (~25 universal rules) ---
BASE_GUARDRAILS: list[dict[str, str]] = [
    # Character consistency
    {"id": "bg_01", "category": "character", "rule": "性格一致性", "description": "角色行为必须符合已设定的性格特征，不可无故突变"},
    {"id": "bg_02", "category": "character", "rule": "对话个性化", "description": "每个角色的对话风格必须有辨识度，不能千人一面"},
    {"id": "bg_03", "category": "character", "rule": "角色能力边界", "description": "角色能力不可超出已设定的等级/境界限制"},
    {"id": "bg_04", "category": "character", "rule": "角色记忆连续", "description": "角色不应遗忘已经历的重要事件"},
    {"id": "bg_05", "category": "character", "rule": "情感弧线连贯", "description": "角色情感变化需要合理的触发事件和过渡"},
    # Narrative quality
    {"id": "bg_06", "category": "narrative", "rule": "展示不告知", "description": "用场景和行动展示信息，避免直接陈述"},
    {"id": "bg_07", "category": "narrative", "rule": "冲突驱动", "description": "每个场景必须包含至少一个冲突或张力"},
    {"id": "bg_08", "category": "narrative", "rule": "感官细节", "description": "描写必须包含至少两种感官细节（视觉/听觉/触觉/嗅觉/味觉）"},
    {"id": "bg_09", "category": "narrative", "rule": "因果完整", "description": "重要事件必须有合理的因果链，不可凭空出现"},
    {"id": "bg_10", "category": "narrative", "rule": "信息密度", "description": "避免无效灌水，每段必须推进情节或塑造角色"},
    # World consistency
    {"id": "bg_11", "category": "consistency", "rule": "世界观一致", "description": "不得违反已设定的世界规则（力量体系、社会结构等）"},
    {"id": "bg_12", "category": "consistency", "rule": "时间线连贯", "description": "事件发生顺序和时间间隔必须符合逻辑"},
    {"id": "bg_13", "category": "consistency", "rule": "地理一致", "description": "地点描述、距离、方位不可自相矛盾"},
    {"id": "bg_14", "category": "consistency", "rule": "物资连续", "description": "物品、资源的出现和消耗必须有据可查"},
    {"id": "bg_15", "category": "consistency", "rule": "锁定属性不变", "description": "已锁定的角色属性（外貌、背景等）不可随意更改"},
    # Structure
    {"id": "bg_16", "category": "structure", "rule": "伏笔有埋有收", "description": "埋下的伏笔必须在合理范围内回收"},
    {"id": "bg_17", "category": "structure", "rule": "章节三幕结构", "description": "每章应有起承转合的基本结构"},
    {"id": "bg_18", "category": "structure", "rule": "场景目标明确", "description": "每个场景必须有明确的叙事目标"},
    {"id": "bg_19", "category": "structure", "rule": "章尾钩子", "description": "每章结尾应设置悬念或期待，吸引继续阅读"},
    # Style
    {"id": "bg_20", "category": "style", "rule": "禁用疲劳词", "description": "不使用AI疲劳词表中的词语"},
    {"id": "bg_21", "category": "style", "rule": "禁用模板句式", "description": "不使用被标记为AI模板的句式"},
    {"id": "bg_22", "category": "style", "rule": "风格一致", "description": "全文写作风格保持统一，不可忽中忽英或风格突变"},
    {"id": "bg_23", "category": "style", "rule": "避免重复表达", "description": "相邻段落不应重复使用相同的修辞手法或句式结构"},
    # Engagement
    {"id": "bg_24", "category": "engagement", "rule": "每章有爽点", "description": "每章至少包含1个读者爽点（打脸、突破、反转等）"},
    {"id": "bg_25", "category": "engagement", "rule": "悬念维持", "description": "始终保持至少一条未解悬念线"},
]

# --- 33 Audit Dimensions ---
AUDIT_DIMENSIONS: list[dict[str, Any]] = [
    # Consistency (8)
    {"id": 1, "name": "character_setting_conflict", "zh_name": "角色设定冲突", "category": "consistency", "description": "检查角色行为是否违反已设定性格", "is_deterministic": False},
    {"id": 2, "name": "character_memory_violation", "zh_name": "角色记忆违反", "category": "consistency", "description": "检查角色是否遗忘已知事件", "is_deterministic": False},
    {"id": 3, "name": "worldview_violation", "zh_name": "世界观违反", "category": "consistency", "description": "检查是否违反世界设定规则", "is_deterministic": False},
    {"id": 4, "name": "timeline_contradiction", "zh_name": "时间线矛盾", "category": "consistency", "description": "检查时间线是否自洽", "is_deterministic": False},
    {"id": 5, "name": "material_continuity", "zh_name": "物资连续性", "category": "consistency", "description": "物品出现/消耗是否有据", "is_deterministic": True},
    {"id": 6, "name": "geography_contradiction", "zh_name": "地理矛盾", "category": "consistency", "description": "地点、距离、方位是否矛盾", "is_deterministic": False},
    {"id": 7, "name": "locked_attribute_violation", "zh_name": "锁定属性违反", "category": "consistency", "description": "已锁定属性是否被修改", "is_deterministic": True},
    {"id": 8, "name": "logic_contradiction", "zh_name": "前后文逻辑矛盾", "category": "consistency", "description": "前后文是否存在逻辑矛盾", "is_deterministic": False},
    # Narrative (7)
    {"id": 9, "name": "outline_compliance", "zh_name": "大纲遵守度", "category": "narrative", "description": "是否偏离大纲规划", "is_deterministic": False},
    {"id": 10, "name": "scene_goal_completion", "zh_name": "场景目标完成度", "category": "narrative", "description": "场景卡目标是否完成", "is_deterministic": False},
    {"id": 11, "name": "chapter_hook_effectiveness", "zh_name": "章节钩子有效性", "category": "narrative", "description": "章尾是否有有效悬念", "is_deterministic": False},
    {"id": 12, "name": "information_density", "zh_name": "信息密度", "category": "narrative", "description": "是否有无效灌水段落", "is_deterministic": False},
    {"id": 13, "name": "pacing_feel", "zh_name": "节奏感", "category": "narrative", "description": "叙事节奏是否合适", "is_deterministic": False},
    {"id": 14, "name": "suspense_maintenance", "zh_name": "悬念维持", "category": "narrative", "description": "是否维持悬念线", "is_deterministic": False},
    {"id": 15, "name": "dialogue_narration_ratio", "zh_name": "对话/叙述比例", "category": "narrative", "description": "对话与叙述是否平衡", "is_deterministic": False},
    # Character (6)
    {"id": 16, "name": "ooc_detection", "zh_name": "OOC检测", "category": "character", "description": "角色是否Out Of Character", "is_deterministic": False},
    {"id": 17, "name": "character_arc_progression", "zh_name": "角色弧线推进", "category": "character", "description": "角色成长弧线是否推进", "is_deterministic": False},
    {"id": 18, "name": "relationship_evolution", "zh_name": "关系演变合理性", "category": "character", "description": "角色关系变化是否合理", "is_deterministic": False},
    {"id": 19, "name": "dialogue_style_consistency", "zh_name": "对话风格一致性", "category": "character", "description": "角色对话风格是否保持一致", "is_deterministic": False},
    {"id": 20, "name": "emotional_arc_continuity", "zh_name": "情感弧线连贯性", "category": "character", "description": "情感变化是否连贯", "is_deterministic": False},
    {"id": 21, "name": "ability_boundary", "zh_name": "角色能力边界", "category": "character", "description": "角色能力是否越界", "is_deterministic": False},
    # Structure (4)
    {"id": 22, "name": "foreshadowing_balance", "zh_name": "伏笔埋设与回收", "category": "structure", "description": "伏笔是否有埋有收", "is_deterministic": False},
    {"id": 23, "name": "subplot_progress", "zh_name": "支线进度", "category": "structure", "description": "支线剧情是否有推进", "is_deterministic": False},
    {"id": 24, "name": "global_pacing_curve", "zh_name": "全书节奏曲线", "category": "structure", "description": "全局节奏是否合理", "is_deterministic": False},
    {"id": 25, "name": "chapter_three_act", "zh_name": "章节内三幕结构", "category": "structure", "description": "章节是否有起承转合", "is_deterministic": False},
    # Style (4)
    {"id": 26, "name": "ai_trace_detection", "zh_name": "AI痕迹检测", "category": "style", "description": "是否存在AI写作痕迹", "is_deterministic": True},
    {"id": 27, "name": "repetition_detection", "zh_name": "重复表达检测", "category": "style", "description": "是否有重复句式或修辞", "is_deterministic": True},
    {"id": 28, "name": "banned_word_detection", "zh_name": "禁用词句检测", "category": "style", "description": "是否使用禁用词句", "is_deterministic": True},
    {"id": 29, "name": "style_consistency", "zh_name": "风格一致性", "category": "style", "description": "写作风格是否统一", "is_deterministic": False},
    # Engagement (4)
    {"id": 30, "name": "coolpoint_density", "zh_name": "爽点密度", "category": "engagement", "description": "爽点数量是否达标", "is_deterministic": False},
    {"id": 31, "name": "coolpoint_pattern", "zh_name": "爽点模式识别", "category": "engagement", "description": "爽点类型是否多样", "is_deterministic": False},
    {"id": 32, "name": "climax_outline_alignment", "zh_name": "高潮对齐大纲", "category": "engagement", "description": "高潮段落是否对齐大纲规划", "is_deterministic": False},
    {"id": 33, "name": "reader_hook_effectiveness", "zh_name": "读者钩子有效性", "category": "engagement", "description": "章节钩子能否吸引继续阅读", "is_deterministic": False},
]

# --- Layer 2: Genre Profiles ---
GENRE_PROFILES: dict[str, dict[str, Any]] = {
    "xuanhuan": {
        "name": "玄幻",
        "disabled_dimensions": ["dialogue_narration_ratio"],  # 玄幻偏叙述
        "taboos": [
            {"id": "xh_t01", "rule": "禁止现代科技", "description": "不可出现手机、电脑等现代科技产品"},
            {"id": "xh_t02", "rule": "修炼体系一致", "description": "境界划分必须严格遵守已设定体系"},
            {"id": "xh_t03", "rule": "灵力规则不矛盾", "description": "灵力/法力消耗和恢复需遵循设定"},
            {"id": "xh_t04", "rule": "宗门规矩一致", "description": "宗门等级、规矩一经设定不可随意更改"},
        ],
        "settings": {
            "power_system": True,
            "realm_tracking": True,
            "combat_focus": True,
            "romance_weight": 0.1,
            "target_words_per_chapter": 3000,
        },
    },
    "xianxia": {
        "name": "仙侠",
        "disabled_dimensions": ["dialogue_narration_ratio"],
        "taboos": [
            {"id": "xx_t01", "rule": "禁止现代用语", "description": "对话和旁白不可使用现代网络用语"},
            {"id": "xx_t02", "rule": "道法自然", "description": "修炼体系需体现道法自然的哲学观"},
            {"id": "xx_t03", "rule": "天道规则一致", "description": "天道/劫难规则一经设定必须一致"},
            {"id": "xx_t04", "rule": "古风文风", "description": "行文需保持古风韵味，适当使用文言"},
        ],
        "settings": {
            "power_system": True,
            "realm_tracking": True,
            "combat_focus": True,
            "romance_weight": 0.2,
            "target_words_per_chapter": 3000,
            "classical_style": True,
        },
    },
    "urban": {
        "name": "都市",
        "disabled_dimensions": ["global_pacing_curve"],  # 都市节奏更灵活
        "taboos": [
            {"id": "ur_t01", "rule": "现实逻辑", "description": "事件发展需符合现实社会逻辑"},
            {"id": "ur_t02", "rule": "法律常识", "description": "涉及法律的情节不可有常识性错误"},
            {"id": "ur_t03", "rule": "社会关系真实", "description": "人际关系和社会互动需真实可信"},
        ],
        "settings": {
            "power_system": False,
            "realm_tracking": False,
            "combat_focus": False,
            "romance_weight": 0.4,
            "target_words_per_chapter": 2500,
        },
    },
}


class RulesEngine:
    """Three-layer rules engine: base guardrails + genre profile + book rules."""

    def merge(
        self,
        genre: str | None = None,
        book_rules: dict | None = None,
    ) -> dict[str, Any]:
        """Merge three rule layers into a single ruleset.

        Returns dict with keys: guardrails, taboos, custom_rules, settings, disabled_dimensions.
        """
        result: dict[str, Any] = {
            "guardrails": list(BASE_GUARDRAILS),
            "taboos": [],
            "custom_rules": [],
            "settings": {},
            "disabled_dimensions": [],
        }

        # Layer 2: genre profile
        if genre and genre in GENRE_PROFILES:
            profile = GENRE_PROFILES[genre]
            result["taboos"] = list(profile.get("taboos", []))
            result["settings"] = dict(profile.get("settings", {}))
            result["disabled_dimensions"] = list(profile.get("disabled_dimensions", []))

        # Layer 3: book-specific rules
        if book_rules:
            result["custom_rules"] = list(book_rules.get("custom_rules", []))
            # Book-level settings override genre settings
            book_settings = book_rules.get("settings", {})
            result["settings"].update(book_settings)
            # Additional disabled dimensions from book rules
            extra_disabled = book_rules.get("disabled_dimensions", [])
            result["disabled_dimensions"].extend(extra_disabled)

        return result

    def get_active_dimensions(
        self, genre: str | None = None, book_rules: dict | None = None
    ) -> list[dict[str, Any]]:
        """Get active audit dimensions after applying genre/book disabling."""
        merged = self.merge(genre=genre, book_rules=book_rules)
        disabled = set(merged["disabled_dimensions"])
        return [d for d in AUDIT_DIMENSIONS if d["name"] not in disabled]

    def get_deterministic_dimensions(self) -> list[dict[str, Any]]:
        """Get dimensions that can be checked without LLM."""
        return [d for d in AUDIT_DIMENSIONS if d["is_deterministic"]]

    def format_for_prompt(self, merged: dict[str, Any]) -> str:
        """Format merged rules as a string for LLM prompt injection."""
        lines = ["## 规则（必须严格遵守）\n"]

        lines.append("### 基础护栏")
        for g in merged["guardrails"]:
            lines.append(f"- {g['rule']}：{g['description']}")

        if merged["taboos"]:
            lines.append("\n### 题材规则")
            for t in merged["taboos"]:
                lines.append(f"- {t['rule']}：{t['description']}")

        if merged["custom_rules"]:
            lines.append("\n### 本书规则")
            for r in merged["custom_rules"]:
                rule_text = r.get("rule", r.get("id", ""))
                desc = r.get("description", "")
                lines.append(f"- {rule_text}：{desc}" if desc else f"- {rule_text}")

        return "\n".join(lines)
