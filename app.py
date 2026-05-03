# 文件名: app.py
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

# 🌟 导入我们刚刚抽离出来的独立画布模块
import invoke_canvas

# ==========================================
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI Pro Workspace V5.1", page_icon="🚀", layout="wide")

# ==========================================
# 🌟🌟🌟🌟🌟 【管理员专用配置区】 🌟🌟🌟🌟🌟
# ==========================================
KEY_MAP = {
    "vip888": "API_VIP",
    "test1234": "API_TEST",
    "123": "API_123",
    "free_trial": "GRSAI_API_KEY"
}
KEY_POINTS = {"vip888": 3000, "test1234": 5000, "123": 5000, "free_trial": 600}
IMAGE_COST = 600

# 工具函数：JSON 存取
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

# ==========================================
# 身份验证 & 动态积分扣除系统
# ==========================================
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

USAGE_FILE = "usage_data.json"
TASKS_FILE = "tasks_history.json"

def get_balance(key):
    usage = load_json(USAGE_FILE, {})
    spent = usage.get(key, 0)
    total = KEY_POINTS.get(key, 0)
    return max(0, total - spent)

def deduct_balance(key, amount):
    usage = load_json(USAGE_FILE, {})
    spent = usage.get(key, 0)
    usage[key] = spent + amount
    save_json(USAGE_FILE, usage)

# 将余额存入 session_state 供其他模块（如 invoke_canvas）随时读取
st.session_state.balance_points = get_balance(user_key)

if 'tasks' not in st.session_state: st.session_state.tasks = load_json(TASKS_FILE)

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
# 动画进度弹窗 (含扣款逻辑)
# ==========================================
@st.experimental_dialog("🔍 实时生图进度", width="large")
def show_progress_dialog(task_id, prompt_text, active_user_key):
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
                    deduct_balance(active_user_key, IMAGE_COST) # 成功后扣款
                    status_text.success("✅ **生成成功！(已自动扣除本次制图额度)**")
                    
                    # 兼容双列表：主大厅和画布独立大厅
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'succeeded'
                            t['url'] = img_url
                    save_json(TASKS_FILE, st.session_state.tasks)
                    
                    if 'invoke_tasks_list' in st.session_state:
                        for t in st.session_state.invoke_tasks_list:
                            if t['task_id'] == task_id:
                                t['status'] = 'succeeded'
                                t['url'] = img_url
                        save_json("invoke_workspace_project.json", st.session_state.invoke_tasks_list)
                    
                    time.sleep(1.5)
                    st.rerun()
                elif status == "failed":
                    reason = q_res["data"].get("failure_reason", "未知错误")
                    status_text.error(f"❌ **失败:** {reason} (失败不扣除额度)")
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'failed'
                            t['reason'] = reason
                    save_json(TASKS_FILE, st.session_state.tasks)
                    
                    if 'invoke_tasks_list' in st.session_state:
                        for t in st.session_state.invoke_tasks_list:
                            if t['task_id'] == task_id:
                                t['status'] = 'failed'
                                t['reason'] = reason
                        save_json("invoke_workspace_project.json", st.session_state.invoke_tasks_list)
                        
                    break
        except: pass
        time.sleep(3)

