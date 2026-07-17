# -*- coding: utf-8 -*-
"""
小航AI助手 - 郑州航空工业管理学院校园问答系统
=============================================
基于Streamlit框架开发的Web版AI助手，支持多身份切换、RAG知识库检索、
对话历史管理、导出功能等。

主要功能：
1. 身份切换：支持大一新生、在校老生、高校教师三种身份
2. 智能问答：基于DeepSeek-V4-Pro模型进行问答
3. 知识库检索：从本地资料文件中检索相关信息
4. 对话管理：每个身份独立保存对话历史
5. 导出功能：支持Markdown和纯文本格式导出
6. 快捷提问：提供各身份专属的推荐问题按钮
7. 输入验证：禁止纯空格或纯特殊字符输入
8. 网络错误处理：快速提示网络连接问题

技术栈：
- Streamlit：Web界面框架
- requests：HTTP请求库
- DeepSeek-V4-Pro：AI模型
- 硅基流动平台：API服务提供商

作者：小航AI助手开发团队
日期：2026年7月
"""

import streamlit as st
import os
import json
import requests
from datetime import datetime
from docx import Document

# ==================== 全局配置 ====================
# API服务地址（硅基流动平台）
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
# 使用的AI模型
MODEL = "deepseek-ai/DeepSeek-V4-Pro"
# API密钥（请替换为你的密钥）
API_KEY = "sk-cymbwrotvdjtcbqpxvfrcojfiwlwuefpnktswzohudvtzxxy"

# ==================== 别名词典 ====================
# 用于处理用户输入中的同义词，确保准确匹配知识库
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

# ==================== 防幻觉规则 ====================
# 确保AI回答的准确性和安全性，防止生成虚假信息
ANTI_HALLUCINATION_RULES = """
【防幻觉硬规则】
1. 如果资料中没有相关信息，明确告知用户"信息未收录"，并建议拨打学校总机0371-61911000咨询。
2. 涉及时间、地点、金额等关键信息时，必须明确标注来源（如"根据《办事指南》"）。
3. 涉及个人隐私或权限的操作，提示用户携带有效证件。
4. 如果用户表达自杀、自残等危险想法，立即回复："请立即联系心理咨询中心（电话：0371-61912654）或辅导员，也可以拨打心理援助热线12320-5。"
5. 不能查询个人成绩、他人信息等隐私内容，礼貌拒绝并说明原因。
6. 回答末尾必须标注信息来源，格式为"[来源:文件名]"，如"[来源:办事指南.md]"。
"""

# ==================== 推荐问题 ====================
# 各身份专属的快捷问题列表，按分类展示，方便用户快速提问
RECOMMENDED_QUESTIONS = {
    "新生": {
        "🏠 生活住宿": [
            "宿舍是几人间？有空调吗？",
            "宿舍费用多少？怎么缴费？",
            "宿舍可以自选床位吗？"
        ],

        "📋 报到流程": [
            "报到那天先去哪？需要带什么材料？",
            "家长可以进学校吗？",
            "报到流程大概需要多久？"
        ],
        "💪 军训安排": [
            "军训几天？身体不好能请假吗？",
            "军训服装需要自己准备吗？",
        ],
        "🚗 交通出行": [
            "从郑州东站怎么去龙子湖校区？",
            "从新郑机场怎么去学校？",
            "学校附近有地铁站吗？"
        ]
    },
    "在校生": {
        "🆔 校园卡": [
            "校园卡丢了在哪里补办？需要带什么材料？",
            "校园卡充值方式有哪些？",
            "校园卡挂失后怎么解挂？"
        ],
        "📝 证明材料": [
            "怎么开在读证明？教务处在哪？",
            "成绩单在哪里打印？",
            "学籍证明需要什么材料？"
        ],
        "📚 图书馆": [
            "图书馆现在几点关门？周末开吗？",
            "图书最多能借多久？"
        ],
        "📦 快递后勤": [
            "快递点都在哪里？营业时间是多少？",
            "宿舍维修怎么报修？",
            "食堂有哪些好吃的？"
        ],
        "📖 学习相关": [
            "选课系统怎么用？什么时候选课？",
            "转专业的条件是什么？",
            "怎么申请缓考？"
        ]
    },
    "教师": {
        "🎓 教学教务": [
            "怎么预约多媒体教室？流程是什么？",
            "课表怎么查询和调整？",
            "调停课流程是什么？"
        ],
        "🔬 科研项目": [
            "科研项目申报时间是什么时候？",
            "项目经费怎么报销？",
        ],
        "🛠️ 行政服务": [
            "办公室设备坏了怎么报修？",
            "会议室怎么预约？",
            "办公用品怎么申请？"
        ],
        "💰 财务报销": [
            "差旅怎么报销？需要什么材料？",
            "报销流程是什么？",
            "发票有什么要求？"
        ],
        "📊 学生管理": [
            "学生请假怎么审批？",
            "缓考申请怎么处理？",
            "学生成绩怎么录入？"
        ]
    }
}


