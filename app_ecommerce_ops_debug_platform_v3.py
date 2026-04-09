import os
import json
from typing import Any, Dict, List, Optional

import streamlit as st

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# =========================
# 基础配置
# =========================
st.set_page_config(
    page_title="AI电商运营训练平台",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MODEL_NAME = "gpt-4o"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

KNOWLEDGE_MODULES = [
    "核心指标定义及计算方式",
    "广告投放及流量获取",
    "竞品分析",
    "A/B Test",
    "商品页面设计",
    "大促与活动运营策略",
    "国内电商平台细分及规则",
    "国外电商平台细分及规则",
    "AI通识课",
]

KNOWLEDGE_CONTENT = {
    "核心指标定义及计算方式": {
        "summary": "理解电商增长的最小分析单元，学会把GMV拆成流量、点击率、转化率、客单价、复购率与投放效率等指标。",
        "points": [
            "GMV = 访客数 × 转化率 × 客单价",
            "CTR = 点击量 / 曝光量；CVR = 成交人数 / 访客数",
            "AOV（客单价）= GMV / 订单数；ROI = 收入 / 投入",
            "分析问题时要先判断是流量问题、转化问题、还是客单价问题",
        ],
    },
    "广告投放及流量获取": {
        "summary": "建立‘自然流量 + 付费流量 + 内容流量’的组合思维，理解投放不是花钱买量，而是买更高质量的转化。",
        "points": [
            "常见指标：CPC、CPM、CTR、CVR、CPA、ROAS、ACOS",
            "关注人群定向、素材点击率、落地页承接和预算分配",
            "流量异常时优先拆分渠道、设备、素材、时段和人群",
            "不要只看曝光，要看成本与最终成交质量",
        ],
    },
    "竞品分析": {
        "summary": "从价格、卖点、素材、评价、活动和渠道布局六个维度做竞品分析，目标是找到差异化机会。",
        "points": [
            "先选核心竞品，再看同价位竞品和替代型竞品",
            "重点看：主图、标题关键词、价格策略、评论痛点、活动节奏",
            "竞品分析不是抄作业，而是识别用户真实偏好",
            "输出要能落到‘我们接下来改什么’",
        ],
    },
    "A/B Test": {
        "summary": "通过实验验证假设，避免拍脑袋运营。要清楚实验对象、实验指标、实验周期和样本量。",
        "points": [
            "先提出明确假设，再只改一个核心变量",
            "常见实验对象：主图、标题、价格、优惠券、按钮文案、落地页结构",
            "核心结果看统计显著性，也要看业务意义",
            "实验失败也有价值，关键是沉淀可复用结论",
        ],
    },
    "商品页面设计": {
        "summary": "商品页面是转化中枢，目标是让用户快速建立‘我需要、我信任、我现在就买’的判断。",
        "points": [
            "页面结构：首屏卖点、核心利益点、证据补强、评价信任、行动引导",
            "主图要回答‘这是什么、适合谁、为什么值得买’",
            "详情页不要只堆参数，要翻译成用户收益",
            "差评和退款原因是优化页面的重要依据",
        ],
    },
    "大促与活动运营策略": {
        "summary": "活动运营不是单天爆发，而是预热、蓄水、爆发、复盘的完整链路管理。",
        "points": [
            "提前规划人群、货品、预算、资源位与内容节奏",
            "大促要兼顾拉新、转化与复购，不只盯销售额",
            "重点看预热收藏加购、活动当天转化、活动后退款与复购",
            "活动结束后必须复盘：什么有效、什么无效、什么可复制",
        ],
    },
    "国内电商平台细分及规则": {
        "summary": "理解货架电商、内容电商和社交电商的差异，明确不同平台的分发逻辑与运营重点。",
        "points": [
            "淘宝/天猫：搜索与货架逻辑强，重点是关键词、转化和店铺权重",
            "京东：履约与品质心智强，适合标准化品牌商品",
            "拼多多：价格力和活动驱动更强，重视点击与低价转化",
            "抖音/小红书：内容种草与推荐流量更强，重点是内容承接和转化闭环",
        ],
    },
    "国外电商平台细分及规则": {
        "summary": "跨境电商要同时理解平台规则、本地化习惯、物流时效和广告机制。",
        "points": [
            "Amazon：搜索与Listing优化极关键，关注Review与ACOS",
            "TikTok Shop：内容与达人带货更重要，强依赖素材质量",
            "Shopify：独立站强调品牌沉淀、站内转化与复购",
            "做海外平台要特别关注站点差异、语言本地化和退货规则",
        ],
    },
    "AI通识课": {
        "summary": "AI可以帮助运营做诊断、总结、生成与自动化，但不能替代业务判断。",
        "points": [
            "典型应用：日报总结、评论归因、竞品拆解、素材初稿、数据异常解释",
            "高质量Prompt要说清背景、问题、数据、输出格式和决策目标",
            "AI输出必须二次校验，尤其是数据结论与业务建议",
            "最好的用法不是替人思考，而是提升分析效率与覆盖面",
        ],
    },
}

DEFAULT_STATES = {
    "page": "home",
    "selected_knowledge_base": None,
    "is_logged_in": False,
    "user_name": "",
    "user_age": 0,
    "completed_courses": [],
    "course_progress": 0,
    "debug_history": [],
    "last_debug_result": None,
    "debug_input": "",
}

for k, v in DEFAULT_STATES.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "page" in st.query_params:
    st.session_state.page = st.query_params["page"]


# =========================
# 工具函数
# =========================
def go_home():
    st.session_state.page = "home"
    st.query_params.clear()


def go_module():
    st.session_state.page = "module"
    st.query_params["page"] = "module"


def go_course():
    st.session_state.page = "course"
    st.query_params["page"] = "course"


def go_ai_debug():
    st.session_state.page = "ai_debug"
    st.query_params["page"] = "ai_debug"


def go_login():
    st.session_state.page = "login"
    st.query_params["page"] = "login"


def go_user_profile():
    st.session_state.page = "user_profile"
    st.query_params["page"] = "user_profile"


def update_course_progress() -> None:
    completed_count = len(st.session_state.get("completed_courses", []))
    total_count = len(KNOWLEDGE_MODULES)
    progress = int(round(completed_count / total_count * 100)) if total_count else 0
    st.session_state.course_progress = progress


def select_knowledge_base(name: str) -> None:
    st.session_state.selected_knowledge_base = name
    if name not in st.session_state.completed_courses:
        st.session_state.completed_courses.append(name)
        update_course_progress()


def mock_wechat_login() -> None:
    st.session_state.is_logged_in = True
    st.session_state.user_name = "刘同学"
    st.session_state.user_age = 23
    update_course_progress()


def get_openai_client() -> Optional[OpenAI]:
    if OpenAI is None:
        return None
    if not OPENAI_API_KEY:
        return None
    try:
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        return None


def fallback_debug(question: str) -> Dict[str, Any]:
    q = question.strip()
    lower_q = q.lower()

    direction = "流量获取侧"
    basis = [
        "当前为降级演示模式，以下判断基于问题关键词进行规则化分析。",
        "建议后续接入真实后台数据（GMV、CTR、CVR、退款率、分端数据）再做更精确诊断。",
    ]
    suggestions = [
        "先把问题拆成流量、点击、转化、客单价、履约五段漏斗。",
        "优先按渠道、设备、商品、时段、人群进行分组排查。",
    ]
    metrics = ["GMV", "CTR", "CVR", "客单价", "退款率"]

    if any(word in q for word in ["支付", "安卓", "下单失败", "结算", "bug", "无法付款"]):
        direction = "产品/技术异常"
        basis = [
            "问题描述中出现支付、安卓、下单失败等关键词，优先怀疑技术链路异常。",
            "如果苹果端正常、安卓端异常，通常需要分端查看支付页面、SDK、版本更新与埋点日志。",
            "此类问题不能只看GMV，需要同步看支付成功率、下单提交成功率与错误码分布。",
        ]
        suggestions = [
            "立即分OS、App版本、支付方式拉取支付成功率，确认异常是否集中在安卓端。",
            "让技术排查支付页改版、SDK升级、接口超时与表单校验问题。",
            "短期先用公告、优惠补偿或替代支付路径降低损失。",
        ]
        metrics = ["支付成功率", "提交订单成功率", "错误码分布", "安卓/苹果分端CVR"]
    elif any(word in q for word in ["点击率", "曝光高", "没人点", "素材", "广告", "投放"]):
        direction = "广告/素材问题"
        basis = [
            "高曝光低点击通常优先指向素材吸引力、人群定向或标题卖点问题。",
            "如果CTR下降但落地页转化稳定，问题更可能在创意端而不是商品页。",
        ]
        suggestions = [
            "先对比不同素材、不同人群和不同渠道CTR差异。",
            "重做首图和前三秒表达，突出核心卖点、优惠和使用场景。",
            "做小流量A/B Test，先验证素材再放量。",
        ]
        metrics = ["CTR", "CPC", "素材点击率", "分人群CTR", "素材消耗占比"]
    elif any(word in q for word in ["转化率", "详情页", "加购", "商品页", "跳失"]):
        direction = "商品页面/转化承接问题"
        basis = [
            "如果流量变化不大但转化率下滑，通常优先排查商品页、价格、优惠或评价信任。",
            "加购高但支付低，说明用户有兴趣但最后决策环节存在阻碍。",
        ]
        suggestions = [
            "检查主图、标题、卖点表达、价格锚点、券后价与评价区。",
            "对详情页首屏和利益点模块做A/B Test。",
            "看差评和客服咨询高频问题，把疑虑前置到页面里。",
        ]
        metrics = ["CVR", "加购率", "详情页停留时长", "跳失率", "支付转化率"]
    elif any(word in q for word in ["大促", "618", "双11", "活动", "预热"]):
        direction = "活动策略与节奏问题"
        basis = [
            "活动问题往往不是单点异常，而是预热、货品、价格和资源位协同不到位。",
            "需要把活动拆成预热期、爆发期、返场期分别看数据。",
        ]
        suggestions = [
            "复盘预热收藏加购、直播间停留、站外引流和主推货品承接。",
            "确认主推SKU库存与优惠门槛是否匹配用户预期。",
            "把活动复盘结构化沉淀为下次可复用模板。",
        ]
        metrics = ["预热收藏加购", "活动CVR", "活动ROI", "主推SKU售罄率", "退款率"]
    elif any(word in lower_q for word in ["amazon", "tiktok shop", "shopify", "listing", "acos"]):
        direction = "海外平台运营问题"
        basis = [
            "问题中出现海外平台关键词，需要同时考虑平台规则、本地化内容与物流履约。",
            "不同平台诊断逻辑不同：Amazon偏搜索与Listing，TikTok Shop偏内容与达人。",
        ]
        suggestions = [
            "先明确平台类型，再拆解是流量、页面、广告还是物流问题。",
            "核查评价星级、物流时效、退货率和广告花费效率。",
            "对标题、卖点和素材做本地化改写。",
        ]
        metrics = ["ACOS/ROAS", "Listing CVR", "星级评分", "物流时效", "退货率"]

    return {
        "problem_direction": direction,
        "core_judgement": f"基于当前问题描述，优先怀疑【{direction}】出现异常，需要先做分层排查，再决定具体修复动作。",
        "basis": basis,
        "fix_suggestions": suggestions,
        "key_metrics": metrics,
        "follow_up_questions": [
            "这个问题从什么时候开始出现？是否有版本、活动或素材的变更？",
            "异常是全量发生，还是集中在某个渠道、人群、商品或设备端？",
        ],
    }


def debug_with_ai(question: str) -> Dict[str, Any]:
    client = get_openai_client()
    if client is None:
        return fallback_debug(question)

    schema = {
        "type": "object",
        "properties": {
            "problem_direction": {"type": "string"},
            "core_judgement": {"type": "string"},
            "basis": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 6},
            "fix_suggestions": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 6},
            "key_metrics": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 6},
            "follow_up_questions": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
        },
        "required": [
            "problem_direction",
            "core_judgement",
            "basis",
            "fix_suggestions",
            "key_metrics",
            "follow_up_questions",
        ],
        "additionalProperties": False,
    }

    developer_prompt = """
你是“AI运营问题诊断Debug系统”的核心分析引擎，服务对象是电商运营新人和业务负责人。
你的目标不是泛泛而谈，而是给出：
1. 问题最可能出现的方向判断；
2. 有依据的诊断逻辑；
3. 明确可执行的修正建议；
4. 建议继续追问的数据口径。

要求：
- 回答必须使用中文。
- 依据不能写成‘根据经验’，而要写成具体的业务推理，例如流量、转化、商品页、投放、活动、技术、履约等链路判断。
- 如果用户信息不足，要明确指出需要补充哪些数据。
- 避免空话套话，输出要适合运营新人直接拿去排查。
"""

    user_prompt = f"""
请诊断下面这个电商运营问题，并严格按JSON返回：
问题：{question}

输出字段说明：
- problem_direction：最可能出问题的方向，例如广告投放、商品页面、活动策略、产品技术异常、履约问题、用户侧问题等
- core_judgement：一句话总体判断
- basis：列出3-6条判断依据
- fix_suggestions：列出3-6条修正建议
- key_metrics：建议优先查看的关键指标
- follow_up_questions：如果要继续定位，需要补充问用户的2-4个问题
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "ops_debug_schema", "schema": schema, "strict": True},
            },
            temperature=0.4,
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception:
        return fallback_debug(question)


# =========================
# 样式
# =========================
st.markdown(
    """
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
    padding: 0;
}

