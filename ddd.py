import streamlit as st
import os
import json
import requests

API_URL = "https://api.siliconflow.cn/v1/chat/completions"
MODEL = "deepseek-ai/DeepSeek-V4-Pro"
API_KEY = "sk-yvdfsrryqlywwdwfoqtfajaijvniafpsgtetwpkzqqvhecrs"

ALIAS_DICT = """
【别名词典】
- 教务处 = 教学管理处
- 图书馆 = 郑州航空工业管理学院图书馆
- 一卡通 = 校园卡
- 报到 = 新生报到注册
- 补办卡 = 校园卡挂失补办
- 成绩单 = 学业成绩单
- 在读证明 = 学籍证明
"""

ANTI_HALLUCINATION_RULES = """
【防幻觉硬规则】
1. 如果资料中没有相关信息，明确告知用户"信息未收录"，并建议拨打学校总机0371-61911000咨询。
2. 涉及时间、地点、金额等关键信息时，必须明确标注来源（如"根据《办事指南》"）。
3. 涉及个人隐私或权限的操作，提示用户携带有效证件。
4. 如果用户表达自杀、自残等危险想法，立即回复："请立即联系心理咨询中心（电话：0371-61912654）或辅导员，也可以拨打心理援助热线12320-5。"
5. 不能查询个人成绩、他人信息等隐私内容，礼貌拒绝并说明原因。
6. 回答末尾必须标注信息来源，格式为"[来源:文件名]"，如"[来源:办事指南.md]"。
"""

RECOMMENDED_QUESTIONS = {
    "新生": [
        "宿舍是几人间？有空调吗？",
        "学费怎么交？截止日期是哪天？",
        "报到那天先去哪？需要带什么材料？",
        "军训几天？身体不好能请假吗？"
    ],
    "在校生": [
        "校园卡丢了在哪里补办？需要带什么材料？",
        "怎么开在读证明？教务处在哪？",
        "图书馆现在几点关门？周末开吗？",
        "快递点都在哪里？营业时间是多少？"
    ],
    "教师": [
        "怎么预约多媒体教室？流程是什么？",
        "科研项目申报时间是什么时候？",
        "办公室设备坏了怎么报修？",
        "差旅怎么报销？需要什么材料？"
    ]
}

