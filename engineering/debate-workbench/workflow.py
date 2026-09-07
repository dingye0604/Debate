from dataclasses import dataclass

PHASES = ["辩题分析", "资料整合", "立论架构", "论据手册", "攻防模拟"]
FILES = ["01-辩题分析.md", "02-资料整合.md", "03-立论架构.md", "04-论据手册.md", "05-攻防手册.md"]

@dataclass(frozen=True)
class Step:
    key: str
    phase: int
    title: str
    instruction: str
    answer: bool = False
    search: bool = False
    plan: bool = False

STEPS = [
    Step("analysis", 0, "理解辩题与核心分歧", "按 skill 第一阶段拆解字面定义、学科视角、现实语境，分析三个核心问题。先给分析，再询问用户最重视的争议与解释。没有实际检索的定义、理论标明待核验。", answer=True),
    Step("research_plan", 1, "确认资料搜索方案", "先简述学理支撑、现实案例、选取视角三步法，制定三轮搜索方案：基础资料、深度资料、对方视角。queries 必须恰好提供三个有区分的具体检索词，分别用于三轮。将查询原文写入 section，让用户确认后执行。", plan=True),
    Step("research", 1, "研究资料与对方视角", "依据实际搜索结果整合资料，逐项给出来源编号、核心观点、相关性、双方价值、核验局限。明确三轮搜索结果与缺口，询问哪些方向需补充。不要把搜索摘要当作已经读过原文。", search=True),
    Step("definitions", 2, "讨论核心定义", "先询问用户拟采用的关键定义与边界，并提出一项可能的对方质疑；用户回答后再归纳方案。检查范围与权威依据。", answer=True),
    Step("arguments", 2, "建立主张与分论点", "先引导用户提出一句主张和约三个分论点，追问它们的关联及其中一个被驳倒时其他是否成立；回答后整理架构。", answer=True),
    Step("logic", 2, "检查论证链条", "逐个分论点讨论前提、证据与结论，向用户追问关键逻辑跳跃。按实际推理判断演绎、归纳、溯因，不能按辩题位置硬对应；避免循环论证。", answer=True),
    Step("burden", 2, "明确初步举证", "先询问用户哪些已知、哪些未知、哪些需要证明，哪个前提对方不会承认。回答后整理举证义务与替代论证路径。", answer=True),
    Step("values", 2, "确定价值倡导", "询问用户为谁的利益、主张什么价值、为什么值得倡导，回应后检验与定义、论点的一致性，形成价值倡导。", answer=True),
    Step("evidence_plan", 3, "确认针对性论据需求", "按已确认分论点列学理、数据、案例、专家论述需求。queries 给出最多三个针对性检索词，覆盖分论点；写进 section 供用户确认。", plan=True),
    Step("evidence", 3, "整理可用论据", "仅从提供的实际来源中按分论点整理论据，逐条包括类型、来源编号、内容、使用逻辑、使用时机、可能攻击、回应。无足够证据时明确缺口，不编数字或出版物。询问是否需补搜。", search=True),
    Step("attack_definitions", 4, "定义与价值攻防", "从对手口吻对定义或价值发起具体攻击，只提攻击并让用户先回答，绝不提前给回应。用户回答后点评、追问或完善，记录攻击与实际回答、教练建议。", answer=True),
    Step("attack_arguments", 4, "分论点与逻辑攻防", "针对主要分论点逐项提出具体逻辑攻击，请用户逐项回应，回答前不泄露反驳答案。回答后检查每个论点的防守，补充反弹利好、切割无关、指出双标的适用边界。", answer=True),
    Step("attack_evidence", 4, "论据可靠性攻防", "针对论据可靠性、典型性或理论适用性提出质疑，让用户先回应；再点评并记录防守和证据缺口。", answer=True),
    Step("cross_exam", 4, "质询演练", "模拟对方二辩提出有连贯目的的质询，先让用户回答，再评价如何守住定义和举证边界，记录练习。", answer=True),
    Step("free_debate", 4, "自由辩连续交锋", "模拟对方连续两到三个简短攻击，先让用户尝试快速回应，再帮助组织反击顺序与核心战场。", answer=True),
    Step("closing", 4, "提炼结辩方向", "请用户先概括本场胜负关键与核心交锋，回答后提供结辩方向与待补强事项，汇总已有攻防，不凭空宣称获胜。", answer=True),
]

def step_info(index):
    if index >= len(STEPS):
        return {"key": "complete", "phase": 4, "title": "备赛档案已完成"}
    s = STEPS[index]
    return {"key": s.key, "phase": s.phase, "title": s.title, "answer_required": s.answer, "search": s.search, "plan": s.plan}