.page-wrapper { width: 100%; min-height: 100vh; color: #FFFFFF; }
.navbar { position: sticky; top: 0; z-index: 999; width: 100%; background: rgba(6,19,38,0.82); backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.08); }
.nav-inner { max-width: 1400px; margin: 0 auto; padding: 18px 40px; display: flex; align-items: center; justify-content: space-between; }
.brand { font-size: 22px; font-weight: 700; color: #FFFFFF; }
.nav-actions { display: flex; gap: 12px; align-items: center; }
.nav-btn { padding: 10px 18px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.18); background: rgba(255,255,255,0.05); color: #FFFFFF; font-size: 14px; font-weight: 500; text-decoration: none; }
.nav-btn.primary { background: linear-gradient(135deg, #2F7BFF 0%, #58A6FF 100%); border: none; box-shadow: 0 10px 24px rgba(47,123,255,0.25); }
.hero { max-width: 1400px; margin: 0 auto; min-height: 78vh; display: flex; align-items: center; padding: 50px 40px 80px 40px; position: relative; overflow: hidden; }
.hero::before { content: ""; position: absolute; width: 560px; height: 560px; right: -120px; top: 40px; background: radial-gradient(circle, rgba(69,147,255,0.28) 0%, rgba(69,147,255,0.06) 42%, rgba(69,147,255,0.00) 70%); border-radius: 50%; }
.hero::after { content: ""; position: absolute; width: 380px; height: 380px; left: -60px; bottom: 40px; background: radial-gradient(circle, rgba(117,181,255,0.16) 0%, rgba(117,181,255,0.03) 45%, rgba(117,181,255,0.00) 72%); border-radius: 50%; }
.hero-content { position: relative; z-index: 2; max-width: 780px; }
.hero-tag { display: inline-block; padding: 8px 14px; border-radius: 999px; font-size: 13px; color: #BFD9FF; border: 1px solid rgba(117,181,255,0.22); background: rgba(255,255,255,0.05); margin-bottom: 26px; }
.hero-title { font-size: 56px; line-height: 1.15; font-weight: 800; margin-bottom: 20px; white-space: nowrap; }
.hero-subtitle { font-size: 22px; line-height: 1.8; color: #D5E6FF; margin-bottom: 36px; max-width: 1100px; }
.hero-actions { display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }
.link-btn { display: inline-block; padding: 16px 28px; border-radius: 14px; font-size: 16px; font-weight: 700; text-decoration: none; border: 1px solid transparent; }
.link-btn-primary { background: linear-gradient(135deg, #2F7BFF 0%, #5EAFFF 100%); color: #FFFFFF !important; box-shadow: 0 14px 30px rgba(47,123,255,0.30); }
.link-btn-secondary { background: rgba(255,255,255,0.06); color: #FFFFFF !important; border: 1px solid rgba(255,255,255,0.16); }
.feature-strip { max-width: 1400px; margin: -10px auto 0 auto; padding: 0 40px 80px 40px; position: relative; z-index: 3; }
.feature-card, .module-card, .panel-card, .profile-card, .debug-card, .history-card, .login-card, .recommend-card { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.10); border-radius: 24px; box-shadow: 0 18px 40px rgba(7, 28, 61, 0.14); padding: 26px 28px; backdrop-filter: blur(10px); margin-bottom: 24px; }
.feature-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
.feature-title { font-size: 18px; font-weight: 700; color: #FFFFFF; margin-bottom: 8px; }
.feature-desc { font-size: 14px; color: #C9DAF5; line-height: 1.8; }
.footer { padding: 28px 40px 40px 40px; }
.footer-inner { max-width: 1400px; margin: 0 auto; display: flex; justify-content: center; gap: 18px; flex-wrap: wrap; }
.footer-btn { background: rgba(255,255,255,0.08); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.12); border-radius: 12px; padding: 12px 20px; font-size: 14px; font-weight: 600; text-decoration: none; }
.module-page, .course-page, .debug-page, .login-page, .profile-page { max-width: 1250px; margin: 0 auto; padding: 70px 40px 50px 40px; color: #FFFFFF; }
.module-header, .page-header { text-align: center; margin-bottom: 34px; }
.module-title, .page-title { font-size: 46px; font-weight: 800; margin-bottom: 16px; }
.module-subtitle, .page-subtitle { font-size: 19px; color: #CFE0FB; line-height: 1.8; }
.module-card-title { font-size: 28px; font-weight: 800; margin-bottom: 14px; color: #FFFFFF; text-align: center; }
.module-card-desc { font-size: 16px; line-height: 1.9; color: #D7E4FA; margin-bottom: 24px; text-align: center; }
.back-btn-area { margin-top: 32px; display: flex; justify-content: center; }
.tip-box, .scenario-box, .summary-box { background: rgba(47,123,255,0.10); border: 1px solid rgba(94,175,255,0.16); color: #E8F2FF; border-radius: 18px; padding: 18px 20px; line-height: 1.9; }
.course-layout { display: grid; grid-template-columns: 320px 1fr; gap: 28px; }
.course-placeholder { min-height: 120px; display: flex; flex-direction: column; justify-content: center; }
.debug-history-wrap { margin-top: 24px; }
.side-note { color: #AFC8EF; font-size: 14px; line-height: 1.8; margin-top: 14px; }
.section-title { font-size: 24px; font-weight: 800; margin-bottom: 16px; color: #FFFFFF; }
.kb-title { font-size: 34px; font-weight: 800; margin-bottom: 12px; color: #FFFFFF; }
.kb-summary { font-size: 17px; color: #D7E4FA; line-height: 1.9; margin-bottom: 16px; }
.kb-list li { margin-bottom: 12px; color: #E6F0FF; line-height: 1.8; }
.progress-track { width: 100%; height: 12px; background: rgba(255,255,255,0.18); border-radius: 999px; overflow: hidden; margin: 16px 0 12px 0; }
.progress-fill { height: 100%; border-radius: 999px; background: linear-gradient(90deg, #4A84FF 0%, #73A9FF 100%); }
.progress-text { color: #DDEBFF; font-size: 15px; margin-top: 10px; line-height: 1.8; }
.info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.info-item { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 18px; }
.info-label { color: #BFD9FF; font-size: 14px; margin-bottom: 8px; }
.info-value { color: #FFFFFF; font-size: 28px; font-weight: 800; }
.history-item { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.07); border-radius: 18px; padding: 18px; margin-bottom: 16px; }
.profile-page .profile-card, .profile-page .recommend-card { margin-bottom: 28px; }
.history-title { font-size: 18px; font-weight: 700; color: #FFFFFF; margin-bottom: 10px; }
.tag-wrap { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
.tag-chip { padding: 8px 14px; border-radius: 999px; font-size: 13px; color: #DDEBFF; border: 1px solid rgba(117,181,255,0.22); background: rgba(255,255,255,0.05); }
.stButton > button { width: 100%; border-radius: 16px; font-weight: 700; border: none; padding: 0.9rem 1rem; font-size: 17px; background: linear-gradient(135deg, #2F7BFF 0%, #5EAFFF 100%); color: white; box-shadow: 0 12px 28px rgba(47,123,255,0.25); }
.stButton > button:hover { filter: brightness(1.04); }
.secondary-button .stButton > button { background: rgba(255,255,255,0.08) !important; color: #FFFFFF !important; border: 1px solid rgba(255,255,255,0.14) !important; box-shadow: none !important; }
textarea { border-radius: 16px !important; }
.stTextArea label p { color: #FFFFFF !important; font-size: 18px !important; font-weight: 700 !important; }
@media (max-width: 992px) {
    .hero { padding: 40px 20px 70px 20px; min-height: 72vh; }
    .hero-title { font-size: 44px; }
    .hero-subtitle { font-size: 18px; }
    .feature-grid, .info-grid, .course-layout { grid-template-columns: 1fr; }
    .module-page, .course-page, .debug-page, .login-page, .profile-page { padding: 60px 20px 40px 20px; }
}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# 页面渲染
# =========================
def render_home() -> None:
    st.markdown(
        """
<div class="page-wrapper">
<div class="navbar">
    <div class="nav-inner">
        <div class="brand">AI电商运营训练平台</div>
        <div class="nav-actions">
            <div class="nav-btn">语言</div>
            <a href="?page=login" class="nav-btn primary">登录/注册</a>
        </div>
    </div>
</div>
<section class="hero">
    <div class="hero-content">
        <div class="hero-tag">AI E-Commerce Ops Demo · 训练 + 诊断 + 进度追踪</div>
        <div class="hero-title">AI驱动・电商运营实战训练平台</div>
        <div class="hero-subtitle">面向电商运营新同学，通过“新兵运营上岗加速器”快速补齐电商运营方法论，再用“AI运营问题诊断Debug系统”对于真实业务进行排障，定位问题方向并输出修正建议。</div>
        <div class="hero-actions">
            <a href="?page=module" class="link-btn link-btn-primary">立即开始</a>
            <a href="#" class="link-btn link-btn-secondary">预约演示</a>
        </div>
    </div>
</section>
<section class="feature-strip">
    <div class="feature-card">
        <div class="feature-grid">
            <div>
                <div class="feature-title">为什么使用平台</div>
                <div class="feature-desc">把分散的电商运营知识、异常诊断经验和学习进度统一到一个平台里，帮助新人更快进入业务状态。</div>
            </div>
            <div>
                <div class="feature-title">你将体验什么</div>
                <div class="feature-desc">从核心指标、平台规则到广告投放和活动复盘，再到真实问题的AI诊断与修正建议输出。</div>
            </div>
            <div>
                <div class="feature-title">如何开始使用</div>
                <div class="feature-desc">先进入“新兵运营上岗加速器”补齐知识，再进入“AI运营问题诊断Debug系统”输入你的业务问题并获得有依据的分析。</div>
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
""",
        unsafe_allow_html=True,
    )


def render_module_page() -> None:
    st.markdown(
        """
<div class="module-page">
    <div class="module-header">
        <div class="hero-tag">AI E-Commerce Ops Demo · 功能选择页</div>
        <div class="module-title">欢迎进入电商运营训练营</div>
        <div class="module-subtitle">请选择模块，开启你的学习与实战诊断流程。</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    left_space, col1, col2, right_space = st.columns([1, 3, 3, 1], gap="large")
    with col1:
        st.markdown(
            """
<div class="module-card">
    <div class="module-card-title">新兵运营上岗加速器</div>
    <div class="module-card-desc">围绕指标、平台规则、投放、竞品、商品页与大促策略，帮助新人快速建立系统化知识框架。</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("进入新兵运营上岗加速器", use_container_width=True, key="go_course"):
            go_course()
            st.rerun()

    with col2:
        st.markdown(
            """
<div class="module-card">
    <div class="module-card-title">AI运营问题诊断Debug系统</div>
    <div class="module-card-desc">输入真实运营问题，调用大模型给出问题方向判断、依据、关键指标和修正建议。</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.button("进入AI运营问题诊断Debug系统", use_container_width=True, key="go_debug"):
            go_ai_debug()
            st.rerun()

    st.markdown("<div class='back-btn-area'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([2.3, 1.4, 2.3])
    with mid:
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("返回首页", use_container_width=True, key="back_home_module"):
            go_home()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_course_page() -> None:
    update_course_progress()
    st.markdown(
        """
<div class="course-page">
    <div class="page-header">
        <div class="hero-tag">AI E-Commerce Ops Demo · 知识模块</div>
        <div class="page-title">新兵运营上岗加速器</div>
        <div class="page-subtitle">点击左侧知识库模块即可学习，并自动记录学习进度到用户中心。</div>
    </div>
""",
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns([1.05, 2.4], gap="large")

    with left_col:
        for i, module_name in enumerate(KNOWLEDGE_MODULES):
            if st.button(module_name, use_container_width=True, key=f"kb_{i}"):
                select_knowledge_base(module_name)
                st.rerun()
        st.markdown(
            f"""
<div class="side-note">
当前已学习 {len(st.session_state.completed_courses)} / {len(KNOWLEDGE_MODULES)} 个模块。<br>
课程进度会同步记录到登录后的用户界面。
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown('<div style="height:12px"></div><div class="secondary-button">', unsafe_allow_html=True)
        if st.button("返回功能选择页", use_container_width=True, key="back_module_course"):
            go_module()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        selected = st.session_state.selected_knowledge_base
        if not selected:
            st.markdown(
                """
<div class="kb-title">请选择知识模块</div>
<div class="kb-summary">点击左侧任意课程按钮后，这里会显示统一的阶段性说明。</div>
""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f'<div class="kb-title">{selected}</div>', unsafe_allow_html=True)
            st.markdown(
                f"""
<div class="summary-box" style="margin-top:12px;">
当前阶段仅实现课程按钮展示效果，后续可继续扩展为课程详情页、学习进度条、知识测验与AI答疑等功能。<br>
当前累计学习进度：{st.session_state.course_progress}%
</div>
""",
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


def render_ai_debug_page() -> None:
    st.markdown(
        """
<div class="debug-page">
    <div class="page-header">
        <div class="hero-tag">AI E-Commerce Ops Demo · Debug系统</div>
        <div class="page-title">AI运营问题诊断Debug系统</div>
        <div class="page-subtitle">输入你的真实运营问题，系统将判断最可能出问题的方向，并给出有依据的修正建议。</div>
    </div>
""",
        unsafe_allow_html=True,
    )

    st.text_area(
        "请输入你的运营问题",
        key="debug_input",
        height=180,
        placeholder="例如：今天店铺流量正常，但商品转化率突然下滑，详情页昨天刚换过新版本，应该先排查什么？",
    )

    col1, col2, col3 = st.columns([1.8, 1.8, 1.8], gap="large")
    with col1:
        submit = st.button("开始诊断", use_container_width=True, key="run_debug")
    with col2:
        if st.button("清空问题", use_container_width=True, key="clear_debug"):
            st.session_state.debug_input = ""
            st.rerun()
    with col3:
        if st.button("返回功能选择页", use_container_width=True, key="back_module_debug"):
            go_module()
            st.rerun()

    if submit:
        question = st.session_state.debug_input.strip()
        if not question:
            st.warning("请先输入具体的运营问题。")
        else:
            with st.spinner("AI正在诊断问题..."):
                result = debug_with_ai(question)
            st.session_state.last_debug_result = result
            st.session_state.debug_history.insert(0, {"question": question, "result": result})
            st.session_state.debug_history = st.session_state.debug_history[:6]
            st.rerun()

    result = st.session_state.get("last_debug_result")
    if result:
        basis_html = "".join([f"<li>{x}</li>" for x in result["basis"]])
        fix_html = "".join([f"<li>{x}</li>" for x in result["fix_suggestions"]])
        metric_html = "".join([f"<div class='tag-chip'>{x}</div>" for x in result["key_metrics"]])
        follow_html = "".join([f"<li>{x}</li>" for x in result["follow_up_questions"]])

        st.markdown(
            f"""
<div class="debug-card">
    <div class="section-title">诊断结果</div>
    <div class="summary-box"><b>问题方向判断：</b>{result['problem_direction']}<br><br><b>总体判断：</b>{result['core_judgement']}</div>
    <div style="height:16px"></div>
    <div class="section-title">判断依据</div>
    <ul class="kb-list">{basis_html}</ul>
    <div class="section-title">修正建议</div>
    <ul class="kb-list">{fix_html}</ul>
    <div class="section-title">建议优先看的关键指标</div>
    <div class="tag-wrap">{metric_html}</div>
    <div class="section-title" style="margin-top:18px;">建议继续补充的信息</div>
    <ul class="kb-list">{follow_html}</ul>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown('<div class="history-card debug-history-wrap"><div class="section-title">最近诊断记录</div>', unsafe_allow_html=True)
    if not st.session_state.debug_history:
        st.markdown('<div class="scenario-box">当前还没有诊断记录。提交一次问题后，这里会自动保存最近历史。</div></div>', unsafe_allow_html=True)
    else:
        for idx, item in enumerate(st.session_state.debug_history, start=1):
            st.markdown(
                f"""
<div class="history-item">
    <div class="history-title">记录 {idx}</div>
    <div class="kb-summary"><b>问题：</b>{item['question']}</div>
    <div class="kb-summary"><b>方向判断：</b>{item['result']['problem_direction']}</div>
    <div class="kb-summary"><b>总体判断：</b>{item['result']['core_judgement']}</div>
</div>
""",
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_login_page() -> None:
    st.markdown(
        """
<div class="login-page">
    <div class="login-card">
        <div class="hero-tag">AI E-Commerce Ops Demo · 登录页</div>
        <div class="page-title" style="font-size:40px;">欢迎登录</div>
        <div class="page-subtitle">登录后可查看“新兵运营上岗加速器”学习进度，以及最近的诊断记录概览。</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    _, mid, _ = st.columns([2.5, 2.2, 2.5])
    with mid:
        if st.button("微信登录", use_container_width=True, key="wechat_login_btn"):
            mock_wechat_login()
            st.success("模拟授权成功")
            go_user_profile()
            st.rerun()

    _, mid2, _ = st.columns([2.5, 2.2, 2.5])
    with mid2:
        st.markdown('<div class="secondary-button">', unsafe_allow_html=True)
        if st.button("返回首页", use_container_width=True, key="back_home_login"):
            go_home()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_user_profile_page() -> None:
    if not st.session_state.get("is_logged_in"):
        go_login()
        st.rerun()

    update_course_progress()
    completed_courses = st.session_state.get("completed_courses", [])
    history = st.session_state.get("debug_history", [])

    st.markdown(
        f"""
<div class="profile-page">
<div class="profile-card">
    <div class="hero-tag">AI E-Commerce Ops Demo · 用户中心</div>
    <div class="page-title" style="font-size:40px;">用户学习中心</div>
    <div class="page-subtitle">这里会记录你的知识学习进度与最近的运营问题诊断记录。</div>
</div>

<div class="profile-card">
    <div class="section-title">用户基础信息</div>
    <div class="info-grid">
        <div class="info-item">
            <div class="info-label">姓名</div>
            <div class="info-value">{st.session_state.user_name}</div>
        </div>
        <div class="info-item">
            <div class="info-label">年龄</div>
            <div class="info-value">{st.session_state.user_age}</div>
        </div>
    </div>
</div>

<div class="profile-card">
    <div class="section-title">新兵运营上岗加速器学习进度</div>
    <div class="progress-track"><div class="progress-fill" style="width:{st.session_state.course_progress}%;"></div></div>
    <div class="progress-text">当前课程完成度：{st.session_state.course_progress}%（已学习 {len(completed_courses)} / {len(KNOWLEDGE_MODULES)} 个模块）</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if completed_courses:
        chips = "".join([f"<div class='tag-chip'>{x}</div>" for x in completed_courses])
        st.markdown(f'<div class="profile-card"><div class="section-title">已学习模块</div><div class="tag-wrap">{chips}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="profile-card"><div class="section-title">已学习模块</div><div class="scenario-box">你还没有学习任何模块，前往“新兵运营上岗加速器”开始学习后，这里会自动更新。</div></div>', unsafe_allow_html=True)

    if history:
        items = []
        for item in history[:3]:
            items.append(
                f"<div class='history-item'><div class='history-title'>{item['result']['problem_direction']}</div><div class='kb-summary'><b>问题：</b>{item['question']}</div><div class='kb-summary'><b>判断：</b>{item['result']['core_judgement']}</div></div>"
            )
        st.markdown(f"<div class='profile-card'><div class='section-title'>最近诊断记录</div>{''.join(items)}</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="profile-card"><div class="section-title">最近诊断记录</div><div class="scenario-box">你还没有使用过AI运营问题诊断Debug系统。</div></div>', unsafe_allow_html=True)

    if st.session_state.course_progress >= 100:
        st.markdown(
            """
<div class="recommend-card">
    <div class="hero-tag">成长提醒</div>
    <div class="kb-title" style="font-size:32px;">已完成全部知识模块学习</div>
    <div class="kb-summary">建议下一步高频使用AI运营问题诊断Debug系统，把知识框架转化为真实业务排障能力。</div>
</div>
""",
            unsafe_allow_html=True,
        )

    _, mid1, mid2, _ = st.columns([1.5, 2.2, 2.2, 1.5], gap="large")
    with mid1:
        if st.button("前往新兵运营上岗加速器", use_container_width=True, key="go_course_profile"):
            go_course()
            st.rerun()
    with mid2:
        if st.button("返回首页", use_container_width=True, key="back_home_profile"):
            go_home()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# 路由
# =========================
if st.session_state.page == "course":
    render_course_page()
elif st.session_state.page == "ai_debug":
    render_ai_debug_page()
elif st.session_state.page == "login":
    render_login_page()
elif st.session_state.page == "user_profile":
    render_user_profile_page()
elif st.session_state.page == "module":
    render_module_page()
else:
    render_home()