# ==========================================
# 侧边栏导航与状态
# ==========================================
max_images = int(st.session_state.balance_points // IMAGE_COST)

st.sidebar.markdown(f'剩余可制图数量: <span style="color:#FF4B4B; font-weight:bold; font-size:18px;">{max_images}</span> 张', unsafe_allow_html=True)
st.sidebar.divider()
menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图", "🎨 专业画布工作台"])

# ==========================================
# 页面分发路由
# ==========================================

# --- 路由 1 & 2：文生图 / 图生图 ---
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
            
        else: 
            st.markdown("#### 🖼️ 图生图 (支持涂鸦参考 / 整图参考)")
            uploaded_files = st.file_uploader("📤 上传参考底图 (支持多张)", type=["png", "jpg"], accept_multiple_files=True)
            canvas_result = None
            
            if not uploaded_files:
                st.info("💡 当前未上传图片：您可以在下方画板自由涂鸦草图作为参考。")
                canvas_result = st_canvas(
                    fill_color="rgba(255, 165, 0, 0.3)", stroke_width=3, stroke_color="#000000",
                    background_color="#ffffff", height=400, drawing_mode="freedraw", key="canvas_img2img"
                )
            else:
                st.success("✅ 已上传图片参考，涂鸦画板自动隐藏。")
                st.markdown("📎 **上传预览：**")
                html_snippets = []
                for idx, file in enumerate(uploaded_files):
                    try:
                        b64_str = base64.b64encode(file.getvalue()).decode("utf-8")
                        html_img = f'''
                        <div style="display: inline-block; margin-right: 15px; margin-bottom: 10px; text-align: center; background: #f0f2f6; padding: 8px; border-radius: 8px; border: 1px solid #ddd;">
                            <div style="font-size: 13px; font-weight: bold; color: #444; margin-bottom: 6px;">图{idx+1}</div>
                            <img src="data:image/jpeg;base64,{b64_str}" style="height: 80px; width: 80px; object-fit: cover; border-radius: 4px; border: 1px solid #ccc; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        </div>
                        '''
                        html_snippets.append(html_img)
                    except: pass
                st.markdown("".join(html_snippets), unsafe_allow_html=True)
                
            prompt_txt = st.text_area("修改指令或最终画面描述", height=80, key="prompt_img2img")
            btn_submit = st.button("✨ 提交任务 (图生图)", type="primary", key="btn_img2img")

        if btn_submit:
            if st.session_state.balance_points < IMAGE_COST:
                st.error("❌ 当前激活码额度不足，无法生成！")
            elif not prompt_txt:
                st.error("❌ 请输入提示词！")
            else:
                payload = {"model": "gpt-image-2", "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
                
                if menu == "🖼️ 图生图":
                    urls_list = []
                    if uploaded_files:
                        for file in uploaded_files:
                            try: urls_list.append(pil_to_data_uri(Image.open(io.BytesIO(file.getvalue()))))
                            except: pass
                    else:
                        if canvas_result is not None and canvas_result.image_data is not None:
                            try:
                                canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                                urls_list.append(pil_to_data_uri(canvas_pil))
                            except: pass
                            
                    if not urls_list:
                        st.error("⚠️ 获取参考图失败，请检查上传文件或涂鸦板状态。")
                        st.stop()
                    payload["urls"] = urls_list
                else:
                    payload["aspectRatio"] = aspect_ratio
                    payload["quality"] = quality

                headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
                try:
                    sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                    if sub_res.get("code") == 0:
                        add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": datetime.now().strftime("%H:%M:%S"), "prompt": prompt_txt, "status": "running", "url": "", "reason": ""})
                        st.success("🎉 任务已提交！等待成功后将自动扣除额度。")
                        time.sleep(1)
                        st.rerun()
                    else: st.error(f"接口报错：{sub_res.get('msg', '未知')}")
                except Exception as e: st.error(f"网络异常：{e}")

    # 右侧任务队列大厅 
    with col_history:
        st.markdown("### 🗂️ 已提交任务大厅")
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
                                show_progress_dialog(item['task_id'], item['prompt'], user_key)
                        elif item.get('status') == 'succeeded':
                            st.markdown(f'<img src="{item["url"]}" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
                        elif item.get('status') == 'failed':
                            st.error(f"❌ 失败: {item.get('reason', '未知')}")
                        st.divider()

# --- 路由 3：独立出去的画布工作台 ---
elif menu == "🎨 专业画布工作台":
    # 🌟 修复点在这里：严格传入 3 个参数 (API Key, 用户激活码, 图片成本)
    invoke_canvas.render_canvas_workspace(GRSAI_API_KEY, user_key, IMAGE_COST)
    
    # 监听是否在 invoke_canvas 里按下了追踪进度按钮
    if 'invoke_tasks_accounted' in st.session_state and st.session_state.invoke_tasks_accounted:
        task = st.session_state.invoke_tasks_accounted
        st.session_state.invoke_tasks_accounted = None # 清空标志
        show_progress_dialog(task['task_id'], task['prompt'], user_key)
