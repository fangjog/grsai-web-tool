import streamlit as st
import requests
import time
from PIL import Image
import io
import base64
from datetime import datetime
import json
import os
from streamlit_drawable_canvas import st_canvas

# ==========================================
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI 创作工作台 V4", page_icon="🎨", layout="wide")

# 注入画布特定的 CSS (仅保留视觉效果，不破坏原有布局)
st.markdown("""
<style>
    .design-canvas {
        background-color: #f0f2f5; border-radius: 10px; min-height: 500px;
        padding: 30px; display: flex; flex-wrap: wrap; gap: 30px; align-items: center; justify-content: center;
        border: 2px dashed #ccc;
    }
    .layer-wrapper { position: relative; display: inline-block; padding: 10px; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    
    /* 选中时的蓝色边框与控制点 (还原图1/图2) */
    .is-selected { border: 2px solid #00c2ff; }
    .handle { position: absolute; width: 10px; height: 10px; background: white; border: 2px solid #00c2ff; border-radius: 50%; }
    .top-left { top: -6px; left: -6px; } .top-right { top: -6px; right: -6px; }
    .bottom-left { bottom: -6px; left: -6px; } .bottom-right { bottom: -6px; right: -6px; }
    .rotate-handle { bottom: -25px; left: 50%; transform: translateX(-50%); position: absolute; font-size: 14px; }

    /* 模拟悬浮工具栏 */
    .mock-toolbar {
        position: absolute; top: -50px; left: 50%; transform: translateX(-50%);
        background: white; border-radius: 8px; padding: 6px 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        display: flex; gap: 15px; font-size: 13px; color: #333; white-space: nowrap; z-index: 10;
        border: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 认证与持久化数据系统
# ==========================================
KEY_MAP = {"vip888": "API_VIP", "test1234": "API_TEST", "123": "API_123", "free_trial": "GRSAI_API_KEY"}
KEY_POINTS = {"vip888": 10000, "test1234": 5000, "123": 5000, "free_trial": 600}

st.sidebar.markdown("### 🪪 身份验证")
user_key_input = st.sidebar.text_input("🔑 请输入激活码", type="password")
user_key = user_key_input.strip() if user_key_input else ""

if not user_key or user_key not in KEY_MAP:
    st.sidebar.warning("👈 请输入激活码解锁。")
    st.stop()

secret_name = KEY_MAP[user_key]
GRSAI_API_KEY = st.secrets.get(secret_name, "")
if not GRSAI_API_KEY:
    st.error(f"⚠️ 找不到配置：请在 Secrets 中添加 `{secret_name}`。")
    st.stop()

# 数据文件定义
TASKS_FILE = "tasks_history.json"
PROJECTS_FILE = "projects_v4.json"

def load_json(path, default=[]):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
    except: pass

# 初始化 Session State
if 'tasks' not in st.session_state:
    st.session_state.tasks = load_json(TASKS_FILE)
if 'projects' not in st.session_state:
    st.session_state.projects = load_json(PROJECTS_FILE)
if 'curr_proj_idx' not in st.session_state:
    st.session_state.curr_proj_idx = 0
if 'selected_layer_idx' not in st.session_state:
    st.session_state.selected_layer_idx = -1

def clean_and_get_tasks():
    curr_time = time.time()
    valid = [t for t in st.session_state.tasks if (curr_time - t['timestamp']) < 3600]
    valid = valid[-10:]
    st.session_state.tasks = valid
    save_json(TASKS_FILE, valid)
    return valid

def add_task(item):
    st.session_state.tasks.append(item)
    clean_and_get_tasks()

def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

# ==========================================
# 2. 动画进度弹窗
# ==========================================
@st.experimental_dialog("🔍 实时生图进度", width="large")
def show_progress_dialog(task_id, prompt_text):
    st.markdown(f"**任务:** `{prompt_text}`")
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

# ==========================================
# 3. 侧边栏导航与状态
# ==========================================
current_points = KEY_POINTS.get(user_key, 600)
max_images = int(current_points / 600)
st.sidebar.markdown(f'剩余可制图数量: <span style="color:#FF4B4B; font-weight:bold; font-size:18px;">{max_images}</span> 张', unsafe_allow_html=True)
st.sidebar.divider()

# 【核心修复】：左侧第三项导航
menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图", "🎨 专业画布工作台"])

# ==========================================
# 4. 页面 1 & 2: 经典的文生图/图生图
# ==========================================
if menu in ["✍️ 文生图", "🖼️ 图生图"]:
    st.title("🚀 image-2 V2")
    col_main, col_history = st.columns([7, 3])
    
    with col_main:
        if menu == "✍️ 文生图":
            st.markdown("#### 📝 输入描述直接生成画面")
            prompt_txt = st.text_area("画面详细描述", height=120)
            c1, c2 = st.columns(2)
            with c1: aspect_ratio = st.selectbox("📏 画幅比例", ["16:9", "9:16", "1:1", "4:3", "3:4"])
            with c2: quality = st.selectbox("💎 图片质量", ["auto", "high", "medium", "low"])
            btn_submit = st.button("✨ 提交任务 (文生图)", type="primary")
            
        else: # 图生图
            st.markdown("#### 🖌️ 上传参考图或在下方画布涂鸦")
            uploaded_files = st.file_uploader("支持多张上传", type=["png", "jpg"], accept_multiple_files=True)
            canvas_bg = None
            if uploaded_files:
                st.markdown("📎 **上传预览：**")
                html_snippets = []
                for idx, file in enumerate(uploaded_files):
                    try:
                        if idx == 0:
                            canvas_bg = Image.open(io.BytesIO(file.getvalue()))
                            canvas_bg.thumbnail((1024, 1024))
                        b64_str = base64.b64encode(file.getvalue()).decode("utf-8")
                        html_img = f'<img src="data:image/jpeg;base64,{b64_str}" style="height:60px; border-radius:4px; margin-right:10px;">'
                        html_snippets.append(html_img)
                    except: pass
                st.markdown("".join(html_snippets), unsafe_allow_html=True)

            canvas_result = st_canvas(stroke_width=3, stroke_color="#000000", background_image=canvas_bg, height=400, drawing_mode="freedraw", key="canvas")
            prompt_txt = st.text_area("修改指令或画面描述", height=80)
            btn_submit = st.button("✨ 提交任务 (图生图)", type="primary")

        # 统一的 API 提交逻辑
        if btn_submit:
            if not prompt_txt:
                st.error("❌ 请输入提示词！")
            else:
                payload = {"model": "gpt-image-2", "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
                if menu == "🖼️ 图生图":
                    urls_list = []
                    if canvas_result.image_data is not None:
                        canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                        urls_list.append(pil_to_data_uri(canvas_pil))
                    if uploaded_files:
                        for file in uploaded_files:
                            try: urls_list.append(pil_to_data_uri(Image.open(io.BytesIO(file.getvalue()))))
                            except: pass
                    payload["urls"] = urls_list 
                else:
                    payload["aspectRatio"] = aspect_ratio
                    payload["quality"] = quality

                headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
                try:
                    sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                    if sub_res.get("code") == 0:
                        add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": datetime.now().strftime("%H:%M:%S"), "prompt": prompt_txt, "status": "running", "url": "", "reason": ""})
                        st.success("🎉 任务已提交！")
                        time.sleep(1)
                        st.rerun()
                    else: st.error(f"接口报错：{sub_res.get('msg', '未知')}")
                except Exception as e: st.error(f"网络异常：{e}")

    # 右侧任务队列大厅
    with col_history:
        st.markdown("### 🗂️ 已提交图片任务")
        tasks_list = clean_and_get_tasks()
        if not tasks_list:
            st.info("💡 暂无提交记录。")
        else:
            with st.container(height=800):
                for item in reversed(tasks_list):
                    with st.container():
                        display_title = item.get('prompt', '')[:20] + "..." if len(item.get('prompt', '')) > 20 else item.get('prompt', '')
                        st.markdown(f"**任务: {display_title}**")
                        with st.expander("📝 完整提示词"):
                            st.code(item.get('prompt', ''), language=None)
                        if item.get('status') == 'running':
                            if st.button("🔍 追踪动画", key=f"btn_{item['task_id']}", use_container_width=True):
                                show_progress_dialog(item['task_id'], item['prompt'])
                        elif item.get('status') == 'succeeded':
                            st.markdown(f'<img src="{item["url"]}" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
                        elif item.get('status') == 'failed':
                            st.error(f"❌ 失败: {item.get('reason', '未知')}")
                        st.divider()

# ==========================================
# 5. 页面 3: 🎨 专业画布工作台 (不破坏布局的稳妥版)
# ==========================================
elif menu == "🎨 专业画布工作台":
    st.title("🎨 专业画布工作台")
    
    # 确保项目数据存在
    if not st.session_state.projects:
        st.session_state.projects.append({"title": "默认画布", "layers": []})
        save_json(PROJECTS_FILE, st.session_state.projects)
        
    curr_proj = st.session_state.projects[st.session_state.curr_proj_idx]
    if "layers" not in curr_proj: curr_proj["layers"] = []

    # 顶部工具栏
    st.markdown("##### 🛠️ 插入元素")
    t1, t2, t3, t4 = st.columns([2, 2, 2, 4])
    with t1:
        up_file = st.file_uploader(" ", type=["png","jpg"], label_visibility="collapsed")
        if up_file:
            b64 = f"data:image/jpeg;base64,{base64.b64encode(up_file.getvalue()).decode()}"
            curr_proj["layers"].append({"type": "image", "content": b64})
            save_json(PROJECTS_FILE, st.session_state.projects); st.rerun()
    with t2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("T 添加文本框", use_container_width=True):
            curr_proj["layers"].append({"type": "text", "content": "在这个文本框输入"})
            save_json(PROJECTS_FILE, st.session_state.projects); st.rerun()
    with t3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ 清空画布", use_container_width=True):
            curr_proj["layers"] = []
            st.session_state.selected_layer_idx = -1
            save_json(PROJECTS_FILE, st.session_state.projects); st.rerun()
            
    st.divider()

    # 画布区域 (纯 HTML 渲染视觉，分离按钮防崩溃)
    st.markdown('<div class="design-canvas">', unsafe_allow_html=True)
    if not curr_proj["layers"]:
        st.markdown("<p style='color:#999;'>画布空空如也，请从上方工具栏添加素材</p>", unsafe_allow_html=True)
    else:
        for idx, layer in enumerate(curr_proj["layers"]):
            is_selected = (idx == st.session_state.selected_layer_idx)
            sel_class = "is-selected" if is_selected else ""
            
            # 开始渲染元素
            st.markdown(f'<div class="layer-wrapper {sel_class}">', unsafe_allow_html=True)
            
            # 渲染选中工具栏 (参考图1/2)
            if is_selected:
                if layer["type"] == "text":
                    st.markdown('<div class="mock-toolbar">💬 添加到对话 | 96 ⌵ | <b>B</b> | 📥</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="mock-toolbar">💬 添加到对话 | 🪄 扩图 | 💎 超清 | ✂️ 抠图</div>', unsafe_allow_html=True)
                    
            # 渲染内容
            if layer["type"] == "text":
                st.markdown(f"<h3 style='margin:0; padding:10px;'>{layer['content']}</h3>", unsafe_allow_html=True)
            else:
                st.markdown(f'<img src="{layer["content"]}" style="max-width:300px; border-radius:4px;">', unsafe_allow_html=True)
                
            # 渲染四周的手柄
            if is_selected:
                st.markdown('''
                    <div class="handle top-left"></div><div class="handle top-right"></div>
                    <div class="handle bottom-left"></div><div class="handle bottom-right"></div>
                    <div class="rotate-handle">🔄</div>
                ''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 【安全稳定的原生按钮控制区】
    st.markdown("<br>##### 🎛️ 画布元素控制台", unsafe_allow_html=True)
    if curr_proj["layers"]:
        # 将操作按钮放在 HTML 画布外部，确保 Python 回调100%触发！
        btn_cols = st.columns(len(curr_proj["layers"]))
        for idx, layer in enumerate(curr_proj["layers"]):
            with btn_cols[idx]:
                name = f"图层 {idx+1} (文本)" if layer["type"]=="text" else f"图层 {idx+1} (图片)"
                if st.button(f"👆 选中 {name}", key=f"sel_{idx}"):
                    st.session_state.selected_layer_idx = idx
                    st.rerun()
                    
        # 编辑选中的元素
        if st.session_state.selected_layer_idx >= 0 and st.session_state.selected_layer_idx < len(curr_proj["layers"]):
            st.markdown("---")
            target = curr_proj["layers"][st.session_state.selected_layer_idx]
            ec1, ec2 = st.columns([8, 2])
            with ec1:
                if target["type"] == "text":
                    new_val = st.text_input("📝 编辑选中文字", value=target["content"])
                    if new_val != target["content"]:
                        target["content"] = new_val
                        save_json(PROJECTS_FILE, st.session_state.projects)
                        st.rerun()
            with ec2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("❌ 删除该图层", type="primary", use_container_width=True):
                    curr_proj["layers"].pop(st.session_state.selected_layer_idx)
                    st.session_state.selected_layer_idx = -1
                    save_json(PROJECTS_FILE, st.session_state.projects)
                    st.rerun()