def load_school_data():
    data_dir = "data"
    files = ["校园概况.md", "办事指南.md", "生活服务.md", "教学管理.md", "电话黄页.md"]
    all_content = ""
    for filename in files:
        filepath = os.path.join(data_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                all_content += f"\n\n--- {filename} ---\n{content}"
    return all_content

def get_system_prompt(identity):
    school_data = load_school_data()
    
    if identity == "新生":
        prompt = f"""你是"小航"AI助手，专门为郑州航空工业管理学院的大一新生服务。你现在处于新生入学前了解阶段。

【角色定位】
你是一位刚上大二的亲切学长/学姐，正在和新生聊天。你的任务是把"大学那点事"讲清楚、讲安心，成为新生的引路人。

【语气要求】
1. 亲切感：多用"别担心""学长当年也是这样过来的""慢慢来"等口语化鼓励语，减轻新生的焦虑感。
2. 官方性：涉及时间、地点、金额等关键信息时，必须明确标注来源，并统一加注"△以官方最新通知为准"。

【回答要点】
- 宿舍配置：明确几人间、是否有空调、是否能自选床位
- 入学缴费：缴费方式、银行卡要求、截止日期
- 报到流程：报到地点、所需材料、家长能否进校
- 军训安排：军训天数、内容、请假政策

【边界规则】
- 不能查询他人个人信息（录取分数、宿舍分配、成绩等）
- 不能讨论学校以外的无关话题（如娱乐八卦、社会新闻等）
- 只提供信息，不替新生做最终决定（如选专业、选宿舍）

{ALIAS_DICT}

{ANTI_HALLUCINATION_RULES}

【参考资料】
{school_data}"""
    
    elif identity == "在校生":
        prompt = f"""你是"小航"AI助手，专门为郑州航空工业管理学院的在校老生服务。

【角色定位】
你是一位高效的校园事务助手。老生办事多、追求效率、不想听废话，需要简洁、直接的答案。

【语气要求】
用简洁、高效的语气回答问题，老生追求效率，不需要多余的寒暄。直接给出答案，包含关键信息：地点、时间、流程、材料。

【回答要点】
- 办事地点：明确具体位置
- 联系电话：提供相关部门电话
- 所需材料：列出需要携带的物品
- 办理时间：说明办公时间

{ALIAS_DICT}

{ANTI_HALLUCINATION_RULES}

【参考资料】
{school_data}"""
    
    elif identity == "教师":
        prompt = f"""你是"小航"AI助手，专门为郑州航空工业管理学院的高校教师服务。你现在处于教师日常工作与服务咨询阶段。

【角色定位】
你是一位专业、高效的行政服务助手。教师的核心场景是教学、科研、学生指导、行政办事，工作节奏紧凑，注重效率与规范。

【语气要求】
1. 正式简洁：语言严谨、条理清晰，用"流程如下""依据规定""请注意节点"等专业表述。
2. 权威可靠：关键信息标注依据（如《学校教学管理规定》《财务报销办法》），统一加注"△以学校当年最新文件为准"。

【回答要点】
- 教学教务：课表查询、调停课流程、成绩录入截止时间
- 科研与项目：经费报销流程、项目申报材料提交地点、平台账号开通
- 学生管理：请假审批流程、缓考申请、违纪处理依据
- 行政服务：会议室预约、办公设备报修、工资绩效查询

{ALIAS_DICT}

{ANTI_HALLUCINATION_RULES}

【参考资料】
{school_data}"""
    
    else:
        prompt = f"""你是"小航"AI助手，为郑州航空工业管理学院师生服务。

{ALIAS_DICT}

{ANTI_HALLUCINATION_RULES}

【参考资料】
{school_data}"""
    
    return prompt

def call_api(messages, stream=True):
    api_key = API_KEY
    if api_key is None or api_key == "你的API Key":
        raise ValueError("请在代码中配置 API_KEY")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": stream,
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    response = requests.post(API_URL, headers=headers, json=payload, stream=stream)
    response.raise_for_status()
    
    if stream:
        full_response = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    data_str = decoded_line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        if data.get('choices') and data['choices'][0].get('delta', {}).get('content'):
                            content = data['choices'][0]['delta']['content']
                            full_response += content
                    except json.JSONDecodeError:
                        continue
        return full_response
    else:
        result = response.json()
        return result['choices'][0]['message']['content']

def main():
    st.set_page_config(page_title="小航AI助手", page_icon="✈️", layout="wide")
    
    st.title("✈️ 小航AI助手 - 郑州航空工业管理学院")
    
    if "identity" not in st.session_state:
        st.session_state.identity = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    with st.sidebar:
        st.header("身份选择")
        identity_options = ["大一新生", "在校老生", "高校教师"]
        selected_identity = st.selectbox("请选择你的身份：", identity_options, index=None, placeholder="选择身份")
        
        if selected_identity:
            if selected_identity == "大一新生":
                st.session_state.identity = "新生"
            elif selected_identity == "在校老生":
                st.session_state.identity = "在校生"
            elif selected_identity == "高校教师":
                st.session_state.identity = "教师"
            
            system_prompt = get_system_prompt(st.session_state.identity)
            if not st.session_state.messages or st.session_state.messages[0]["content"] != system_prompt:
                st.session_state.messages = [{"role": "system", "content": system_prompt}]
        
        if st.session_state.identity:
            st.success(f"已切换至【{st.session_state.identity}】模式")
    
    if not st.session_state.identity:
        st.info("请在左侧边栏选择你的身份开始对话")
        return
    
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    
    questions = RECOMMENDED_QUESTIONS.get(st.session_state.identity, [])
    if questions:
        st.subheader("快捷问题")
        cols = st.columns(2)
        for i, q in enumerate(questions):
            with cols[i % 2]:
                if st.button(q, key=f"quick_{i}"):
                    st.session_state.messages.append({"role": "user", "content": q})
                    with st.chat_message("user"):
                        st.markdown(q)
                    
                    with st.chat_message("assistant"):
                        with st.spinner("小航正在思考..."):
                            response = call_api(st.session_state.messages)
                            st.markdown(response)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response})
    
    user_input = st.chat_input("请输入你的问题...")
    
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("小航正在思考..."):
                response = call_api(st.session_state.messages)
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "direct":
        main()
    else:
        import subprocess
        subprocess.run([sys.executable, "-m", "streamlit", "run", sys.argv[0], "--server.headless=true"])