def load_conversation_history():
    """
    从文件加载对话历史
    
    从data目录下的conversation_history.json文件加载对话历史，
    确保网页刷新后对话记录不会丢失。
    
    Returns:
        dict: 各身份的对话历史
    """
    history_file = os.path.join("data", "conversation_history.json")
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_conversation_history(history):
    """
    保存对话历史到文件
    
    将各身份的对话历史保存到data目录下的conversation_history.json文件，
    确保网页刷新后对话记录不会丢失。
    
    Args:
        history (dict): 各身份的对话历史
    """
    history_file = os.path.join("data", "conversation_history.json")
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except:
        pass


def read_txt_file(file_bytes):
    """
    读取TXT文件内容
    
    支持UTF-8、GBK、GB2312等编码格式，自动检测并处理编码问题。
    
    Args:
        file_bytes (bytes): 文件字节内容
    
    Returns:
        str: 文件的文本内容
    """
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']
    for encoding in encodings:
        try:
            return file_bytes.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return file_bytes.decode('utf-8', errors='replace')


def read_docx_file(file_bytes):
    """
    读取DOCX文件内容
    
    使用python-docx库解析Word文档，提取纯文本内容。
    
    Args:
        file_bytes (bytes): 文件字节内容
    
    Returns:
        str: 文档的纯文本内容
    """
    try:
        doc = Document(file_bytes)
        full_text = []
        for paragraph in doc.paragraphs:
            full_text.append(paragraph.text)
        return '\n'.join(full_text)
    except Exception as e:
        return f"读取DOCX文件失败：{str(e)}"


