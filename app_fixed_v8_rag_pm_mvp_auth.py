import os
import re
import time
import json
from typing import Any, Dict, List, Optional

import streamlit as st

# ========= OpenAI SDK =========
# 安装：
# pip install openai
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


# =========================
# 页面基础配置
# =========================
st.set_page_config(
    page_title="AI-HR岗位模拟平台",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# OpenAI 配置
# 优先从环境变量读取；未设置时保留占位
# 不会把 API Key 展示到前端
# =========================
API_KEY = os.getenv("OPENAI_API_KEY", "YOUR_API_KEY")
MODEL_NAME = "gpt-4o"


# =========================
# 页面状态初始化
# =========================
default_states = {
    "page": "home",
    "selected_knowledge_base": None,

    # 岗位模拟试炼场
    "show_role_options": False,
    "selected_role": None,
    "selected_level": None,
    "show_level_options": False,
    "show_confirm_button": False,
    "selection_confirmed": False,
    "can_start_simulation": False,

    # AI模拟页
    "simulation_started": False,
    "current_round": 1,
    "current_scenario": "",
    "history": [],
    "current_scores": None,
    "current_feedback": "",
    "current_suggestion": "",
    "current_follow_up": "",
    "is_finished": False,
    "final_summary": None,
    "answer_input_widget": "",
    "clear_answer_input": False,
    "current_question_started_at": None,
    "authenticity_check_result": None,
    "show_authenticity_warning": False,

    # 登录与用户信息
    "is_logged_in": False,
    "user_name": "",
    "user_age": 0,
    "course_progress": 90,
    "completed_roles": [],
    "simulation_progress": 0,
    "role_scores": {},
    "recommended_role": None,
}

for key, value in default_states.items():
    if key not in st.session_state:
        st.session_state[key] = value

query_params = st.query_params
if "page" in query_params:
    st.session_state.page = query_params["page"]


# =========================
# 页面切换函数
# =========================
def go_home():
    st.session_state.page = "home"
    st.session_state.selected_knowledge_base = None
    st.query_params.clear()


def go_module():
    st.session_state.page = "module"
    st.query_params["page"] = "module"


def go_course():
    st.session_state.page = "course"
    st.session_state.selected_knowledge_base = None
    st.query_params["page"] = "course"


def go_simulation_arena():
    reset_simulation_state()
    st.session_state.page = "simulation_arena"
    st.query_params["page"] = "simulation_arena"


def go_ai_simulation():
    st.session_state.page = "ai_simulation"
    st.query_params["page"] = "ai_simulation"


def go_login():
    st.session_state.page = "login"
    st.query_params["page"] = "login"


def go_user_profile():
    st.session_state.page = "user_profile"
    st.query_params["page"] = "user_profile"


def select_knowledge_base(name: str):
    st.session_state.selected_knowledge_base = name




ALL_ROLES = ["产品岗", "设计岗", "市场岗", "职能岗"]


PM_SCORE_CONFIG = {
    "学习能力": {"weight": 0.10, "desc": "快速适应和更新迭代的能力"},
    "业务/用户洞察力": {"weight": 0.30, "desc": "是否能抓住用户痛点、业务目标和问题本质"},
    "数据能力": {"weight": 0.30, "desc": "是否会用指标拆解问题、验证假设、支持判断"},
    "沟通能力": {"weight": 0.20, "desc": "是否体现跨部门协作、推动落地与信息对齐"},
    "项目经验": {"weight": 0.10, "desc": "是否能结合真实项目或实习经历支撑回答"},
}

DEFAULT_SCORE_ORDER = ["业务理解", "结构化表达", "数据意识", "协同能力", "决策质量"]
PM_SCORE_ORDER = list(PM_SCORE_CONFIG.keys())


def is_pm_beginner_rag(role: Optional[str], level: Optional[str]) -> bool:
    return role == "产品岗" and level == "初级"


def get_score_order(role: Optional[str], level: Optional[str], score_dict: Optional[Dict[str, Any]] = None) -> List[str]:
    if score_dict:
        keys = list(score_dict.keys())
        if keys == PM_SCORE_ORDER or set(keys) == set(PM_SCORE_ORDER):
            return PM_SCORE_ORDER
        if keys == DEFAULT_SCORE_ORDER or set(keys) == set(DEFAULT_SCORE_ORDER):
            return DEFAULT_SCORE_ORDER
        return keys
    if is_pm_beginner_rag(role, level):
        return PM_SCORE_ORDER
    return DEFAULT_SCORE_ORDER


def compute_total_score(score_dict: Dict[str, int], role: Optional[str] = None, level: Optional[str] = None) -> int:
    """将五维评分汇总为百分制附近的演示分数。"""
    if not score_dict:
        return 0

    if is_pm_beginner_rag(role, level) and set(score_dict.keys()) == set(PM_SCORE_ORDER):
        weighted_total = 0.0
        for dim, cfg in PM_SCORE_CONFIG.items():
            weighted_total += int(score_dict.get(dim, 0)) * cfg["weight"]
        return int(round(weighted_total * 20))

    raw_total = sum(int(v) for v in score_dict.values())
    return raw_total * 4


def update_simulation_progress_and_recommendation():
    completed_roles = st.session_state.get("completed_roles", [])
    unique_roles = [role for role in ALL_ROLES if role in completed_roles]
    st.session_state.completed_roles = unique_roles
    st.session_state.simulation_progress = min(len(unique_roles) * 25, 100)

    role_scores = st.session_state.get("role_scores", {})
    if st.session_state.simulation_progress == 100 and role_scores:
        valid_scores = {role: score for role, score in role_scores.items() if role in ALL_ROLES}
        if len(valid_scores) == 4:
            st.session_state.recommended_role = max(valid_scores, key=valid_scores.get)
        else:
            st.session_state.recommended_role = None
    else:
        st.session_state.recommended_role = None


def mark_role_completed(role_name: str, score: Optional[int] = None):
    """在 AI 模拟结束后回写岗位完成状态与得分。"""
    if not role_name:
        return

    if role_name not in st.session_state.completed_roles:
        st.session_state.completed_roles.append(role_name)

    if score is not None:
        st.session_state.role_scores[role_name] = score

    update_simulation_progress_and_recommendation()


def mock_wechat_login():
    """模拟微信授权登录并生成假用户信息。"""
    st.session_state.is_logged_in = True
    st.session_state.user_name = "刘同学"
    st.session_state.user_age = 23
    st.session_state.course_progress = 90
    if "completed_roles" not in st.session_state:
        st.session_state.completed_roles = []
    if "role_scores" not in st.session_state:
        st.session_state.role_scores = {}
    update_simulation_progress_and_recommendation()

# =========================
# 岗位模拟试炼场状态函数
# =========================
def reset_simulation_state():
    st.session_state.show_role_options = False
    st.session_state.selected_role = None
    st.session_state.selected_level = None
    st.session_state.show_level_options = False
    st.session_state.show_confirm_button = False
    st.session_state.selection_confirmed = False
    st.session_state.can_start_simulation = False
    reset_ai_simulation_state()


def handle_role_select(role_name: str):
    st.session_state.selected_role = role_name
    st.session_state.selected_level = None
    st.session_state.show_level_options = True
    st.session_state.show_confirm_button = False
    st.session_state.selection_confirmed = False
    st.session_state.can_start_simulation = False
    reset_ai_simulation_state()


def handle_level_select(level_name: str):
    st.session_state.selected_level = level_name
    st.session_state.show_confirm_button = True
    st.session_state.selection_confirmed = False
    st.session_state.can_start_simulation = False
    reset_ai_simulation_state()


def confirm_simulation_selection():
    if st.session_state.selected_role and st.session_state.selected_level:
        st.session_state.selection_confirmed = True
        st.session_state.can_start_simulation = True


# =========================
# AI模拟页状态函数
# =========================
def reset_ai_simulation_state():
    st.session_state.simulation_started = False
    st.session_state.current_round = 1
    st.session_state.current_scenario = ""
    st.session_state.history = []
    st.session_state.current_scores = None
    st.session_state.current_feedback = ""
    st.session_state.current_suggestion = ""
    st.session_state.current_follow_up = ""
    st.session_state.is_finished = False
    st.session_state.final_summary = None
    st.session_state.answer_input_widget = ""
    st.session_state.clear_answer_input = False
    st.session_state.current_question_started_at = None
    st.session_state.authenticity_check_result = None
    st.session_state.show_authenticity_warning = False


# =========================
# OpenAI 工具函数
# =========================
def get_openai_client() -> Optional[OpenAI]:
    """创建 OpenAI 客户端。"""
    if OpenAI is None:
        return None

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key == "YOUR_API_KEY":
        return None

    try:
        return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"OpenAI 客户端初始化失败：{repr(e)}")
        return None


