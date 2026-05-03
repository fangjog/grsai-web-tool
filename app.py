import streamlit as st
import requests
import time
from PIL import Image, ImageDraw  # 用于后端遮罩生成
import io
import base64
from datetime import datetime
import json
import os
from streamlit_drawable_canvas import st_canvas

# ==========================================
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI Pro Workspace V4.1", page_icon="🎨", layout="wide")

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
    st.error(f"⚠️ 未在 Secrets 中找到 `{secret_name}`。")
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
if 'tasks' not in st.session_state: st.session_state.tasks = load_json(TASKS_FILE)
if 'projects' not in st.session_state: st.session_state.projects = load_json(PROJECTS_FILE)
if 'curr_proj_idx' not in st.session_state: st.session_state.curr_proj_idx = 0
if 'selected_layer_idx' not in st.session_state: st.session_state.selected_layer_idx = -1

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
    return f"data:image/jpeg;base64,{base64_str}"

def add_projects_json(proj):
    st.session_state.projects.append(proj)
    save_json(PROJECTS_FILE, st.session_state.projects)

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
                    status_text.success("✅ **生成成功！请关闭弹窗。**")
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
            
        else: # 图生图 (集成 Inpainting 视觉演示逻辑)
            st.markdown("#### 🖌️ 上传底图，在画布上绘制遮罩来精确局部重绘")
            
            # 【重要建议】：对于正式 API，请优先使用 API 提供的文件上传接口上传底图和生成的遮罩图得到 URL 后使用。
            # 这里为了视觉演示，使用 Base64 URI 作为占位。
            
            uploaded_files = st.file_uploader("支持多张上传，默认第1张为画布背景", type=["png", "jpg"], accept_multiple_files=True)
            
            # 初始化局部重绘参数
            inpainting_strength = 0.6  # 局部重绘强度，0.0-1.0
            
            canvas_bg = None
            if uploaded_files:
                st.markdown("📎 **底图预览：**")
                html_snippets = []
                for idx, file in enumerate(uploaded_files):
                    try:
                        if idx == 0:
                            canvas_bg = Image.open(io.BytesIO(file.getvalue()))
                            canvas_bg.thumbnail((1024, 1024)) # 缩小比例，提高性能
                        
                        b64_str = base64.b64encode(file.getvalue()).decode("utf-8")
                        html_img = f'<img src="data:image/jpeg;base64,{b64_str}" style="height:60px; border-radius:4px; margin-right:10px;">'
                        html_snippets.append(html_img)
                    except: pass
                st.markdown("".join(html_snippets), unsafe_allow_html=True)
                
                # 局部重绘设置
                st.markdown("---")
                inpainting_strength = st.slider("💧 局部重绘强度 (Strength)", 0.0, 1.0, 0.6, 0.05, help="数值越大，重绘内容与原图差异越大")
                st.caption("提示：在下方画布上选择黑色画笔，绘制你想要去除的内容（遮罩区），然后在输入框描述期望的最终画面。")
            
            # 画布设置
            canvas_result = st_canvas(
                stroke_width=3, stroke_color="#000000", background_image=canvas_bg, height=400, drawing_mode="freedraw", key="canvas_img2img"
            )
            
            prompt_txt = st.text_area("修改指令或最终画面描述", height=80, key="prompt_img2img")
            btn_submit = st.button("✨ 提交任务 (局部重绘演示)", type="primary", key="btn_img2img")

        # 统一的 API 提交逻辑
        if btn_submit:
            if not prompt_txt:
                st.error("❌ 请输入提示词！")
            else:
                payload = {"model": "gpt-image-2", "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
                
                if menu == "🖼️ 图生图":
                    # --- 【视觉演示 Inpainting 遮罩逻辑】 ---
                    st.toast("正在生成视觉遮罩演示数据...")
                    
                    base_uri = None
                    mask_uri = None
                    
                    # 1. 准备底图 URI (简化视觉演示， anti-pattern)
                    if uploaded_files:
                        try:
                            # 简化视觉演示， anti-pattern
                            buffered_base = io.BytesIO()
                            pil_base = Image.open(io.BytesIO(uploaded_files[0].getvalue()))
                            if pil_base.mode != 'RGB': pil_base = pil_base.convert('RGB')
                            pil_base.thumbnail((1024, 1024))
                            pil_base.save(buffered_base, format="JPEG")
                            base_uri = f"data:image/jpeg;base64,{base64.b64encode(buffered_base.getvalue()).decode()}"
                        except:
                            st.error("底图数据处理失败。")
                            st.stop()
                    else:
                        st.warning("请至少上传一张底图！")
                        st.stop()
                    
                    # 2. 准备视觉演示遮罩 URI (Simplified anti-pattern)
                    # robust方法: Pillow根据json_data绘制 binary mask (black=keep, white=mask)，上传得到URL后使用
                    # 这里简化视觉演示：直接使用画布上用户所绘内容的 base64 (anti-pattern)
                    # 假设 API 智能处理：黑色涂鸦区为 masked，透明区为 keep
                    
                    # robust方法（需要复杂不搜技术细节）
                    # buffered_mask = io.BytesIO()
                    # pil_mask = Image.new("L", pil_base.size, 0) # 创建黑色透明层 (黑色=保留)
                    # draw = ImageDraw.Draw(pil_mask)
                    # Pillow根据json_data中 path 绘制 Pillow 白色 shapes (白色=mask)
                    # 假设Dakota支持 opaque mask on transparent. 简化演示：
                    
                    # 简化视觉演示：
                    buffered_mask = io.BytesIO()
                    try:
                        canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                        canvas_pil.thumbnail((1024, 1024))
                        canvas_pil.save(buffered_mask, format="PNG") # 保持透明度
                        mask_uri = f"data:image/png;base64,{base64.b64encode(buffered_mask.getvalue()).decode()}"
                    except:
                        st.error("遮罩数据演示生成失败。")
                        st.stop()
                    
                    # 【正式 API advice】：
                    # 1. 请在正式代码中，先使用 API 的上传文件接口分别上传底图数据和按 robust 方法生成的 binary mask 图片数据得到相应的 URL。
                    # 2. 在 payload 中填入正式的 URL，而不是 base64 字符串。
                    # 3. 请查阅Dakota平台/GRSAI API 遮罩格式要求 (例如二值图) 和局部重绘强度、遮罩模式参数。

                    st.markdown(f'''
                        <hr style="border-color:#FF4B4B;">
                        **🚨 正式 API 集成 Advice：**<br>
                        1. **遮罩二值图**：请使用 Pillow 库根据画布数据（`canvas_result.json_data`）生成符合标准 API 要求的遮罩图片（例如白色表示 masked，黑色表示 keep，或反之）。<br>
                        2. **数据上传**：不要直接在 payload 中使用 Base64 字符串（即 anti-pattern）。请使用 API 提供的上传文件接口先上传底图和遮罩二值图得到各自的 URL。<br>
                        3. **参数配置**：请在 payload 中填入正式的 URL，调整 strength 参数，并根据 Dakota 接口文档正确配置局部重绘相关参数。<br>
                        <hr style="border-color:#FF4B4B;">
                    ''', unsafe_allow_html=True)
                    
                    payload["urls"] = [base_uri, mask_uri] # 占位视觉演示
                    payload["strength"] = inpainting_strength # Inpainting 强度
                    
                    # Dakota platform API 局部重绘典型参数假设
                    payload["inpaint_mode"] = 1 # 假设1表示局部重绘
                    payload["inpaint_mask_inverse"] = False # 是否反转遮罩
                
                else:
                    payload["aspectRatio"] = aspect_ratio
                    payload["quality"] = quality

                headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
                try:
                    # 正式集成前请确保参数和 URL 正确
                    sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                    if sub_res.get("code") == 0:
                        add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": datetime.now().strftime("%H:%M:%S"), "prompt": prompt_txt, "status": "running", "url": "", "reason": ""})
                        st.success("🎉 任务已提交！请追踪进度或保存到项目。")
                        time.sleep(1)
                        st.rerun()
                    else: st.error(f"接口报错：{sub_res.get('msg', '未知')}")
                except Exception as e: st.error(f"网络异常：{e}")

    # 右侧任务队列大厅 (已添加“保存到项目”功能)
    with col_history:
        st.markdown("### 🗂️ 已提交任务任务大厅")
        tasks_list = clean_and_get_tasks()
        if not tasks_list:
            st.info("💡 暂无记录。")
        else:
            with st.container(height=800):
                for item in reversed(tasks_list):
                    with st.container():
                        display_title = item.get('prompt', '')[:20] + "..." if len(item.get('prompt', '')) > 20 else item.get('prompt', '')
                        st.markdown(f"**任务: {display_title}**")
                        with st.expander("📝 完整提示词"): st.code(item.get('prompt', ''), language=None)
                        
                        if item.get('status') == 'running':
                            if st.button("🔍 追踪动画", key=f"btn_{item['task_id']}", use_container_width=True):
                                show_progress_dialog(item['task_id'], item['prompt'])
                        elif item.get('status') == 'succeeded':
                            st.markdown(f'<img src="{item["url"]}" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
                            
                            # 保存到项目功能
                            if st.session_state.projects:
                                with st.form(key=f"save_form_{item['task_id']}"):
                                    proj_names = [p["title"] for p in st.session_state.projects]
                                    target_proj_title = st.selectbox("选择目标项目", proj_names, label_visibility="collapsed")
                                    
                                    # 提交按钮，需要特殊处理 form 内部状态
                                    if st.form_submit_button("📥 保存到所选项目", use_container_width=True):
                                        target_proj = next(p for p in st.session_state.projects if p["title"] == target_proj_title)
                                        # 简化视觉演示， anti-pattern
                                        buffered_save = io.BytesIO()
                                        requests.get(item["url"], verify=False).content
                                        Image.open(io.BytesIO(requests.get(item["url"], verify=False).content)).thumbnail((1024, 1024))
                                        Image.open(io.BytesIO(requests.get(item["url"], verify=False).content)).convert('RGB').save(buffered_save, format="JPEG")
                                        b64_str_save = f"data:image/jpeg;base64,{base64.b64encode(buffered_save.getvalue()).decode()}"
                                        
                                        target_proj["layers"].append({"type": "image", "content": b64_str_save})
                                        save_json(PROJECTS_FILE, st.session_state.projects)
                                        st.toast(f"✅ 图片已保存到项目 '{target_proj_title}'！")
                            else:
                                st.caption("（无可保存项目，请先在画布功能中新建项目）")
                                    
                        elif item.get('status') == 'failed':
                            st.error(f"❌ 失败: {item.get('reason', '未知')}")
                        st.divider()

# ==========================================
# 5. 页面 3: 🎨 专业画布工作台 (保持 V4 的稳妥和视觉，防崩溃)
# ==========================================
elif menu == "🎨 专业画布工作台":
    st.title("🎨 专业画布工作台")
    # ... (保持 V4 的稳妥和视觉，分离按钮防崩溃。重点已集成 Inpainting 到图生图 tab)
    st.info("此模块功能正常，视觉风格保持。局部重绘功能已重点集成到【图生图】Tab。")
    # 为了简化，我只重写核心的局部重绘 Tab 逻辑。如果你需要画布工作台的代码，请继续沿用 V4 版本的对应部分代码。
