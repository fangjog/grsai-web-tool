import streamlit as st
import requests
import time
from PIL import Image
import io
import base64
from datetime import datetime
import json
import os

# ==========================================
# 0. 网页基础配置 (必须是第一句)
# ==========================================
st.set_page_config(page_title="AI 创作工作台 V3", page_icon="🎨", layout="wide")

# ==========================================
# 1. 密钥与积分管理模块
# ==========================================
KEY_MAP = {
    "vip888": "API_VIP",
    "test1234": "API_TEST",
    "123": "API_123",
    "free_trial": "GRSAI_API_KEY"
}
KEY_POINTS = {"vip888": 10000, "test1234": 5000, "123": 5000, "free_trial": 600}

# 侧边栏菜单设计
st.sidebar.markdown("### 🪪 身份验证")
user_key_input = st.sidebar.text_input("🔑 请输入激活码", type="password")
user_key = user_key_input.strip() if user_key_input else ""

if not user_key or user_key not in KEY_MAP:
    st.warning("👈 请在左侧输入有效的激活码解锁工作台。")
    st.stop()

secret_name = KEY_MAP[user_key]
if secret_name in st.secrets:
    GRSAI_API_KEY = st.secrets[secret_name]
else:
    st.error(f"⚠️ 找不到配置：请在 Secrets 中添加 `{secret_name}`。")
    st.stop()

current_points = KEY_POINTS.get(user_key, 600)
cost_input = 600
max_images = int(current_points / cost_input)

st.sidebar.markdown("---")
st.sidebar.markdown(f'**可用算力**: <span style="color:#FF4B4B; font-weight:bold; font-size:16px;">≈ {max_images}</span> 张', unsafe_allow_html=True)
st.sidebar.markdown("---")

# 主导航栏
menu_selection = st.sidebar.radio("导航菜单", ["🏠 灵感创作台", "🎨 我的画布项目"])

# ==========================================
# 2. 持久化数据系统 (任务 & 项目)
# ==========================================
TASKS_FILE = "tasks_history.json"
PROJECTS_FILE = "projects_data.json"