def load_school_data():
    """
    加载校园知识库资料
    
    从data目录下读取所有资料文件，拼接成完整的参考资料文本。
    支持的文件：校园概况.md、办事指南.md、生活服务.md、教学管理.md、电话黄页.md、交通出行.md
    
    Returns:
        str: 所有资料文件的内容，按文件分隔
    """
    data_dir = "data"
    files = ["校园概况.md", "办事指南.md", "生活服务.md", "教学管理.md", "电话黄页.md", "交通出行.md"]
    all_content = ""
    for filename in files:
        filepath = os.path.join(data_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                all_content += f"\n\n--- {filename} ---\n{content}"
    return all_content


def get_system_prompt(identity):
    """
    根据用户身份生成系统提示词
    
    为不同身份（新生/在校生/教师）生成个性化的系统提示词，
    包含角色定位、语气要求、回答要点、边界规则等。
    
    Args:
        identity (str): 用户身份，可选值："新生"、"在校生"、"教师"
    
    Returns:
        str: 完整的系统提示词
    """
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


def is_valid_input(text):
    """
    验证用户输入是否有效
    
    检查输入是否为空、纯空格或纯特殊字符，确保用户输入有意义的内容。
    
    Args:
        text (str): 用户输入的文本
    
    Returns:
        bool: 输入有效返回True，无效返回False
    """
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    has_alphanumeric = any(c.isalnum() for c in stripped)
    return has_alphanumeric


def export_conversation(messages, identity, export_format="md"):
    """
    导出对话记录
    
    将当前身份的对话记录导出为Markdown或纯文本格式，
    包含身份信息、导出时间、对话轮数等元数据。
    
    Args:
        messages (list): 对话消息列表
        identity (str): 当前身份
        export_format (str): 导出格式，可选"md"或"txt"
    
    Returns:
        tuple: (导出内容, 文件名, MIME类型)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if export_format == "md":
        filename = f"对话记录_{identity}_{timestamp}.md"
        content = f"# 小航AI助手 - 对话记录\n\n"
        content += f"**身份**: {identity}\n"
        content += f"**导出时间**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n"
        content += f"**对话轮数**: {len([m for m in messages if m['role'] != 'system']) // 2}\n\n"
        content += "---\n\n"
        
        for msg in messages:
            if msg["role"] == "system":
                continue
            role_name = "用户" if msg["role"] == "user" else "小航"
            content += f"## {role_name}\n\n"
            content += f"{msg['content']}\n\n"
        mime = "text/markdown"
    else:
        filename = f"对话记录_{identity}_{timestamp}.txt"
        content = f"小航AI助手 - 对话记录\n"
        content += "=" * 50 + "\n"
        content += f"身份: {identity}\n"
        content += f"导出时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}\n"
        content += f"对话轮数: {len([m for m in messages if m['role'] != 'system']) // 2}\n"
        content += "=" * 50 + "\n\n"
        
        for msg in messages:
            if msg["role"] == "system":
                continue
            role_name = "用户" if msg["role"] == "user" else "小航"
            content += f"{role_name}:\n"
            content += f"{msg['content']}\n\n"
            content += "-" * 50 + "\n\n"
        mime = "text/plain"
    
    return content, filename, mime


def call_api(messages, stream=False):
    """
    调用AI API
    
    向硅基流动平台发送请求，获取AI的回答。
    包含完善的错误处理，支持快速网络错误提示。
    
    Args:
        messages (list): 对话消息列表，包含system、user、assistant消息
        stream (bool): 是否使用流式输出，默认False（非流式）
    
    Returns:
        tuple: (AI回答内容, 耗时秒数)
    """
    import time
    start_time = time.time()
    
    # 检查API密钥是否配置
    api_key = API_KEY
    if api_key is None or api_key == "你的API Key":
        return "错误：请在代码中配置 API_KEY", 0
    
    # 构建请求头
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 构建请求体
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": stream,
        "temperature": 0.7,
        "max_tokens": 2048
    }
    
    try:
        # 发送POST请求，5秒超时
        response = requests.post(API_URL, headers=headers, json=payload, stream=stream, timeout=60)
        response.raise_for_status()
        
        # 解析JSON响应
        result = response.json()
        if result.get('choices') and result['choices'][0].get('message', {}).get('content'):
            return result['choices'][0]['message']['content'], time.time() - start_time
        else:
            return "⚠️ 响应格式异常，无法获取回答内容。", time.time() - start_time
    
    except requests.exceptions.ConnectionError:
        # 网络连接失败（断网）
        return "⚠️ 网络连接失败，请检查网络设置。\n\n💡 建议：\n1. 检查网络连接是否正常\n2. 尝试重启路由器\n3. 尝试切换网络\n4. 确认防火墙未阻止应用访问网络", time.time() - start_time
    
    except requests.exceptions.Timeout:
        # 请求超时
        return "⚠️ 请求超时，请稍后重试或检查网络连接。\n\n💡 建议：\n1. 检查网络连接是否正常\n2. 尝试切换WiFi或移动数据\n3. 稍后再次尝试", time.time() - start_time
    
    except requests.exceptions.HTTPError as e:
        # HTTP错误（4xx/5xx）
        error_code = response.status_code if 'response' in dir() else '未知'
        error_messages = {
            401: "⚠️ 认证失败，请检查API Key是否正确。",
            403: "⚠️ 访问被拒绝，可能是API Key无效或模型已禁用。",
            404: "⚠️ 请求的资源不存在。",
            429: "⚠️ 请求过于频繁，请稍后再试。\n\n💡 建议：减少提问频率，稍后再次尝试。",
            500: "⚠️ 服务器内部错误，请稍后重试。",
            502: "⚠️ 网关错误，请稍后重试。",
            503: "⚠️ 服务暂时不可用，请稍后重试。",
            504: "⚠️ 网关超时，请稍后重试。"
        }
        if error_code in error_messages:
            return error_messages[error_code], time.time() - start_time
        return f"⚠️ HTTP错误 {error_code}: {str(e)}", time.time() - start_time
    
    except requests.exceptions.RequestException as e:
        # 其他请求异常
        return f"⚠️ 请求失败：{str(e)}\n\n💡 建议：\n1. 检查网络连接\n2. 确认API Key有效\n3. 稍后再次尝试", time.time() - start_time
    
    except Exception as e:
        # 未知异常
        return f"⚠️ 解析响应失败：{str(e)}", time.time() - start_time


def main():
    """
    主函数：Streamlit应用入口
    
    负责初始化应用、渲染界面、处理用户交互、管理对话状态。
    """
    # 配置页面设置
    st.set_page_config(page_title="小航AI助手", page_icon="✈️", layout="wide")
    
    # 自定义CSS样式：聊天消息左对齐
    st.markdown("""
    <style>
    .st-chat-message {
        text-align: left !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 页面标题
    st.title("✈️ 小航AI助手 - 郑州航空工业管理学院")
    
    # 初始化会话状态
    if "identity" not in st.session_state:
        st.session_state.identity = None  # 当前身份
    if "identity_messages" not in st.session_state:
        # 从文件加载对话历史，确保刷新后不丢失
        saved_history = load_conversation_history()
        st.session_state.identity_messages = saved_history if saved_history else {}  # 各身份的对话历史
    if "loading" not in st.session_state:
        st.session_state.loading = False  # 是否正在加载
    
    # ==================== 侧边栏 ====================
    with st.sidebar:
        st.header("身份选择")
        identity_options = ["大一新生", "在校老生", "高校教师"]
        selected_identity = st.selectbox("请选择你的身份：", identity_options, index=None, placeholder="选择身份")
        
        # 处理身份选择
        if selected_identity:
            # 映射显示名称到内部标识
            if selected_identity == "大一新生":
                new_identity = "新生"
            elif selected_identity == "在校老生":
                new_identity = "在校生"
            elif selected_identity == "高校教师":
                new_identity = "教师"
            
            st.session_state.identity = new_identity
            
            # 如果是新身份，初始化对话历史（包含系统提示词）
            if new_identity not in st.session_state.identity_messages:
                system_prompt = get_system_prompt(new_identity)
                st.session_state.identity_messages[new_identity] = [{"role": "system", "content": system_prompt}]
                save_conversation_history(st.session_state.identity_messages)
        
        # 如果已选择身份，显示操作按钮
        if st.session_state.identity:
            st.success(f"已切换至【{st.session_state.identity}】模式")
            
            # 清空历史按钮
            if st.button("清空当前身份对话历史", key="clear_history", type="secondary"):
                system_prompt = get_system_prompt(st.session_state.identity)
                st.session_state.identity_messages[st.session_state.identity] = [{"role": "system", "content": system_prompt}]
                save_conversation_history(st.session_state.identity_messages)
                st.success("对话历史已清空！")
            
            # 导出格式选择
            export_format = st.radio("导出格式", ["Markdown (.md)", "纯文本 (.txt)"], key="export_format")
            format_type = "md" if export_format == "Markdown (.md)" else "txt"
            
            # 导出按钮
            if st.button("导出对话记录", key="export_button"):
                current_messages_export = st.session_state.identity_messages.get(st.session_state.identity, [])
                # 检查是否有对话内容（排除系统消息）
                if len([m for m in current_messages_export if m['role'] != 'system']) == 0:
                    st.error("导出内容不存在")
                else:
                    export_content, export_filename, export_mime = export_conversation(current_messages_export, st.session_state.identity, format_type)
                    st.download_button(
                        label="点击下载",
                        data=export_content,
                        file_name=export_filename,
                        mime=export_mime,
                        key="download_button",
                        use_container_width=True
                    )
            
            # 文件导入功能
            st.divider()
            st.header("导入文件")
            
            with st.form("upload_form", clear_on_submit=True):
                uploaded_file = st.file_uploader(
                    "上传TXT或DOCX文件",
                    type=["txt", "docx"],
                    key="file_uploader"
                )
                submit_button = st.form_submit_button("导入文件")
                
                if submit_button and uploaded_file is not None:
                    file_name = uploaded_file.name
                    file_ext = file_name.split('.')[-1].lower()
                    
                    # 读取文件内容
                    file_bytes = uploaded_file.read()
                    
                    if file_ext == 'txt':
                        file_content = read_txt_file(file_bytes)
                    elif file_ext == 'docx':
                        file_content = read_docx_file(file_bytes)
                    else:
                        st.error("不支持的文件格式！")
                        file_content = ""
                    
                    if file_content and st.session_state.identity:
                        # 将文件内容作为用户输入发送
                        current_messages_import = st.session_state.identity_messages.get(st.session_state.identity, [])
                        current_messages_import.append({"role": "user", "content": f"根据以下文件内容回答问题：\n\n{file_content}"})
                        st.session_state.identity_messages[st.session_state.identity] = current_messages_import
                        save_conversation_history(st.session_state.identity_messages)
                        st.session_state.loading = True
                        st.success(f"文件 '{file_name}' 已导入！")
                        st.rerun()
                    elif not st.session_state.identity:
                        st.warning("请先选择身份再导入文件！")
                    elif not file_content:
                        st.error("文件内容为空或读取失败！")
    
    # ==================== 主内容区 ====================
    # 如果未选择身份，显示提示信息
    if not st.session_state.identity:
        st.info("请在左侧边栏选择你的身份开始对话")
        return
    
    # 获取当前身份的对话历史
    current_messages = st.session_state.identity_messages.get(st.session_state.identity, [])
    
    # 显示对话消息
    for msg in current_messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                # 如果是AI回答，显示字数和耗时
                if msg["role"] == "assistant" and "word_count" in msg:
                    st.caption(f"字数: {msg['word_count']} | 耗时: {msg['elapsed_time']:.2f}秒")
    
    # ==================== 加载状态处理 ====================
    # 如果正在加载，调用API获取回答
    if st.session_state.loading:
        with st.chat_message("assistant"):
            with st.spinner("小航正在思考..."):
                response, elapsed_time = call_api(current_messages)
            word_count = len(response)
            st.markdown(response)
            st.caption(f"字数: {word_count} | 耗时: {elapsed_time:.2f}秒")
        # 将AI回答添加到对话历史
        current_messages.append({"role": "assistant", "content": response, "word_count": word_count, "elapsed_time": elapsed_time})
        st.session_state.identity_messages[st.session_state.identity] = current_messages
        save_conversation_history(st.session_state.identity_messages)
        st.session_state.loading = False
        st.rerun()
    
    # ==================== 快捷问题 ====================
    questions = RECOMMENDED_QUESTIONS.get(st.session_state.identity, {})
    if questions:
        st.subheader("快捷问题")
        for category, q_list in questions.items():
            with st.expander(category, expanded=True):
                cols = st.columns(2)
                for i, q in enumerate(q_list):
                    with cols[i % 2]:
                        if st.button(q, key=f"quick_{st.session_state.identity}_{category}_{i}"):
                            current_messages.append({"role": "user", "content": q})
                            st.session_state.loading = True
                            st.session_state.identity_messages[st.session_state.identity] = current_messages
                            save_conversation_history(st.session_state.identity_messages)
                            st.rerun()
    
    # ==================== 用户输入 ====================
    user_input = st.chat_input("请输入你的问题...")
    
    if user_input:
        # 验证输入有效性
        if not is_valid_input(user_input):
            st.error("请输入有效的问题，不能只输入空格或特殊字符！")
        else:
            # 添加用户问题到对话历史
            current_messages.append({"role": "user", "content": user_input})
            # 设置加载状态，触发API调用
            st.session_state.loading = True
            st.session_state.identity_messages[st.session_state.identity] = current_messages
            save_conversation_history(st.session_state.identity_messages)
            st.rerun()


if __name__ == "__main__":
    # 启动应用
    main()