# =========================
# 产品岗 RAG MVP（仅产品岗 + 初级）
# =========================
PM_RAG_KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    {
        "id": "pm_q_001",
        "role": "产品岗",
        "difficulty": "初级",
        "category": "project_intro",
        "question_title": "介绍一个你做得比较好的项目",
        "keywords": ["项目", "介绍", "亮点", "结果", "STAR", "背景", "任务", "行动", "结果"],
        "interviewer_intent": "考察候选人能否挑选与岗位匹配的项目，并用结构化方式讲清背景、任务、行动和结果。",
        "answer_framework": [
            "先交代业务背景和问题",
            "说明自己承担的核心任务",
            "拆解关键行动和协作方式",
            "补充结果数据和个人贡献"
        ],
        "sample_answer": "回答项目题时，要优先选择与产品岗位匹配、结果或复杂度有亮点的项目，并用 STAR 法则讲清楚。",
        "scenario_seed": "你所在团队准备上线一个新功能，但用户使用率一直偏低。请你从背景、分析、方案和推进方式四个部分说明你会怎么做。",
        "score_tags": ["业务/用户洞察力", "数据能力", "沟通能力", "项目经验"]
    },
    {
        "id": "pm_q_002",
        "role": "产品岗",
        "difficulty": "初级",
        "category": "bad_project_review",
        "question_title": "说一个你觉得做得不够好的项目",
        "keywords": ["复盘", "迭代", "问题", "失败", "不好", "改进"],
        "interviewer_intent": "考察候选人的复盘迭代能力，是否能发现问题、分析原因并推动修正。",
        "answer_framework": [
            "说明项目背景和目标",
            "指出真实但非致命的问题",
            "解释如何定位原因并推动修正",
            "说明修正后的结果和复盘收获"
        ],
        "sample_answer": "面试官真正想听到的是：你发现问题、思考问题，并最终把问题解决了。",
        "scenario_seed": "你负责跟进的一个功能上线后，核心指标没有达到预期。请你说明你会如何定位原因，并推动下一轮迭代。",
        "score_tags": ["学习能力", "数据能力", "沟通能力", "项目经验"]
    },
    {
        "id": "pm_q_003",
        "role": "产品岗",
        "difficulty": "初级",
        "category": "hard_problem",
        "question_title": "你做过最难的事情是什么",
        "keywords": ["困难", "挑战", "复杂问题", "推进", "主导", "跨部门"],
        "interviewer_intent": "考察候选人能否处理复杂问题、扛住压力，并在推进中承担主导角色。",
        "answer_framework": [
            "定义困难来自哪里",
            "说明自己在其中承担的责任",
            "拆解推进过程中的关键动作",
            "说明问题如何被解决以及结果"
        ],
        "sample_answer": "难点题要有层层推导过程，不能一步到位，需要体现候选人的主导性和解决复杂问题的能力。",
        "scenario_seed": "一个跨部门需求卡在研发、运营和业务三方之间，推进效率很低。请你说明你会怎么推动项目继续往前走。",
        "score_tags": ["沟通能力", "学习能力", "项目经验"]
    },
    {
        "id": "pm_q_004",
        "role": "产品岗",
        "difficulty": "初级",
        "category": "pm_understanding",
        "question_title": "你怎么理解产品经理",
        "keywords": ["产品经理", "理解", "职责", "价值", "岗位认知", "用户"],
        "interviewer_intent": "考察候选人是否理解产品经理的核心价值、工作方式和职业动机。",
        "answer_framework": [
            "用一句话概括产品经理的价值",
            "说明典型工作内容，如需求分析、跨部门协作、推动上线",
            "结合个人经历说明为什么适合做产品"
        ],
        "sample_answer": "优秀回答通常会覆盖价值、职责和职业动机三部分，而不是只背定义。",
        "scenario_seed": "如果你接手一个用户投诉较多的功能，请说明产品经理在这个过程中应该扮演什么角色，以及你会先做什么。",
        "score_tags": ["业务/用户洞察力", "沟通能力", "学习能力"]
    },
    {
        "id": "pm_q_005",
        "role": "产品岗",
        "difficulty": "初级",
        "category": "open_business_case",
        "question_title": "开放题：这个业务给你该怎么办",
        "keywords": ["开放题", "业务", "策略", "用户", "竞品", "市场", "方案"],
        "interviewer_intent": "考察候选人入职后能否快速理解业务、拆解问题并提出可执行方案。",
        "answer_framework": [
            "先明确业务目标和用户群体",
            "拆解现状问题和关键约束",
            "提出分阶段方案",
            "给出验证指标和落地路径"
        ],
        "sample_answer": "开放题没有标准答案，关键是让面试官觉得你的分析有逻辑、有依据、值得一试。",
        "scenario_seed": "某内容社区的新用户次日留存持续走低，团队希望你给出初步改进方案。请你说明你会如何拆解这个问题，并给出优先级最高的动作。",
        "score_tags": ["业务/用户洞察力", "数据能力", "沟通能力"]
    },
    {
        "id": "pm_q_006",
        "role": "产品岗",
        "difficulty": "初级",
        "category": "self_intro",
        "question_title": "请做一个简单的自我介绍",
        "keywords": ["自我介绍", "经历", "标签", "匹配", "引导", "结果"],
        "interviewer_intent": "考察候选人是否能快速建立与岗位匹配的人设标签，并用结果证明自己。",
        "answer_framework": [
            "提炼与岗位相关的经历标签",
            "突出一到两个可量化结果",
            "自然引导到更能体现优势的项目"
        ],
        "sample_answer": "好的自我介绍不是流水账，而是岗位匹配标签、结果数据和引导面试官提问的组合。",
        "scenario_seed": "你需要在 3 分钟内向面试官介绍自己，并突出自己适合产品岗的原因。请说明你会如何组织这段表达。",
        "score_tags": ["沟通能力", "项目经验", "学习能力"]
    },
    {
        "id": "pm_q_007",
        "role": "产品岗",
        "difficulty": "初级",
        "category": "career_plan",
        "question_title": "未来的职业规划是什么",
        "keywords": ["职业规划", "稳定性", "深耕", "发展", "长期"],
        "interviewer_intent": "考察候选人是否愿意在相关方向深耕，以及职业规划是否与岗位方向一致。",
        "answer_framework": [
            "说明自己对产品方向的兴趣和理由",
            "体现愿意持续学习和沉淀",
            "避免过于空泛或频繁跳方向"
        ],
        "sample_answer": "职业规划题的重点不是说得多远，而是让面试官相信你会在这个方向持续投入。",
        "scenario_seed": "如果面试官问你为什么想长期走产品方向，你会如何把个人经历、学习意愿和岗位理解串起来回答？",
        "score_tags": ["学习能力", "项目经验"]
    },
    {
        "id": "pm_q_008",
        "role": "产品岗",
        "difficulty": "初级",
        "category": "strengths",
        "question_title": "你的优点是什么",
        "keywords": ["优点", "能力", "证明", "论据", "逻辑", "岗位匹配"],
        "interviewer_intent": "考察候选人是否知道岗位需要什么能力，并能用真实例子证明自己的优势。",
        "answer_framework": [
            "只说与产品岗匹配的优点",
            "每个优点都要有具体论据或项目支撑",
            "避免空泛形容词"
        ],
        "sample_answer": "说优点时，关键不是列词，而是把优点和岗位要求一一对应，并给出证据。",
        "scenario_seed": "如果你要证明自己适合做产品岗，你会优先强调哪两项能力？请结合具体经历说明。",
        "score_tags": ["项目经验", "沟通能力", "业务/用户洞察力"]
    },
]


def normalize_query_text(text: str) -> str:
    return (text or "").replace("\n", " ").strip().lower()


def retrieve_pm_rag_knowledge(query: str, task_type: str = "evaluation", top_k: int = 4) -> List[Dict[str, Any]]:
    normalized = normalize_query_text(query)
    results: List[Dict[str, Any]] = []

    for item in PM_RAG_KNOWLEDGE_BASE:
        score = 0.0

        for kw in item.get("keywords", []):
            if kw.lower() in normalized:
                score += 3

        if task_type == "generation":
            if item["category"] in {"project_intro", "open_business_case", "bad_project_review", "hard_problem", "pm_understanding"}:
                score += 2
        elif task_type == "follow_up":
            if item["category"] in {"project_intro", "bad_project_review", "hard_problem", "open_business_case"}:
                score += 1.5
        else:
            if item["category"] in {"project_intro", "bad_project_review", "open_business_case", "pm_understanding"}:
                score += 1.5

        if "用户" in normalized and "业务/用户洞察力" in item.get("score_tags", []):
            score += 2
        if "数据" in normalized and "数据能力" in item.get("score_tags", []):
            score += 2
        if any(k in normalized for k in ["协作", "沟通", "推进", "跨部门"]) and "沟通能力" in item.get("score_tags", []):
            score += 2

        if score > 0:
            results.append({**item, "_score": score})

    if not results:
        defaults = ["pm_q_005", "pm_q_001", "pm_q_002", "pm_q_004"]
        results = [{**item, "_score": float(len(defaults)-idx)} for idx, item in enumerate(PM_RAG_KNOWLEDGE_BASE) if item["id"] in defaults]

    results = sorted(results, key=lambda x: x["_score"], reverse=True)
    return results[:top_k]


def format_rag_context(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "暂无可用知识。"
    parts = []
    for idx, item in enumerate(items, start=1):
        framework = "；".join(item.get("answer_framework", []))
        tags = "、".join(item.get("score_tags", []))
        parts.append(
            f"[参考知识{idx}]\n"
            f"题型：{item.get('question_title', '')}\n"
            f"面试官真实考察：{item.get('interviewer_intent', '')}\n"
            f"回答框架：{framework}\n"
            f"可迁移场景种子：{item.get('scenario_seed', '')}\n"
            f"重点评分维度：{tags}\n"
        )
    return "\n".join(parts)


def build_pm_beginner_assessor_prompt() -> str:
    score_desc = "\n".join(
        [f"- {dim}（权重 {int(cfg['weight'] * 100)}%）：{cfg['desc']}" for dim, cfg in PM_SCORE_CONFIG.items()]
    )
    return f"""
你是“产品岗初级面试评估官”，服务于 AI-HR 岗位模拟平台的产品岗初级难度。

你的任务：
1. 参考检索到的产品经理面试知识，生成真实、初级可答的业务场景题。
2. 基于产品岗五维能力模型进行严格评分。
3. 给出专业、具体、可执行的反馈与追问。
4. 整个风格要像真实校招/实习产品面试官，避免空泛夸奖。

固定评分维度（1-5 分整数）：
{score_desc}

强约束：
- 输出必须基于候选人的真实回答，不要编造候选人没说过的内容。
- 五个分数不允许全部相同，至少要体现明显高低差异。
- 初级产品岗更看重：用户/业务洞察、数据意识、沟通推进、复盘学习。
- 题目必须贴近真实业务，不要变成纯理论八股题。
- feedback、suggestion、follow_up_question 都要简洁专业，且和回答短板直接对应。
- follow_up_question 必须只问 1 个问题，并且能够继续考察候选人的短板。
"""


def generate_first_scenario_with_rag(role: str, level: str) -> str:
    retrieved = retrieve_pm_rag_knowledge("产品岗 初级 用户洞察 数据分析 协作 项目经验", task_type="generation", top_k=4)
    rag_context = format_rag_context(retrieved)
    developer_prompt = build_pm_beginner_assessor_prompt()
    user_prompt = f"""
请基于以下检索到的知识，为“产品岗 + 初级”生成第一轮业务模拟题。

检索知识：
{rag_context}

输出要求：
1. 只输出一个真实、完整、可作答的业务场景题。
2. 题目更偏校招/实习产品岗，不能要求过高的管理经验。
3. 场景要包含：背景、目标、约束或判断要求。
4. 优先考察：业务/用户洞察力、数据能力、沟通能力。
5. 题目适合候选人用 150-400 字作答。
6. 不要直接照搬参考知识原文，要生成一条新的真实场景题。
"""
    result = chat_completion_json(FIRST_SCENARIO_SCHEMA, developer_prompt, user_prompt)
    return result["scenario"]




AUTHENTICITY_CHECK_SCHEMA = {
    "name": "authenticity_check_schema",
    "schema": {
        "type": "object",
        "properties": {
            "ai_probability": {"type": "integer", "minimum": 0, "maximum": 100},
            "relevance_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "detail_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "template_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "reason": {"type": "string"},
            "rewrite_tip": {"type": "string"},
            "risk_flags": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 5
            }
        },
        "required": [
            "ai_probability",
            "relevance_score",
            "detail_score",
            "template_score",
            "reason",
            "rewrite_tip",
            "risk_flags"
        ],
        "additionalProperties": False
    }
}