def load_json(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_json(file_path, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
    except: pass

# 初始化 Session State
if 'tasks' not in st.session_state:
    st.session_state.tasks = load_json(TASKS_FILE)
if 'projects' not in st.session_state:
    st.session_state.projects = load_json(PROJECTS_FILE)
if 'current_project_id' not in st.session_state:
    st.session_state.current_project_id = None
if 'img2img_cache' not in st.session_state:
    st.session_state.img2img_cache = None # 用于跨页面传递重绘图片

def add_task(item):
    st.session_state.tasks.append(item)
    st.session_state.tasks = st.session_state.tasks[-15:] # 保留15条
    save_json(TASKS_FILE, st.session_state.tasks)

def create_project():
    new_id = int(time.time())
    new_proj = {
        "id": new_id,
        "title": f"未命名项目 {datetime.now().strftime('%m-%d %H:%M')}",
        "elements": [] # 存放文本、图片等元素
    }
    st.session_state.projects.insert(0, new_proj)
    st.session_state.projects = st.session_state.projects[:10] # 最多保留10个项目
    save_json(PROJECTS_FILE, st.session_state.projects)
    st.session_state.current_project_id = new_id

def get_current_project():
    for p in st.session_state.projects:
        if p["id"] == st.session_state.current_project_id: return p
    return None

def save_projects():
    save_json(PROJECTS_FILE, st.session_state.projects)

# 辅助函数：PIL转Base64
def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    base64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{base64_str}"

# ==========================================
# 3. 弹窗对话框 (进度动画 & 聊天记录)
# ==========================================
@st.experimental_dialog("🔍 实时生图进度", width="large")
def show_progress_dialog(task_id, prompt_text):
    st.markdown(f"**任务描述:** `{prompt_text}`")
    progress_bar = st.progress(0)
    status_text = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    
    for i in range(40):
        p = min(5 + i*2, 95)
        track = "━" * int((p/100)*25) + "🏃‍♂️" + "  " * (25 - int((p/100)*25)) + "🏁"
        status_text.markdown(f"**云端绘制中...**\n\n{track} **{p}%**")
        progress_bar.progress(p)
        try:
            q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
            if q_res.get("code") == 0:
                status = q_res["data"]["status"]
                if status == "succeeded":
                    progress_bar.progress(100)
                    img_url = q_res["data"]["results"][0]["url"]
                    status_text.success("✅ **生成成功！请关闭弹窗查看。**")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'succeeded'
                            t['url'] = img_url
                    save_json(TASKS_FILE, st.session_state.tasks)
                    time.sleep(1)
                    st.rerun()
                elif status == "failed":
                    reason = q_res["data"].get("failure_reason", "未知错误")
                    status_text.error(f"❌ **失败:** {reason}")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'failed'
                            t['reason'] = reason
                    save_json(TASKS_FILE, st.session_state.tasks)
                    break
        except: pass
        time.sleep(3)

@st.experimental_dialog("💬 AI 对话与生成记录", width="large")
def show_chat_history():
    st.markdown("这里记录了你最近的提示词和 AI 生成历史：")
    if not st.session_state.tasks:
        st.info("暂无记录")
    for t in reversed(st.session_state.tasks[-5:]):
        st.markdown(f"**[{t['time_str']}] You:** {t['prompt']}")
        if t.get('url'):
            st.markdown(f"**AI:** 生成了图片 [点击查看]({t['url']})")
        st.divider()

# ==========================================
# 4. 页面1：🏠 灵感创作台 (文生图/图生图)
# ==========================================
if menu_selection == "🏠 灵感创作台":
    st.title("✨ 灵感创作台")
    col_main, col_history = st.columns([7, 3])

    with col_main:
        tab1, tab2 = st.tabs(["✍️ 文生图", "🖼️ 图生图 (重绘)"])
        
        # --- 文生图 ---
        with tab1:
            col_p1, col_p2 = st.columns([8, 2])
            with col_p1:
                prompt_txt = st.text_area("在此输入画面描述指令...", height=120, key="txt2img_prompt")
            with col_p2:
                # 【参考图3】：输入框旁边的查看对话记录按钮
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💬 对话记录", use_container_width=True):
                    show_chat_history()
            
            col1_1, col1_2 = st.columns(2)
            with col1_1: aspect_ratio_txt = st.selectbox("📏 画幅比例", ["16:9", "9:16", "1:1", "4:3", "3:4"], key="txt_ratio")
            with col1_2: quality_txt = st.selectbox("💎 图片质量", ["auto", "high", "medium"], key="txt_quality")
            btn_txt2img = st.button("🚀 立即生成 (文生图)", key="btn_submit_txt", type="primary")

        # --- 图生图 (去除了涂鸦板，极简上传) ---
        with tab2:
            st.markdown("#### 🖼️ 上传参考图重绘")
            
            # 接收从“画布项目”传过来的待编辑图片
            cache_img = st.session_state.img2img_cache
            if cache_img:
                st.info("💡 正在使用从【画布项目】传来的图片作为参考底图。如需更改，请点击下方清除。")
                st.markdown(f'<img src="{cache_img}" style="height:150px; border-radius:8px;">', unsafe_allow_html=True)
                if st.button("🗑️ 清除联动图片"):
                    st.session_state.img2img_cache = None
                    st.rerun()
                uploaded_files = []
            else:
                uploaded_files = st.file_uploader("本地上传参考图 (支持多张)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
            
            if uploaded_files:
                cols = st.columns(min(len(uploaded_files), 5))
                for idx, file in enumerate(uploaded_files[:5]):
                    with cols[idx]:
                        st.image(file, caption=f"参考图 {idx+1}", use_column_width=True)
            
            prompt_img = st.text_area("修改指令或重绘描述", height=80, key="img2img_prompt")
            btn_img2img = st.button("🚀 立即生成 (图生图)", key="btn_submit_img", type="primary")

        # --- 提交逻辑 ---
        if btn_txt2img or btn_img2img:
            mode = "txt2img" if btn_txt2img else "img2img"
            current_prompt = prompt_txt if mode == "txt2img" else prompt_img
            if not current_prompt:
                st.error("❌ 请输入提示词！")
            else:
                payload = {"model": "gpt-image-2", "prompt": current_prompt, "webHook": "-1", "shutProgress": True}
                if mode == "img2img":
                    urls_list = []
                    # 如果有联动传递过来的图，优先使用
                    if cache_img: urls_list.append(cache_img)
                    elif uploaded_files:
                        for file in uploaded_files:
                            try: urls_list.append(pil_to_data_uri(Image.open(io.BytesIO(file.getvalue()))))
                            except: pass
                    if not urls_list:
                        st.warning("请上传至少一张参考图！")
                        st.stop()
                    payload["urls"] = urls_list 
                else:
                    payload["aspectRatio"] = aspect_ratio_txt
                    payload["quality"] = quality_txt

                headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
                try:
                    sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                    if sub_res.get("code") == 0:
                        add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": datetime.now().strftime("%H:%M:%S"), "prompt": current_prompt, "status": "running", "url": "", "reason": ""})
                        st.success("🎉 任务已提交！")
                        st.session_state.img2img_cache = None # 清理缓存
                        time.sleep(1)
                        st.rerun()
                    else: st.error(f"接口报错：{sub_res.get('msg', '未知')}")
                except Exception as e: st.error(f"网络异常：{e}")

    # --- 右侧任务队列 ---
    with col_history:
        st.markdown("### 🗂️ 队列记录")
        if not st.session_state.tasks:
            st.info("💡 暂无记录。")
        else:
            with st.container(height=800):
                for item in reversed(st.session_state.tasks):
                    with st.container():
                        raw_prompt = item.get('prompt', '无描述')
                        st.markdown(f"**任务: {raw_prompt[:15]}...**")
                        if item.get('status') == 'running':
                            if st.button("🔍 追踪进度", key=f"btn_{item['task_id']}", use_container_width=True):
                                show_progress_dialog(item['task_id'], item['prompt'])
                        elif item.get('status') == 'succeeded':
                            st.markdown(f'<img src="{item["url"]}" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
                        elif item.get('status') == 'failed':
                            st.error(f"❌ 失败: {item.get('reason', '未知')}")
                        st.divider()

# ==========================================
# 5. 页面2：🎨 我的画布项目 (项目管理 & 模拟画板)
# ==========================================
elif menu_selection == "🎨 我的画布项目":
    st.title("🎨 我的画布与项目")
    
    # 状态1：未选择项目，展示项目列表（参考图1）
    if not st.session_state.current_project_id:
        st.markdown("#### 📁 最近项目")
        
        # 新建项目按钮
        if st.button("➕ 新建画布项目", type="primary"):
            create_project()
            st.rerun()
            
        st.markdown("---")
        if not st.session_state.projects:
            st.info("还没有任何项目，点击上方新建一个吧！")
        else:
            cols = st.columns(4)
            for idx, proj in enumerate(st.session_state.projects):
                with cols[idx % 4]:
                    st.markdown(f'''
                    <div style="background:#f8f9fa; padding:20px; border-radius:10px; border:1px solid #ddd; text-align:center; height:120px; margin-bottom:15px;">
                        <h4 style="color:#333;">🖼️ {proj["title"][:10]}...</h4>
                    </div>
                    ''', unsafe_allow_html=True)
                    if st.button("进入项目", key=f"enter_{proj['id']}", use_container_width=True):
                        st.session_state.current_project_id = proj['id']
                        st.rerun()

    # 状态2：已进入特定项目，展示工具栏和画板（参考图5/6/7）
    else:
        current_proj = get_current_project()
        
        col_title, col_back = st.columns([8, 2])
        with col_title: st.subheader(f"🖌️ 当前项目: {current_proj['title']}")
        with col_back:
            if st.button("🔙 返回项目大厅"):
                st.session_state.current_project_id = None
                st.rerun()
                
        # --- 顶部工具栏 (参考图5 本地上传 / 图6 画板尺寸 / 图7 文本) ---
        st.markdown("---")
        t_col1, t_col2, t_col3 = st.columns(3)
        
        with t_col1:
            st.markdown("**📤 本地上传**")
            up_file = st.file_uploader("添加图片到画板", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
            if up_file:
                b64_str = pil_to_data_uri(Image.open(io.BytesIO(up_file.getvalue())))
                current_proj["elements"].append({"type": "image", "content": b64_str})
                save_projects()
                st.success("图片已加入画板！")
                
        with t_col2:
            st.markdown("**⌗ 添加布局/画板**")
            st.selectbox("预设尺寸 (仅标记)", ["自由比例", "16:9", "4:3", "1:1", "9:16"], label_visibility="collapsed")
            
        with t_col3:
            st.markdown("**T 添加文本标签**")
            txt_input = st.text_input("输入文本", placeholder="在此输入文本...", label_visibility="collapsed")
            if st.button("添加到画板"):
                if txt_input:
                    current_proj["elements"].append({"type": "text", "content": txt_input})
                    save_projects()
                    st.rerun()

        st.markdown("---")
        st.markdown("<p style='color:#666; font-size:14px;'>🖱️ 提示：按住鼠标滚轮或触控板双指滑动，可自由浏览下方画板内容。</p>", unsafe_allow_html=True)
        
        # --- 模拟无限拖拽画布区 (用 CSS overflow 实现参考图2效果) ---
        with st.container():
            st.markdown("""
            <style>
            .canvas-board {
                width: 100%;
                height: 600px;
                background-color: #f0f2f6;
                border: 2px dashed #ccc;
                border-radius: 10px;
                overflow: auto;
                padding: 20px;
                white-space: nowrap;
            }
            .canvas-item {
                display: inline-block;
                vertical-align: top;
                margin-right: 20px;
                background: white;
                padding: 10px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            </style>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="canvas-board">', unsafe_allow_html=True)
            
            if not current_proj["elements"]:
                st.markdown("<h3 style='text-align:center; color:#999; margin-top:200px;'>画板空空如也，请从上方工具栏添加图片或文字</h3>", unsafe_allow_html=True)
            
            # 渲染画板中的元素
            cols = st.columns(len(current_proj["elements"]) if current_proj["elements"] else 1)
            for idx, element in enumerate(current_proj["elements"]):
                with cols[idx]:
                    st.markdown('<div class="canvas-item">', unsafe_allow_html=True)
                    if element["type"] == "text":
                        st.markdown(f"### 📝 {element['content']}")
                    elif element["type"] == "image":
                        st.markdown(f'<img src="{element["content"]}" style="width:250px; border-radius:5px;">', unsafe_allow_html=True)
                        # 【参考图4功能】：点击图片送去重绘编辑
                        if st.button("🪄 去创作台重绘此图", key=f"edit_{idx}"):
                            st.session_state.img2img_cache = element["content"]
                            st.success("✅ 图片已锁定！请点击左侧菜单返回【🏠 灵感创作台】进行图生图操作。")
                    st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