SUSPECT_TEMPLATE_PHRASES = [
    "首先", "其次", "最后", "综上所述", "总的来说", "一方面", "另一方面",
    "为了", "通过", "基于以上分析", "从而实现", "赋能", "抓手", "闭环",
    "方法论", "落地", "协同推进", "最终达成", "用户价值", "商业价值"
]


def count_matches(text: str, patterns: List[str]) -> int:
    return sum(text.count(pattern) for pattern in patterns if pattern)


def estimate_response_seconds(start_ts: Optional[float]) -> Optional[float]:
    if not start_ts:
        return None
    return max(time.time() - float(start_ts), 0.0)


def build_rule_based_authenticity_signals(answer: str, question: str, response_seconds: Optional[float]) -> Dict[str, Any]:
    clean_answer = answer.strip()
    char_count = len(clean_answer)
    sentence_count = max(len([s for s in re.split(r"[。！？!?\n]", clean_answer) if s.strip()]), 1)
    digit_count = len(re.findall(r"\d", clean_answer))
    template_hits = count_matches(clean_answer, SUSPECT_TEMPLATE_PHRASES)
    first_person_hits = count_matches(clean_answer, ["我", "我们", "当时", "后来", "这个项目", "这次实习", "在浪潮", "在华福", "我负责", "我做了"])
    action_hits = count_matches(clean_answer, ["分析", "拆解", "验证", "推进", "协调", "沟通", "复盘", "监控", "优化", "调研", "访谈", "上线"])
    keyword_overlap = 0
    question_keywords = [kw for kw in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", question) if len(kw) >= 2]
    for kw in set(question_keywords):
        if kw in clean_answer:
            keyword_overlap += 1

    chars_per_second = None
    if response_seconds and response_seconds > 0:
        chars_per_second = round(char_count / response_seconds, 2)

    speed_risk = 0
    if chars_per_second is not None:
        if char_count >= 220 and chars_per_second >= 6.5:
            speed_risk = 28
        elif char_count >= 160 and chars_per_second >= 5.0:
            speed_risk = 18
        elif chars_per_second >= 4.0:
            speed_risk = 8

    template_risk = min(template_hits * 6, 30)
    short_or_sparse_risk = 0
    if char_count < 80:
        short_or_sparse_risk += 25
    elif char_count < 120:
        short_or_sparse_risk += 12

    if digit_count == 0:
        short_or_sparse_risk += 8
    if first_person_hits <= 1:
        short_or_sparse_risk += 14
    if action_hits <= 2:
        short_or_sparse_risk += 8
    if keyword_overlap <= 1:
        short_or_sparse_risk += 12

    detail_score = max(0, min(100, 30 + digit_count * 8 + first_person_hits * 10 + action_hits * 6 - template_hits * 4))
    relevance_score = max(0, min(100, 35 + keyword_overlap * 12 + min(action_hits, 4) * 4))
    template_score = max(0, min(100, 20 + template_hits * 12 - first_person_hits * 4))
    rule_ai_risk = max(0, min(100, speed_risk + template_risk + short_or_sparse_risk + max(0, 40 - detail_score) // 2))

    risk_flags: List[str] = []
    if chars_per_second is not None and chars_per_second >= 5.0 and char_count >= 160:
        risk_flags.append("作答速度与文本长度组合偏异常")
    if template_hits >= 4:
        risk_flags.append("表达较模板化")
    if detail_score < 45:
        risk_flags.append("个人经历与动作细节不足")
    if relevance_score < 55:
        risk_flags.append("与题目贴合度不足")
    if digit_count == 0:
        risk_flags.append("缺少数据或结果支撑")
    if not risk_flags:
        risk_flags.append("未发现明显高风险信号")

    return {
        "char_count": char_count,
        "sentence_count": sentence_count,
        "digit_count": digit_count,
        "template_hits": template_hits,
        "first_person_hits": first_person_hits,
        "action_hits": action_hits,
        "keyword_overlap": keyword_overlap,
        "chars_per_second": chars_per_second,
        "speed_risk": speed_risk,
        "detail_score": detail_score,
        "relevance_score": relevance_score,
        "template_score": template_score,
        "rule_ai_risk": rule_ai_risk,
        "risk_flags": risk_flags[:5]
    }


def check_answer_authenticity(answer: str, question: str, response_seconds: Optional[float]) -> Dict[str, Any]:
    rule_signals = build_rule_based_authenticity_signals(answer, question, response_seconds)

    llm_result = {
        "ai_probability": rule_signals["rule_ai_risk"],
        "relevance_score": rule_signals["relevance_score"],
        "detail_score": rule_signals["detail_score"],
        "template_score": rule_signals["template_score"],
        "reason": "已使用规则信号进行本地校验。",
        "rewrite_tip": "请补充你的真实项目背景、具体动作、判断依据和数据结果。",
        "risk_flags": rule_signals["risk_flags"]
    }

    client = get_openai_client()
    if client is not None:
        developer_prompt = """你是一个中文招聘场景下的文本真实性校验助手。
你的任务不是断言文本一定由 AI 生成，而是判断“这段回答是否疑似过度依赖 AI、模板化严重、缺少真实个人细节”。
请谨慎判断，避免把正常、逻辑清楚的人类回答误判为 AI。
请重点关注：是否贴题、是否有真实动作链路、是否有项目细节、是否有个体表达痕迹、是否过于模板化。"""
        user_prompt = f"""请评估下面这段产品岗面试回答的真实性风险，并返回 JSON。

当前题目：{question}
候选人回答：{answer}
作答耗时（秒）：{"未知" if response_seconds is None else round(response_seconds, 1)}

规则信号：
- 字数：{rule_signals['char_count']}
- 句子数：{rule_signals['sentence_count']}
- 数字个数：{rule_signals['digit_count']}
- 模板短语命中：{rule_signals['template_hits']}
- 第一人称/个人经历表达命中：{rule_signals['first_person_hits']}
- 动作类词命中：{rule_signals['action_hits']}
- 与题目关键词重合：{rule_signals['keyword_overlap']}
- 每秒字符数：{rule_signals['chars_per_second']}

评分含义：
- ai_probability：0-100，越高代表越像过度依赖 AI 或强模板化文本
- relevance_score：0-100，越高代表越贴题
- detail_score：0-100，越高代表越有真实细节
- template_score：0-100，越高代表越模板化

要求：
1. 请谨慎，不能仅因条理清晰就判为 AI。
2. 如果文本里有真实项目动作、数据、个人决策痕迹，应降低 ai_probability。
3. rewrite_tip 要明确告诉候选人怎样重写才能更真实。
4. risk_flags 给出 1-5 条简短中文提示。"""
        try:
            llm_result = chat_completion_json(AUTHENTICITY_CHECK_SCHEMA, developer_prompt, user_prompt)
        except Exception:
            llm_result = llm_result

    final_ai_probability = int(round(llm_result["ai_probability"] * 0.55 + rule_signals["rule_ai_risk"] * 0.45))
    final_relevance = int(round(llm_result["relevance_score"] * 0.7 + rule_signals["relevance_score"] * 0.3))
    final_detail = int(round(llm_result["detail_score"] * 0.7 + rule_signals["detail_score"] * 0.3))
    final_template = int(round(llm_result["template_score"] * 0.7 + rule_signals["template_score"] * 0.3))

    merged_flags = []
    for item in llm_result.get("risk_flags", []) + rule_signals.get("risk_flags", []):
        if item and item not in merged_flags:
            merged_flags.append(item)

    is_valid = final_ai_probability < 30 and final_relevance >= 55 and final_detail >= 35
    if not is_valid:
        warning_message = f"检测到本次回答的 AI 风险偏高或真实性不足（综合风险 {final_ai_probability}%）。本轮回答暂不计入有效作答，请结合真实经历重新回答。"
    else:
        warning_message = "本次回答已通过基础真实性校验。"

    return {
        "is_valid": is_valid,
        "final_ai_probability": final_ai_probability,
        "relevance_score": final_relevance,
        "detail_score": final_detail,
        "template_score": final_template,
        "reason": llm_result.get("reason", ""),
        "rewrite_tip": llm_result.get("rewrite_tip", "请补充你的真实项目细节和判断依据。"),
        "risk_flags": merged_flags[:5],
        "rule_signals": rule_signals,
        "warning_message": warning_message,
        "response_seconds": None if response_seconds is None else round(response_seconds, 1)
    }


def render_authenticity_warning_box():
    result = st.session_state.get("authenticity_check_result")
    if not st.session_state.get("show_authenticity_warning") or not result:
        return

    risk_html = "".join([f"<li>{flag}</li>" for flag in result.get("risk_flags", [])])
    st.markdown(f"""
<div style="border:1.5px solid #ffb3b3;border-radius:18px;padding:18px 20px;background:linear-gradient(180deg,#fff5f5 0%,#fff 100%);box-shadow:0 8px 24px rgba(255,90,90,0.08);margin:10px 0 18px 0;">
  <div style="font-size:20px;font-weight:700;color:#c62828;margin-bottom:10px;">⚠️ 回答未通过真实性校验</div>
  <div style="font-size:15px;color:#333;line-height:1.8;">{result.get('warning_message','')}</div>
  <div style="margin-top:10px;font-size:14px;color:#555;line-height:1.8;">
    <b>综合 AI 风险：</b>{result.get('final_ai_probability', 0)}%<br>
    <b>贴题度：</b>{result.get('relevance_score', 0)} / 100 &nbsp; | &nbsp;
    <b>细节真实性：</b>{result.get('detail_score', 0)} / 100 &nbsp; | &nbsp;
    <b>模板化程度：</b>{result.get('template_score', 0)} / 100
  </div>
  <div style="margin-top:10px;font-size:14px;color:#555;">
    <b>主要风险信号：</b>
    <ul style="margin:8px 0 0 18px;">{risk_html}</ul>
  </div>
  <div style="margin-top:10px;font-size:14px;color:#555;line-height:1.8;"><b>重答建议：</b>{result.get('rewrite_tip','请结合真实经历重新作答。')}</div>
</div>
""", unsafe_allow_html=True)
    btn_left, btn_mid, btn_right = st.columns([2.5, 2.0, 2.5])
    with btn_mid:
        if st.button("我知道了，重新作答", use_container_width=True, key="dismiss_auth_warning_btn"):
            st.session_state.show_authenticity_warning = False
            st.rerun()


PM_EVAL_SCHEMA = {
    "name": "pm_beginner_eval_schema",
    "schema": {
        "type": "object",
        "properties": {
            "scores": {
                "type": "object",
                "properties": {
                    "学习能力": {"type": "integer", "minimum": 1, "maximum": 5},
                    "业务/用户洞察力": {"type": "integer", "minimum": 1, "maximum": 5},
                    "数据能力": {"type": "integer", "minimum": 1, "maximum": 5},
                    "沟通能力": {"type": "integer", "minimum": 1, "maximum": 5},
                    "项目经验": {"type": "integer", "minimum": 1, "maximum": 5}
                },
                "required": ["学习能力", "业务/用户洞察力", "数据能力", "沟通能力", "项目经验"],
                "additionalProperties": False
            },
            "feedback": {"type": "string"},
            "suggestion": {"type": "string"},
            "follow_up_question": {"type": "string"},
            "is_finished": {"type": "boolean"},
            "final_summary": {
                "type": "object",
                "properties": {
                    "recommended_direction": {"type": "string"},
                    "strengths": {"type": "string"},
                    "improvements": {"type": "string"}
                },
                "required": ["recommended_direction", "strengths", "improvements"],
                "additionalProperties": False
            }
        },
        "required": [
            "scores",
            "feedback",
            "suggestion",
            "follow_up_question",
            "is_finished",
            "final_summary"
        ],
        "additionalProperties": False
    }
}


def evaluate_answer_and_get_next_with_rag(
    role: str,
    level: str,
    current_round: int,
    current_scenario: str,
    user_answer: str,
    history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    history_text = build_history_text(history)
    will_finish = current_round >= 3
    retrieval_query = f"{current_scenario}\n{user_answer}"
    task_type = "evaluation" if current_round == 1 else "follow_up"
    retrieved = retrieve_pm_rag_knowledge(retrieval_query, task_type=task_type, top_k=4)
    rag_context = format_rag_context(retrieved)
    score_desc = "\n".join(
        [f"- {dim}：{cfg['desc']}（权重 {int(cfg['weight'] * 100)}%）" for dim, cfg in PM_SCORE_CONFIG.items()]
    )

    developer_prompt = build_pm_beginner_assessor_prompt()
    user_prompt = f"""
现在请你作为“产品岗初级面试评估官”，基于候选人的本轮回答进行评分，并返回 JSON。

岗位：{role}
难度：{level}
当前轮次：第{current_round}轮（共3轮）
当前题目：{current_scenario}
候选人回答：{user_answer}

历史记录：
{history_text}

检索到的参考知识：
{rag_context}

评分标准：
{score_desc}

输出要求：
1. 必须按五个维度分别给出 1-5 分整数分。
2. feedback 先总结整体表现，再明确指出最主要短板。
3. suggestion 必须给出 1-2 条可执行建议，优先围绕最主要短板。
4. 如未结束，follow_up_question 只能追问一个问题，且要基于本轮短板继续深挖。
5. 如当前为最后一轮，is_finished = true，follow_up_question 可写“本轮已结束”，并输出 final_summary。
6. 如未结束，is_finished = false，final_summary 也要返回完整字段，但可以简洁。
7. 优秀回答通常应体现：对用户或业务问题的理解、数据验证思路、跨部门推进意识，以及真实项目支撑。
8. 如果候选人回答偏空泛、缺少案例或数据，请明确扣到对应维度，不要给高分。
9. 当前轮次是否最后一轮：{"是" if will_finish else "否"}。
"""
    return chat_completion_json(PM_EVAL_SCHEMA, developer_prompt, user_prompt)


def generate_scenario_entry(role: str, level: str) -> str:
    if is_pm_beginner_rag(role, level):
        return generate_first_scenario_with_rag(role, level)
    return generate_first_scenario(role, level)


def evaluate_answer_entry(
    role: str,
    level: str,
    current_round: int,
    current_scenario: str,
    user_answer: str,
    history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    if is_pm_beginner_rag(role, level):
        return evaluate_answer_and_get_next_with_rag(role, level, current_round, current_scenario, user_answer, history)
    return evaluate_answer_and_get_next(role, level, current_round, current_scenario, user_answer, history)


def build_assessor_prompt() -> str:
    """企业轮岗评估官系统设定。"""
    return """
你是“企业轮岗评估官”，负责为企业候选人提供真实、专业、可执行的岗位模拟训练与评估。

你的任务：
1. 根据给定岗位与难度生成真实业务场景题。
2. 根据用户回答进行严格评分与分析。
3. 给出简洁、专业、可执行的反馈。
4. 在每轮结束后给出下一轮追问。
5. 在最后一轮输出总结报告。

评分规则必须严格执行：
- 评分维度：
  - 业务理解
  - 结构化表达
  - 数据意识
  - 协同能力
  - 决策质量
- 每个维度为 1-5 分整数。
- 不允许五个维度全部相同。
- 至少体现出明显高低差异。
- 必须根据用户真实回答打分，不能空泛夸奖。

风格要求：
- 语言专业、简洁、像企业轮岗评估官。
- 题目要真实、贴近岗位工作场景。
- 反馈要可执行，避免套话。
- 若用户回答泛泛而谈，应明确指出问题。
"""


def build_history_text(history: List[Dict[str, Any]]) -> str:
    """将历史记录拼成文本，供模型理解上下文。"""
    if not history:
        return "暂无历史记录。"
    lines = []
    for item in history:
        lines.append(f"轮次：第{item.get('round')}轮")
        lines.append(f"题目：{item.get('scenario')}")
        lines.append(f"用户回答：{item.get('answer')}")
        feedback = item.get("feedback", "")
        if feedback:
            lines.append(f"AI反馈：{feedback}")
        follow = item.get("follow_up_question", "")
        if follow:
            lines.append(f"下一轮追问：{follow}")
        lines.append("----")
    return "\n".join(lines)


FIRST_SCENARIO_SCHEMA = {
    "name": "first_scenario_schema",
    "schema": {
        "type": "object",
        "properties": {
            "scenario": {
                "type": "string",
                "description": "第一轮业务模拟题目，必须是完整、可作答的真实业务场景题。"
            }
        },
        "required": ["scenario"],
        "additionalProperties": False
    }
}

EVAL_SCHEMA = {
    "name": "simulation_eval_schema",
    "schema": {
        "type": "object",
        "properties": {
            "scores": {
                "type": "object",
                "properties": {
                    "业务理解": {"type": "integer", "minimum": 1, "maximum": 5},
                    "结构化表达": {"type": "integer", "minimum": 1, "maximum": 5},
                    "数据意识": {"type": "integer", "minimum": 1, "maximum": 5},
                    "协同能力": {"type": "integer", "minimum": 1, "maximum": 5},
                    "决策质量": {"type": "integer", "minimum": 1, "maximum": 5}
                },
                "required": ["业务理解", "结构化表达", "数据意识", "协同能力", "决策质量"],
                "additionalProperties": False
            },
            "feedback": {"type": "string"},
            "suggestion": {"type": "string"},
            "follow_up_question": {"type": "string"},
            "is_finished": {"type": "boolean"},
            "final_summary": {
                "type": "object",
                "properties": {
                    "recommended_direction": {"type": "string"},
                    "strengths": {"type": "string"},
                    "improvements": {"type": "string"}
                },
                "required": ["recommended_direction", "strengths", "improvements"],
                "additionalProperties": False
            }
        },
        "required": [
            "scores",
            "feedback",
            "suggestion",
            "follow_up_question",
            "is_finished",
            "final_summary"
        ],
        "additionalProperties": False
    }
}


def chat_completion_json(schema: Dict[str, Any], developer_prompt: str, user_prompt: str) -> Dict[str, Any]:
    """调用 OpenAI Chat Completions，并用 json_schema 约束结构化输出。"""
    client = get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI 客户端初始化失败。请检查 openai 是否已安装，以及 OPENAI_API_KEY 是否已正确设置。")

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema["name"],
                    "schema": schema["schema"],
                    "strict": True
                }
            },
            temperature=0.7
        )
    except Exception as e:
        import traceback
        st.error(f"OpenAI 请求失败：{e}")
        st.code(traceback.format_exc())
        raise

    content = response.choices[0].message.content
    return json.loads(content)


def generate_first_scenario(role: str, level: str) -> str:
    """生成第一轮场景题。"""
    developer_prompt = build_assessor_prompt()
    user_prompt = f"""
请为以下模拟训练生成第一道真实业务场景题：

岗位：{role}
难度：{level}
轮次：第1轮（共3轮）

要求：
1. 只输出一个适合该岗位和难度的真实业务场景题。
2. 题目必须有明确背景、任务目标、限制条件或判断要求。
3. 题目应适合候选人用 150-400 字作答。
4. 不要输出答案，不要输出评分。
"""
    result = chat_completion_json(FIRST_SCENARIO_SCHEMA, developer_prompt, user_prompt)
    return result["scenario"]


def evaluate_answer_and_get_next(
    role: str,
    level: str,
    current_round: int,
    current_scenario: str,
    user_answer: str,
    history: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """评估本轮答案，并生成下一轮追问或最终总结。"""
    developer_prompt = build_assessor_prompt()
    history_text = build_history_text(history)
    will_finish = current_round >= 3

    user_prompt = f"""
现在请对候选人的回答进行评估，并返回 JSON。

岗位：{role}
难度：{level}
当前轮次：第{current_round}轮（共3轮）
当前题目：{current_scenario}
候选人回答：{user_answer}

历史记录：
{history_text}

输出要求：
1. 对当前回答进行五维评分。
2. 给出总体评价 feedback。
3. 给出改进建议 suggestion。
4. 如果还没结束，请给出下一轮追问 follow_up_question。
5. 如果当前轮已是最后一轮，请设置 is_finished = true，并输出 final_summary。
6. 如果未结束，则 is_finished = false，final_summary 也必须返回完整字段，但内容可简洁。
7. 不允许五个分数都相同。
8. feedback、suggestion、follow_up_question 要简洁专业、可执行。
9. 当前轮次是否最后一轮：{"是" if will_finish else "否"}。
"""
    return chat_completion_json(EVAL_SCHEMA, developer_prompt, user_prompt)


# =========================
# 全局样式
# =========================
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

html, body, [class*="css"] {
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
}

.stApp {
    background: radial-gradient(circle at 70% 20%, #183B73 0%, #0B1F3A 40%, #061326 100%);
}

.main .block-container {
    max-width: 100%;
    padding-top: 0rem;
    padding-bottom: 0rem;
    padding-left: 0rem;
    padding-right: 0rem;
}

.page-wrapper {
    width: 100%;
    min-height: 100vh;
    color: #FFFFFF;
}

/* 顶部导航 */
.navbar {
    position: sticky;
    top: 0;
    z-index: 999;
    width: 100%;
    background: rgba(6, 19, 38, 0.82);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(255,255,255,0.08);
}

.nav-inner {
    max-width: 1400px;
    margin: 0 auto;
    padding: 18px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.brand {
    font-size: 22px;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: 0.5px;
}

.brand span {
    color: #75B5FF;
    margin-right: 8px;
}

.nav-actions {
    display: flex;
    gap: 12px;
    align-items: center;
}

.nav-btn {
    padding: 10px 18px;
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,0.18);
    background: rgba(255,255,255,0.05);
    color: #FFFFFF;
    font-size: 14px;
    font-weight: 500;
    display: inline-block;
}

.nav-btn.primary {
    background: linear-gradient(135deg, #2F7BFF 0%, #58A6FF 100%);
    border: none;
    box-shadow: 0 10px 24px rgba(47,123,255,0.25);
}

/* 首页 */
.hero {
    max-width: 1400px;
    margin: 0 auto;
    min-height: 78vh;
    display: flex;
    align-items: center;
    padding: 50px 40px 80px 40px;
    position: relative;
    overflow: hidden;
}

.hero::before {
    content: "";
    position: absolute;
    width: 560px;
    height: 560px;
    right: -120px;
    top: 40px;
    background: radial-gradient(circle, rgba(69,147,255,0.28) 0%, rgba(69,147,255,0.06) 42%, rgba(69,147,255,0.00) 70%);
    border-radius: 50%;
    pointer-events: none;
}

.hero::after {
    content: "";
    position: absolute;
    width: 380px;
    height: 380px;
    left: -60px;
    bottom: 40px;
    background: radial-gradient(circle, rgba(117,181,255,0.16) 0%, rgba(117,181,255,0.03) 45%, rgba(117,181,255,0.00) 72%);
    border-radius: 50%;
    pointer-events: none;
}

.hero-content {
    position: relative;
    z-index: 2;
    max-width: 760px;
}

.hero-tag {
    display: inline-block;
    padding: 8px 14px;
    border-radius: 999px;
    font-size: 13px;
    color: #BFD9FF;
    border: 1px solid rgba(117,181,255,0.22);
    background: rgba(255,255,255,0.05);
    margin-bottom: 26px;
    letter-spacing: 0.3px;
}

.hero-title {
    font-size: 64px;
    line-height: 1.15;
    font-weight: 800;
    margin-bottom: 20px;
    color: #FFFFFF;
    letter-spacing: 0.5px;
}

.hero-subtitle {
    font-size: 22px;
    line-height: 1.8;
    color: #D5E6FF;
    margin-bottom: 36px;
    max-width: 720px;
}

.hero-actions {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    align-items: center;
}

.link-btn {
    display: inline-block;
    padding: 16px 28px;
    border-radius: 14px;
    font-size: 16px;
    font-weight: 700;
    text-decoration: none;
    transition: all 0.25s ease;
    border: 1px solid transparent;
    cursor: pointer;
}

.link-btn-primary {
    background: linear-gradient(135deg, #2F7BFF 0%, #5EAFFF 100%);
    color: #FFFFFF !important;
    box-shadow: 0 14px 30px rgba(47,123,255,0.30);
}

.link-btn-secondary {
    background: rgba(255,255,255,0.06);
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.16);
}

.feature-strip {
    max-width: 1400px;
    margin: -10px auto 0 auto;
    padding: 0 40px 80px 40px;
    position: relative;
    z-index: 3;
}

.feature-card {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 24px;
    box-shadow: 0 18px 40px rgba(7, 28, 61, 0.10);
    padding: 26px 28px;
    backdrop-filter: blur(10px);
}

.feature-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
}

.feature-item {
    padding: 12px 10px;
}

.feature-title {
    font-size: 18px;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 8px;
}

.feature-desc {
    font-size: 14px;
    color: #C9DAF5;
    line-height: 1.8;
}

.footer {
    padding: 28px 40px 40px 40px;
}

.footer-inner {
    max-width: 1400px;
    margin: 0 auto;
    display: flex;
    justify-content: center;
    gap: 18px;
    flex-wrap: wrap;
}

.footer-btn {
    background: rgba(255,255,255,0.08);
    color: #FFFFFF;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 12px;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 600;
    text-decoration: none;
    box-shadow: 0 8px 20px rgba(12, 36, 72, 0.05);
}

/* 功能选择页 */
.module-page {
    max-width: 1200px;
    margin: 0 auto;
    min-height: 100vh;
    padding: 70px 40px 60px 40px;
    color: #FFFFFF;
}

.module-header {
    text-align: center;
    margin-bottom: 40px;
}

.module-title {
    font-size: 48px;
    font-weight: 800;
    margin-bottom: 16px;
    letter-spacing: 0.5px;
}

.module-subtitle {
    font-size: 20px;
    color: #CFE0FB;
    line-height: 1.8;
}

.module-card {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 24px;
    padding: 36px 28px;
    min-height: 250px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    text-align: center;
    backdrop-filter: blur(10px);
    box-shadow: 0 18px 40px rgba(7, 28, 61, 0.14);
}

.module-card-title {
    font-size: 30px;
    font-weight: 800;
    margin-bottom: 16px;
    color: #FFFFFF;
}

.module-card-desc {
    font-size: 16px;
    line-height: 1.9;
    color: #D7E4FA;
    max-width: 420px;
    margin: 0 auto 28px auto;
}

.module-note {
    margin-top: 40px;
    text-align: center;
    color: #AFC8EF;
    font-size: 14px;
}

.back-btn-area {
    margin-top: 42px;
    display: flex;
    justify-content: center;
}

/* 专业知识课程页 */
.course-main-wrap {
    max-width: 1400px;
    margin: 0 auto;
    padding: 60px 40px 40px 40px;
}

.course-header {
    margin-bottom: 28px;
}

.course-title {
    font-size: 42px;
    font-weight: 700;
    color: #FFFFFF !important;
    margin-top: 14px;
    margin-bottom: 16px;
}

.course-subtitle {
    font-size: 18px;
    color: #CFE0FB !important;
    line-height: 1.8;
    margin-bottom: 6px;
}

.tip-box {
    background: rgba(47,123,255,0.10);
    border: 1px solid rgba(94,175,255,0.16);
    color: #DDEBFF;
    border-radius: 16px;
    padding: 16px 18px;
    margin-bottom: 22px;
    font-size: 15px;
    line-height: 1.8;
}

.course-grid-title {
    font-size: 24px;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 20px;
}

.course-small-note {
    margin-top: 20px;
    color: #AFC8EF;
    font-size: 14px;
    line-height: 1.8;
}

.placeholder-box {
    min-height: 420px;
    display: flex;
    align-items: flex-start;
    justify-content: flex-start;
    text-align: left;
    color: #AFC8EF;
    line-height: 1.9;
    font-size: 17px;
    padding-top: 8px;
}

.left-nav-button {
    margin-bottom: 12px;
}

.course-button .stButton > button {
    min-height: 92px;
    font-size: 17px;
    line-height: 1.5;
}

/* 岗位模拟试炼场 */
.arena-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 70px 40px 24px 40px;
    color: #FFFFFF;
}

.arena-header {
    text-align: center;
    margin-bottom: 18px;
}

.arena-title {
    font-size: 46px;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 14px;
}

.arena-subtitle {
    font-size: 18px;
    color: #CFE0FB;
    line-height: 1.8;
}

.section-label {
    font-size: 22px;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 18px;
}

.selection-summary {
    margin-top: 22px;
    background: rgba(47,123,255,0.10);
    border: 1px solid rgba(94,175,255,0.16);
    color: #DDEBFF;
    border-radius: 16px;
    padding: 16px 18px;
    line-height: 1.9;
    font-size: 16px;
}

.operation-area {
    margin-top: 18px;
}

/* AI模拟页 */
.ai-page {
    max-width: 1300px;
    margin: 0 auto;
    padding: 60px 40px 50px 40px;
    color: #FFFFFF;
}

.ai-top-card,
.ai-main-card,
.ai-feedback-card,
.ai-history-card {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 24px;
    padding: 26px 24px;
    backdrop-filter: blur(10px);
    box-shadow: 0 18px 40px rgba(7, 28, 61, 0.14);
    margin-bottom: 22px;
}

.ai-page-title {
    font-size: 40px;
    font-weight: 800;
    margin-bottom: 14px;
    color: #FFFFFF;
}

.ai-meta {
    color: #D7E4FA;
    font-size: 16px;
    line-height: 1.9;
}

.ai-section-title {
    font-size: 24px;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 16px;
}

.scenario-box {
    background: rgba(47,123,255,0.10);
    border: 1px solid rgba(94,175,255,0.16);
    color: #E8F2FF;
    border-radius: 18px;
    padding: 18px 20px;
    line-height: 1.9;
    font-size: 16px;
    margin-bottom: 16px;
}

.score-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 14px;
    margin-bottom: 18px;
}

.score-item {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 16px 12px;
    text-align: center;
}

.score-label {
    font-size: 14px;
    color: #BFD9FF;
    margin-bottom: 8px;
}

.score-value {
    font-size: 28px;
    font-weight: 800;
    color: #FFFFFF;
}

.feedback-box {
    background: rgba(255,255,255,0.05);
    border-radius: 16px;
    padding: 16px 18px;
    color: #E6F0FF;
    line-height: 1.9;
    margin-bottom: 14px;
}

.history-item {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 16px;
}

.history-title {
    font-size: 18px;
    font-weight: 700;
    color: #FFFFFF;
    margin-bottom: 10px;
}

.summary-box {
    background: rgba(47,123,255,0.12);
    border: 1px solid rgba(94,175,255,0.16);
    border-radius: 18px;
    padding: 18px;
    margin-top: 18px;
    line-height: 1.9;
    color: #E8F2FF;
}


/* 登录页 / 用户信息页 */
.login-page,
.profile-page {
    max-width: 1180px;
    margin: 0 auto;
    min-height: 100vh;
    padding: 70px 40px 50px 40px;
    color: #FFFFFF;
}

.login-card,
.profile-card,
.recommend-card,
.role-score-card {
    width: 100%;
    box-sizing: border-box;
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 24px;
    padding: 28px 26px;
    backdrop-filter: blur(10px);
    box-shadow: 0 18px 40px rgba(7, 28, 61, 0.14);
    margin-bottom: 22px;
}

.login-title,
.profile-title {
    font-size: 40px;
    font-weight: 800;
    margin-bottom: 12px;
    color: #FFFFFF;
}

.login-desc,
.profile-desc {
    font-size: 17px;
    color: #D7E4FA;
    line-height: 1.9;
}

.info-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
}

.info-item {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 18px;
}

.info-label {
    color: #BFD9FF;
    font-size: 14px;
    margin-bottom: 8px;
}

.info-value {
    color: #FFFFFF;
    font-size: 28px;
    font-weight: 800;
}

.progress-text {
    color: #DDEBFF;
    font-size: 15px;
    margin-top: 10px;
    line-height: 1.8;
}

.progress-card-body {
    margin-top: 18px;
}

.progress-track {
    width: 100%;
    height: 12px;
    background: rgba(255,255,255,0.18);
    border-radius: 999px;
    overflow: hidden;
    margin: 16px 0 12px 0;
}

.progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #4A84FF 0%, #73A9FF 100%);
    box-shadow: 0 0 18px rgba(74,132,255,0.35);
}

.role-chip-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 14px;
}

.role-chip {
    padding: 8px 14px;
    border-radius: 999px;
    font-size: 13px;
    color: #DDEBFF;
    border: 1px solid rgba(117,181,255,0.22);
    background: rgba(255,255,255,0.05);
}

.role-score-list {
    margin-top: 18px;
}

.role-score-item {
    width: 100%;
    box-sizing: border-box;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 16px;
    border-radius: 16px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.07);
    margin-bottom: 12px;
    color: #E8F2FF;
}

.recommend-card {
    background: linear-gradient(135deg, rgba(47,123,255,0.18) 0%, rgba(94,175,255,0.12) 100%);
    border: 1px solid rgba(94,175,255,0.22);
}

.recommend-badge {
    display: inline-block;
    padding: 8px 14px;
    border-radius: 999px;
    background: rgba(255,255,255,0.10);
    color: #BFD9FF;
    font-size: 13px;
    margin-bottom: 14px;
}

.recommend-role {
    font-size: 36px;
    font-weight: 800;
    color: #FFFFFF;
    margin-bottom: 12px;
}

/* Streamlit 按钮 */
.stButton > button {
    width: 100%;
    border-radius: 16px;
    font-weight: 700;
    border: none;
    padding: 0.9rem 1rem;
    font-size: 18px;
    background: linear-gradient(135deg, #2F7BFF 0%, #5EAFFF 100%);
    color: white;
    box-shadow: 0 12px 28px rgba(47,123,255,0.25);
}

.stButton > button:hover {
    filter: brightness(1.04);
}

.secondary-button .stButton > button {
    background: rgba(255,255,255,0.08) !important;
    color: #FFFFFF !important;
    border: 1px solid rgba(255,255,255,0.14) !important;
    box-shadow: none !important;
}

.stButton > button:disabled {
    background: rgba(255,255,255,0.12) !important;
    color: rgba(255,255,255,0.45) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
}

/* 文本输入框 */
textarea {
    border-radius: 16px !important;
}

/* 响应式 */
@media (max-width: 992px) {
    .nav-inner {
        padding: 16px 20px;
    }

    .hero {
        padding: 40px 20px 70px 20px;
        min-height: 72vh;
    }

    .hero-title {
        font-size: 46px;
    }

    .hero-subtitle {
        font-size: 18px;
        line-height: 1.7;
    }

    .feature-strip {
        padding: 0 20px 60px 20px;
    }

    .feature-grid {
        grid-template-columns: 1fr;
    }

    .footer {
        padding: 24px 20px 36px 20px;
    }

    .module-page {
        padding: 60px 20px 50px 20px;
    }

    .module-title {
        font-size: 38px;
    }

    .course-main-wrap {
        padding: 50px 20px 40px 20px;
    }

    .course-title {
        font-size: 34px;
    }

    .arena-page {
        padding: 60px 20px 24px 20px;
    }

    .arena-title {
        font-size: 38px;
    }

    .ai-page {
        padding: 50px 20px 40px 20px;
    }

    .login-page,
    .profile-page {
        padding: 60px 20px 40px 20px;
    }

    .ai-page-title {
        font-size: 32px;
    }

    .score-grid {
        grid-template-columns: 1fr 1fr;
    }
}

@media (max-width: 576px) {
    .brand {
        font-size: 18px;
    }

    .nav-actions {
        gap: 8px;
    }

    .nav-btn {
        padding: 8px 12px;
        font-size: 12px;
    }

    .hero-title {
        font-size: 34px;
    }

    .hero-subtitle {
        font-size: 16px;
    }

    .link-btn {
        width: 100%;
        text-align: center;
    }

    .module-title {
        font-size: 30px;
    }

    .module-subtitle {
        font-size: 16px;
    }

    .module-card-title {
        font-size: 24px;
    }

    .course-title {
        font-size: 28px;
    }

    .course-subtitle {
        font-size: 16px;
    }

    .arena-title {
        font-size: 30px;
    }

    .arena-subtitle {
        font-size: 16px;
    }

    .ai-page-title {
        font-size: 28px;
    }

    .login-title,
    .profile-title {
        font-size: 28px;
    }

    .info-grid {
        grid-template-columns: 1fr;
    }

    .score-grid {
        grid-template-columns: 1fr;
    }
}
</style>
""", unsafe_allow_html=True)


# =========================
# 首页
# =========================
def render_home():
    st.markdown("""
<div class="page-wrapper">

<div class="navbar">
    <div class="nav-inner">
        <div class="brand"></div>
        <div class="nav-actions">
            <div class="nav-btn">语言</div>
            <a href="?page=login" class="nav-btn primary">登录/注册</a>
        </div>
    </div>
</div>

<section class="hero">
    <div class="hero-content">
        <div class="hero-tag">AI HR Demo · 企业级岗位模拟与人才识别平台</div>
        <div class="hero-title">AI 驱动・全域轮岗试炼</div>
        <div class="hero-subtitle">
            一键模拟全岗试炼，提前看见你的职业可能性。<br>
            面向即将参与轮岗的候选人，帮助你在更短时间内完成多岗位情境挑战，
            发现自己的销售能力、商业判断、数据驱动能力与跨部门协同潜力。
        </div>
        <div class="hero-actions">
            <a href="?page=module" class="link-btn link-btn-primary">立即开始</a>
            <a href="#" class="link-btn link-btn-secondary">预约演示</a>
        </div>
    </div>
</section>

<section class="feature-strip">
    <div class="feature-card">
        <div class="feature-grid">
            <div class="feature-item">
                <div class="feature-title">为什么使用平台</div>
                <div class="feature-desc">
                    通过 AI 预演真实业务场景，减少大规模轮岗带来的时间成本与组织成本，
                    更高效地完成候选人能力识别。
                </div>
            </div>
            <div class="feature-item">
                <div class="feature-title">你将体验什么</div>
                <div class="feature-desc">
                    在多个关键岗位中完成模拟任务与决策挑战，系统将基于过程表现生成能力画像，
                    帮助你提前看见最适合的发展方向。
                </div>
            </div>
            <div class="feature-item">
                <div class="feature-title">如何开始使用</div>
                <div class="feature-desc">
                    点击“立即开始”，进入岗位试炼流程；平台会根据你的作答表现，
                    提供岗位匹配建议与后续验证路径。
                </div>
            </div>
        </div>
    </div>
</section>

<footer class="footer">
    <div class="footer-inner">
        <a href="#" class="footer-btn">关于我们</a>
        <a href="#" class="footer-btn">用户反馈</a>
        <a href="#" class="footer-btn">联系我们</a>
    </div>
</footer>

</div>
""", unsafe_allow_html=True)


# =========================
# 功能选择页
# =========================
def render_module_page():
    st.markdown("""
<div class="module-page">
    <div class="module-header">
        <div class="hero-tag">AI HR Demo · 功能选择页</div>
        <div class="module-title">欢迎进入轮岗试炼营</div>
        <div class="module-subtitle">请选择模块，开启你的模拟轮岗之旅。</div>
    </div>
</div>
""", unsafe_allow_html=True)

    left_space, col1, col2, right_space = st.columns([1, 3, 3, 1], gap="large")

    with col1:
        st.markdown("""
<div class="module-card">
    <div class="module-card-title">专业知识课程</div>
    <div class="module-card-desc">
        帮助你快速补齐岗位所需的核心知识与方法。
    </div>
</div>
""", unsafe_allow_html=True)
        if st.button("进入专业知识课程", use_container_width=True, key="course_btn"):
            go_course()
            st.rerun()

    with col2:
        st.markdown("""
<div class="module-card">
    <div class="module-card-title">岗位模拟训练场</div>
    <div class="module-card-desc">
        通过真实业务场景，体验不同岗位挑战。
    </div>
</div>
""", unsafe_allow_html=True)
        if st.button("进入岗位模拟训练场", use_container_width=True, key="sim_btn"):
            go_simulation_arena()
            st.rerun()

    st.markdown("<div class='back-btn-area'></div>", unsafe_allow_html=True)

    back_left, back_mid, back_right = st.columns([2.3, 1.4, 2.3])
    with back_mid:
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("返回首页", use_container_width=True, key="back_home_btn"):
            go_home()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("""
<div class="module-note">
    当前为 Demo 演示版本，你可以从这里继续扩展到课程页、模拟页、能力测评页等完整流程。
</div>
""", unsafe_allow_html=True)


# =========================
# 专业知识课程页
# =========================
def render_course_page():
    st.markdown('<div class="course-main-wrap">', unsafe_allow_html=True)

    left_col, right_col = st.columns([1.05, 2.4], gap="large")

    with left_col:
        st.markdown("""
<div class="course-header">
    <div class="hero-tag">AI HR Demo · 专业知识课程</div>
    <div class="course-title">专业知识课程</div>
    <div class="course-subtitle">
        请选择岗位知识库，系统将为你展示对应的核心课程内容。
    </div>
</div>
""", unsafe_allow_html=True)

        st.markdown("<div class='left-nav-button'>", unsafe_allow_html=True)
        if st.button("产品岗知识库", use_container_width=True, key="kb_product"):
            select_knowledge_base("产品岗知识库")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='left-nav-button'>", unsafe_allow_html=True)
        if st.button("设计岗知识库", use_container_width=True, key="kb_design"):
            select_knowledge_base("设计岗知识库")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='left-nav-button'>", unsafe_allow_html=True)
        if st.button("市场岗知识库", use_container_width=True, key="kb_marketing"):
            select_knowledge_base("市场岗知识库")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='left-nav-button'>", unsafe_allow_html=True)
        if st.button("职能岗知识库", use_container_width=True, key="kb_function"):
            select_knowledge_base("职能岗知识库")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='left-nav-button'>", unsafe_allow_html=True)
        if st.button("AI通识课（必修）", use_container_width=True, key="kb_ai"):
            select_knowledge_base("AI通识课（必修）")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("返回功能选择页", use_container_width=True, key="back_module_btn"):
            go_module()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        st.markdown("<div style='height: 235px;'></div>", unsafe_allow_html=True)

        selected = st.session_state.selected_knowledge_base

        if selected is None:
            st.markdown("""
<div class="placeholder-box">
    请选择左侧岗位知识库。<br>
    课程内容将在这里动态展示。
</div>
""", unsafe_allow_html=True)

        elif selected == "产品岗知识库":
            st.markdown("""
<div class="tip-box">
    当前已为你展开 <b>产品岗知识库</b>。以下为产品岗位常见的核心课程内容，后续可继续扩展为视频课、文档课或测验模块。
</div>
<div class="course-grid-title">产品岗核心课程</div>
""", unsafe_allow_html=True)

            row1_col1, row1_col2 = st.columns(2, gap="large")
            with row1_col1:
                st.markdown('<div class="course-button">', unsafe_allow_html=True)
                st.button("基础指标概念", use_container_width=True, key="course_metric")
                st.markdown('</div>', unsafe_allow_html=True)

            with row1_col2:
                st.markdown('<div class="course-button">', unsafe_allow_html=True)
                st.button("SQL基础教程", use_container_width=True, key="course_sql")
                st.markdown('</div>', unsafe_allow_html=True)

            row2_col1, row2_col2 = st.columns(2, gap="large")
            with row2_col1:
                st.markdown('<div class="course-button">', unsafe_allow_html=True)
                st.button("如何撰写PRD", use_container_width=True, key="course_prd")
                st.markdown('</div>', unsafe_allow_html=True)

            with row2_col2:
                st.markdown('<div class="course-button">', unsafe_allow_html=True)
                st.button("如何画流程图➕原型图", use_container_width=True, key="course_flow")
                st.markdown('</div>', unsafe_allow_html=True)

            row3_col1, row3_col2 = st.columns(2, gap="large")
            with row3_col1:
                st.markdown('<div class="course-button">', unsafe_allow_html=True)
                st.button("需求优先级方法论", use_container_width=True, key="course_priority")
                st.markdown('</div>', unsafe_allow_html=True)

            with row3_col2:
                st.markdown('<div class="course-button">', unsafe_allow_html=True)
                st.button("竞品分析方法论", use_container_width=True, key="course_competitor")
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("""
<div class="course-small-note">
    当前阶段仅实现课程按钮展示效果，后续可继续扩展为课程详情页、学习进度条、知识测验与AI答疑等功能。
</div>
""", unsafe_allow_html=True)

        elif selected == "设计岗知识库":
            st.markdown("""
<div class="placeholder-box">
    设计岗知识库内容待补充
</div>
""", unsafe_allow_html=True)

        elif selected == "市场岗知识库":
            st.markdown("""
<div class="placeholder-box">
    市场岗知识库内容待补充
</div>
""", unsafe_allow_html=True)

        elif selected == "职能岗知识库":
            st.markdown("""
<div class="placeholder-box">
    职能岗知识库内容待补充
</div>
""", unsafe_allow_html=True)

        elif selected == "AI通识课（必修）":
            st.markdown("""
<div class="placeholder-box">
    AI通识课内容待补充
</div>
""", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# 岗位模拟试炼场页面
# =========================
def render_simulation_arena_page():
    st.markdown("""
<div class="arena-page">
    <div class="arena-header">
        <div class="hero-tag">AI HR Demo · 岗位模拟试炼场</div>
        <div class="arena-title">岗位模拟试炼场</div>
        <div class="arena-subtitle">
            请选择岗位与挑战难度，完成基础设定后即可进入模拟试炼流程。
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    top_left, top_mid, top_right = st.columns([1, 10, 1])
    with top_mid:
        st.markdown('<div class="section-label">岗位选择</div>', unsafe_allow_html=True)

        if st.button("岗位选择", use_container_width=True, key="arena_show_roles"):
            st.session_state.show_role_options = True

        if st.session_state.show_role_options:
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            role_col1, role_col2, role_col3, role_col4 = st.columns(4, gap="large")

            with role_col1:
                if st.button("产品岗", use_container_width=True, key="role_product"):
                    handle_role_select("产品岗")
                    st.rerun()

            with role_col2:
                if st.button("设计岗", use_container_width=True, key="role_design"):
                    handle_role_select("设计岗")
                    st.rerun()

            with role_col3:
                if st.button("市场岗", use_container_width=True, key="role_marketing"):
                    handle_role_select("市场岗")
                    st.rerun()

            with role_col4:
                if st.button("职能岗", use_container_width=True, key="role_function"):
                    handle_role_select("职能岗")
                    st.rerun()

        if st.session_state.show_level_options:
            st.markdown("<div style='height: 26px;'></div>", unsafe_allow_html=True)
            st.markdown('<div class="section-label">难度选择</div>', unsafe_allow_html=True)

            level_col1, level_col2, level_col3 = st.columns(3, gap="large")

            with level_col1:
                if st.button("初级", use_container_width=True, key="level_basic"):
                    handle_level_select("初级")
                    st.rerun()

            with level_col2:
                if st.button("进阶", use_container_width=True, key="level_advanced"):
                    handle_level_select("进阶")
                    st.rerun()

            with level_col3:
                if st.button("综合挑战", use_container_width=True, key="level_comprehensive"):
                    handle_level_select("综合挑战")
                    st.rerun()

        if st.session_state.show_confirm_button:
            st.markdown("<div style='height: 26px;'></div>", unsafe_allow_html=True)
            confirm_left, confirm_mid, confirm_right = st.columns([2.8, 2.4, 2.8])
            with confirm_mid:
                if st.button("确定", use_container_width=True, key="confirm_selection_btn"):
                    confirm_simulation_selection()
                    st.rerun()

        if st.session_state.selection_confirmed:
            st.markdown(f"""
<div class="selection-summary">
    当前岗位：{st.session_state.selected_role}<br>
    当前难度：{st.session_state.selected_level}
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height: 34px;'></div>", unsafe_allow_html=True)
    op_left, op_mid, op_right = st.columns([1.4, 5.2, 1.4])
    with op_mid:
        btn_col1, btn_col2 = st.columns(2, gap="large")

        with btn_col1:
            start_disabled = not st.session_state.can_start_simulation
            if st.button("开始模拟", use_container_width=True, key="start_simulation_btn", disabled=start_disabled):
                go_ai_simulation()
                st.rerun()

        with btn_col2:
            if st.button("重新开始", use_container_width=True, key="reset_simulation_btn"):
                reset_simulation_state()
                st.rerun()

    st.markdown("<div class='back-btn-area'></div>", unsafe_allow_html=True)
    back_left, back_mid, back_right = st.columns([2.3, 1.6, 2.3])
    with back_mid:
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("返回功能选择页", use_container_width=True, key="back_module_from_arena"):
            go_module()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# =========================
# AI模拟页
# =========================
def render_ai_simulation_page():
    role = st.session_state.selected_role
    level = st.session_state.selected_level

    # 未选择岗位或难度时，提示返回
    if not role or not level:
        st.markdown("""
<div class="ai-page">
    <div class="ai-top-card">
        <div class="ai-page-title">AI岗位模拟训练</div>
        <div class="ai-meta">
            当前未检测到完整的岗位与难度选择。请先返回“岗位模拟试炼场”完成设置。
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

        back_left, back_mid, back_right = st.columns([2.2, 1.8, 2.2])
        with back_mid:
            st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
            if st.button("返回岗位模拟试炼场", use_container_width=True, key="back_arena_no_selection"):
                go_simulation_arena()
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # 若缺少 SDK 或 API Key，给出提示但不泄露 key
    sdk_missing = OpenAI is None
    client_missing = get_openai_client() is None

    st.markdown('<div class="ai-page">', unsafe_allow_html=True)

    # 首次进入自动生成第一题
    if not st.session_state.simulation_started and not sdk_missing and not client_missing:
        with st.spinner("正在生成第一道业务模拟题..."):
            try:
                first_scenario = generate_scenario_entry(role, level)
                st.session_state.current_scenario = first_scenario
                st.session_state.simulation_started = True
                st.session_state.current_round = 1
                st.session_state.current_question_started_at = time.time()
                st.session_state.show_authenticity_warning = False
                st.session_state.authenticity_check_result = None
            except Exception as e:
                import traceback
                st.error(f"生成第一题失败：{e}")
                st.code(traceback.format_exc())

    # 顶部信息区
    st.markdown(f"""
<div class="ai-top-card">
    <div class="hero-tag">AI HR Demo · AI模拟页</div>
    <div class="ai-page-title">AI岗位模拟训练</div>
    <div class="ai-meta">
        当前岗位：{role}<br>
        当前难度：{level}<br>
        当前轮次：第{st.session_state.current_round}轮 / 第3轮
    </div>
</div>
""", unsafe_allow_html=True)

    # 环境提示
    if sdk_missing:
        st.error("当前环境未安装 openai 库。请先执行：pip install openai")
    elif client_missing:
        st.warning("未检测到可用的 OpenAI API 配置。请设置环境变量 OPENAI_API_KEY，或将代码中的 API_KEY 占位替换为你的密钥。")

    # 中间主交互区
    st.markdown(f"""
<div class="ai-main-card">
    <div class="ai-section-title">当前业务场景题目</div>
    <div class="scenario-box">
        {st.session_state.current_scenario if st.session_state.current_scenario else "等待生成题目..."}
    </div>
</div>
""", unsafe_allow_html=True)

    render_authenticity_warning_box()

    answer_disabled = (
        st.session_state.is_finished
        or not st.session_state.current_scenario
        or sdk_missing
        or client_missing
    )
    if st.session_state.clear_answer_input:
      st.session_state.answer_input_widget = ""
      st.session_state.clear_answer_input = False

    st.text_area(
    "请输入你的回答",
    key="answer_input_widget",
    height=220,
    placeholder="请结合你的分析过程、判断依据、协同思路和执行建议进行回答。"
    )
    submit_col1, submit_col2, submit_col3 = st.columns([1.8, 1.8, 1.8], gap="large")

    with submit_col1:
      submit_clicked = st.button(
        "提交答案",
        use_container_width=True,
        disabled=answer_disabled,
        key="submit_answer_btn"
      )

    with submit_col2:
      if st.button("重新开始本轮模拟", use_container_width=True, key="restart_ai_simulation_btn"):
        reset_ai_simulation_state()
        st.rerun()

    with submit_col3:
      back_clicked = st.button(
        "返回岗位模拟试炼场",
        use_container_width=True,
        key="back_to_arena_from_ai"
      )
      if back_clicked:
        go_simulation_arena()
        st.rerun()
      if submit_clicked:
        user_answer = st.session_state.answer_input_widget.strip()

        if not user_answer:
            st.warning("请先输入你的回答，再提交。")
        elif st.session_state.is_finished:
            st.info("本轮模拟已结束，请重新开始本轮模拟。")
        else:
            response_seconds = estimate_response_seconds(st.session_state.get("current_question_started_at"))
            with st.spinner("正在进行回答真实性校验..."):
                authenticity_result = check_answer_authenticity(
                    answer=user_answer,
                    question=st.session_state.current_scenario,
                    response_seconds=response_seconds
                )

            st.session_state.authenticity_check_result = authenticity_result

            if not authenticity_result["is_valid"]:
                st.session_state.show_authenticity_warning = True
                st.warning("本次回答暂未通过真实性校验，请根据提示重新作答。")
                st.rerun()
            else:
                st.session_state.show_authenticity_warning = False
                with st.spinner("AI评估官正在分析你的回答..."):
                    try:
                        result = evaluate_answer_entry(
                            role=role,
                            level=level,
                            current_round=st.session_state.current_round,
                            current_scenario=st.session_state.current_scenario,
                            user_answer=user_answer,
                            history=st.session_state.history
                        )

                        st.session_state.current_scores = result["scores"]
                        st.session_state.current_feedback = result["feedback"]
                        st.session_state.current_suggestion = result["suggestion"]
                        st.session_state.current_follow_up = result["follow_up_question"]
                        st.session_state.is_finished = result["is_finished"]
                        st.session_state.final_summary = result["final_summary"]

                        # 若本岗位模拟结束，则将岗位成绩回写到用户中心
                        if result["is_finished"]:
                            final_role_score = compute_total_score(result["scores"], role=role, level=level)
                            mark_role_completed(role, final_role_score)

                        # 写入历史
                        st.session_state.history.append({
                            "round": st.session_state.current_round,
                            "scenario": st.session_state.current_scenario,
                            "answer": user_answer,
                            "scores": result["scores"],
                            "feedback": result["feedback"],
                            "suggestion": result["suggestion"],
                            "follow_up_question": result["follow_up_question"],
                            "is_finished": result["is_finished"],
                            "final_summary": result["final_summary"],
                            "authenticity_check": authenticity_result
                        })

                        # 未结束时，下一轮题目直接采用 follow_up_question
                        if not result["is_finished"]:
                            st.session_state.current_round += 1
                            st.session_state.current_scenario = result["follow_up_question"]
                            st.session_state.current_question_started_at = time.time()

                        st.session_state.clear_answer_input = True
                        st.rerun()

                    except Exception as e:
                        st.error(f"AI评估失败：{e}")

    # 评分与反馈区
    if st.session_state.current_scores:
        scores = st.session_state.current_scores
        st.markdown("""
<div class="ai-feedback-card">
    <div class="ai-section-title">评分与反馈</div>
""", unsafe_allow_html=True)

        score_order = get_score_order(role, level, scores)
        score_items_html = "".join(
            [
                f'<div class="score-item"><div class="score-label">{label}</div><div class="score-value">{scores.get(label, "-")}</div></div>'
                for label in score_order
            ]
        )
        st.markdown(f"""
<div class="score-grid">
    {score_items_html}
</div>
""", unsafe_allow_html=True)

        total_score_preview = compute_total_score(scores, role=role, level=level)
        st.markdown(f"""
<div class="feedback-box"><b>当前综合分：</b><br>{total_score_preview}分</div>
<div class="feedback-box"><b>总体评价：</b><br>{st.session_state.current_feedback}</div>
<div class="feedback-box"><b>改进建议：</b><br>{st.session_state.current_suggestion}</div>
""", unsafe_allow_html=True)

        if not st.session_state.is_finished:
            st.markdown(f"""
<div class="feedback-box"><b>下一轮追问：</b><br>{st.session_state.current_follow_up}</div>
""", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # 历史记录区
    st.markdown("""
<div class="ai-history-card">
    <div class="ai-section-title">历史记录</div>
</div>
""", unsafe_allow_html=True)

    if not st.session_state.history:
        st.markdown("""
<div class="feedback-box">当前还没有提交记录。完成一次作答后，这里会显示题目、回答与AI反馈。</div>
""", unsafe_allow_html=True)
    else:
        for item in st.session_state.history:
            st.markdown(f"""
<div class="history-item">
    <div class="history-title">第{item['round']}轮</div>
    <div class="feedback-box"><b>题目：</b><br>{item['scenario']}</div>
    <div class="feedback-box"><b>你的回答：</b><br>{item['answer']}</div>
    <div class="feedback-box"><b>AI反馈：</b><br>{item['feedback']}</div>
    <div class="feedback-box"><b>改进建议：</b><br>{item['suggestion']}</div>
</div>
""", unsafe_allow_html=True)

    # 最终总结
    if st.session_state.is_finished and st.session_state.final_summary:
        fs = st.session_state.final_summary
        st.markdown(f"""
<div class="summary-box">
    <b>最终总结</b><br><br>
    更适合优先尝试的岗位方向：{fs.get('recommended_direction', '')}<br>
    当前优势能力：{fs.get('strengths', '')}<br>
    重点提升建议：{fs.get('improvements', '')}
</div>
""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)




# =========================
# 登录页
# =========================
def render_login_page():
    st.markdown("""
<div class="login-page">
    <div class="login-card">
        <div class="hero-tag">AI HR Demo · 登录页</div>
        <div class="login-title">欢迎登录！</div>
        <div class="login-desc">
            本页面为演示版，当前使用微信登录模拟授权流程。<br>
            点击下方按钮后，系统将生成一份模拟用户信息，并进入“用户信息页”。
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    left, mid, right = st.columns([2.5, 2.2, 2.5])
    with mid:
        if st.button("微信登录", use_container_width=True, key="wechat_login_btn"):
            mock_wechat_login()
            st.success("模拟授权成功")
            go_user_profile()
            st.rerun()

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
    left2, mid2, right2 = st.columns([2.5, 2.2, 2.5])
    with mid2:
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("返回首页", use_container_width=True, key="back_home_from_login"):
            go_home()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


# =========================
# 用户信息页
# =========================
def render_user_profile_page():
    if not st.session_state.get("is_logged_in", False):
        st.warning("请先登录后再查看用户信息页。")
        go_login()
        st.rerun()

    update_simulation_progress_and_recommendation()

    user_name = st.session_state.get("user_name", "刘同学")
    user_age = st.session_state.get("user_age", 23)
    course_progress = int(st.session_state.get("course_progress", 90))
    simulation_progress = int(st.session_state.get("simulation_progress", 0))
    completed_roles = st.session_state.get("completed_roles", [])
    role_scores = st.session_state.get("role_scores", {})
    recommended_role = st.session_state.get("recommended_role")

    st.markdown(f"""<div class="profile-page">
<div class="profile-card">
    <div class="hero-tag">AI HR Demo · 用户信息页</div>
    <div class="profile-title">用户信息页</div>
    <div class="profile-desc">
        当前为演示版用户中心，可查看基础信息、专业知识课程进度、岗位模拟试炼场进度与岗位推荐结果。
    </div>
</div>

<div class="profile-card">
    <div class="ai-section-title">用户基础信息</div>
    <div class="info-grid">
        <div class="info-item">
            <div class="info-label">姓名</div>
            <div class="info-value">{user_name}</div>
        </div>
        <div class="info-item">
            <div class="info-label">年龄</div>
            <div class="info-value">{user_age}</div>
        </div>
    </div>
</div>

<div class="profile-card">
    <div class="ai-section-title">专业知识课程进度</div>
    <div class="progress-card-body">
        <div class="progress-track">
            <div class="progress-fill" style="width: {course_progress}%;"></div>
        </div>
        <div class="progress-text">当前课程完成度：{course_progress}%</div>
    </div>
</div>

<div class="profile-card">
    <div class="ai-section-title">岗位模拟试炼场进度</div>
    <div class="progress-card-body">
        <div class="progress-track">
            <div class="progress-fill" style="width: {simulation_progress}%;"></div>
        </div>
        <div class="progress-text">当前已完成 {len(completed_roles)} / 4 个岗位模拟，总进度：{simulation_progress}%</div>
""", unsafe_allow_html=True)

    completed_html = "".join([f"<div class='role-chip'>{role}</div>" for role in completed_roles])
    if completed_html:
        st.markdown(f"<div class='role-chip-wrap'>{completed_html}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='progress-text'>你还没有完成岗位模拟，前往“岗位模拟试炼场”开始体验后，这里会实时更新。</div>", unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    score_items_html = "".join([
        f"<div class='role-score-item'><span>{role}</span><span>{(str(role_scores[role]) + '分') if role in role_scores else '暂未生成'}</span></div>"
        for role in ALL_ROLES
    ])
    st.markdown(f"""<div class='role-score-card'>
    <div class='ai-section-title'>岗位成绩记录</div>
    <div class='role-score-list'>
        {score_items_html}
    </div>
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    if simulation_progress < 100 or not recommended_role:
        st.markdown("""<div class="profile-card">
    <div class="ai-section-title">推荐岗位结果</div>
    <div class="feedback-box">完成全部岗位模拟后，将为你生成推荐岗位结果。</div>
</div>
""", unsafe_allow_html=True)
    else:
        final_score = role_scores.get(recommended_role, "-")
        st.markdown(f"""<div class="recommend-card">
    <div class="recommend-badge">推荐岗位结果已生成</div>
    <div class="recommend-role">{recommended_role}</div>
    <div class="feedback-box">
        根据你在各岗位模拟中的综合表现，系统当前更推荐你优先尝试 <b>{recommended_role}</b> 方向。
        当前该岗位综合得分为 <b>{final_score}</b> 分。
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    _, bottom_mid1, bottom_mid2, _ = st.columns([1.5, 2.2, 2.2, 1.5], gap="large")
    with bottom_mid1:
        if st.button("前往岗位模拟试炼场", use_container_width=True, key="go_arena_from_profile"):
            go_simulation_arena()
            st.rerun()
    with bottom_mid2:
        if st.button("返回首页", use_container_width=True, key="back_home_from_profile"):
            go_home()
            st.rerun()

# =========================
# 页面路由
# =========================
if st.session_state.page == "course":
    render_course_page()
elif st.session_state.page == "simulation_arena":
    render_simulation_arena_page()
elif st.session_state.page == "ai_simulation":
    render_ai_simulation_page()
elif st.session_state.page == "login":
    render_login_page()
elif st.session_state.page == "user_profile":
    render_user_profile_page()
elif st.session_state.page == "module":
    render_module_page()
else:
    render_home()