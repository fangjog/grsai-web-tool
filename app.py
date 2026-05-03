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

# ==========================================
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI Pro Image Studio V6.0", page_icon="🚀", layout="wide")

# ==========================================
# 🌟🌟🌟🌟🌟 【管理员专用配置区】 🌟🌟🌟🌟🌟
# ==========================================
KEY_MAP = {
    "vip888": "API_VIP",
    "test1234": "API_TEST",
    "123": "API_123",
    "free_trial": "GRSAI_API_KEY"
}
# 初始总积分
KEY_POINTS = {"vip888": 3000, "test1234": 5000, "123": 5000, "free_trial": 600}
# 单张成本
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

# 任务历史初始化
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
                    deduct_balance(active_user_key, IMAGE_COST) # 成功后扣款
                    status_text.success("✅ **生成成功！(已自动扣除 1 张额度)**")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'succeeded'
                            t['url'] = img_url
                    save_json(TASKS_FILE, st.session_state.tasks)
                    time.sleep(1.5)
                    st.rerun()
                elif status == "failed":
                    reason = q_res["data"].get("failure_reason", "安全审查或系统异常")
                    status_text.error(f"❌ **任务失败:** {reason} (失败不扣费)")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'failed'
                            t['reason'] = reason
                    save_json(TASKS_FILE, st.session_state.tasks)
                    break
        except: pass
        time.sleep(3)

# ==========================================
# 侧边栏状态
# ==========================================
current_balance = get_balance(user_key)
max_images = int(current_balance // IMAGE_COST)

st.sidebar.markdown(f'剩余可制图数量: <span style="color:#FF4B4B; font-weight:bold; font-size:18px;">{max_images}</span> 张', unsafe_allow_html=True)
st.sidebar.divider()
menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图"]) # 🌟 已删掉画布选项

# ==========================================
# 页面内容
# ==========================================

st.title("🚀 image-2 Pro Studio")

col_main, col_history = st.columns([7, 3])

with col_main:
    if menu == "✍️ 文生图":
        st.markdown("#### 📝 文生图模式")
        prompt_txt = st.text_area("输入画面详细描述", height=120, placeholder="例如：一个赛博朋克风格的繁华都市，雨夜，霓虹灯倒影在积水中...")
        c1, c2 = st.columns(2)
        with c1: aspect_ratio = st.selectbox("📏 画幅比例", ["16:9", "9:16", "1:1", "4:3", "3:4"])
        with c2: quality = st.selectbox("💎 图片质量", ["auto", "high", "medium", "low"])
        btn_submit = st.button("✨ 立即生成", type="primary", use_container_width=True)
        
    else: 
        st.markdown("#### 🖼️ 图生图模式")
        uploaded_files = st.file_uploader("📤 上传参考图 (支持多张参考)", type=["png", "jpg"], accept_multiple_files=True)
        
        # 涂鸦板作为兜底
        canvas_result = None
        if not uploaded_files:
            st.info("💡 提示：您也可以在下方直接涂鸦草图作为生成参考。")
            canvas_result = st_canvas(
                fill_color="rgba(255, 165, 0, 0.3)", stroke_width=3, stroke_color="#000000",
                background_color="#ffffff", height=400, drawing_mode="freedraw", key="canvas_img2img"
            )
            
        prompt_txt = st.text_area("指令/修改描述", height=80, placeholder="例如：保持原图风格，把背景换成森林...")
        btn_submit = st.button("🚀 开始垫图生成", type="primary", use_container_width=True)

    # 提交逻辑
    if btn_submit:
        if get_balance(user_key) < IMAGE_COST:
            st.error("❌ 额度不足，请联系管理员充值。")
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
                elif canvas_result and canvas_result.image_data is not None:
                    try:
                        canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                        urls_list.append(pil_to_data_uri(canvas_pil))
                    except: pass
                
                if not urls_list:
                    st.error("⚠️ 图生图模式需要上传图片或进行涂鸦。")
                    st.stop()
                payload["urls"] = urls_list
            else:
                payload["aspectRatio"] = aspect_ratio
                payload["quality"] = quality

            headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
            try:
                sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                if sub_res.get("code") == 0:
                    add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": datetime.now().strftime("%H:%M"), "prompt": prompt_txt, "status": "running", "url": ""})
                    st.success("🎉 任务已提交云端！")
                    time.sleep(1)
                    st.rerun()
                else: st.error(f"接口报错：{sub_res.get('msg', '未知故障')}")
            except Exception as e: st.error(f"网络连接异常")

# 右侧历史大厅
with col_history:
    st.markdown("### 🗂️ 创作记录")
    tasks_list = clean_and_get_tasks()
    if not tasks_list:
        st.info("暂无生成记录。")
    else:
        with st.container(height=800):
            for item in reversed(tasks_list):
                with st.container():
                    st.markdown(f"**[{item['time_str']}]**")
                    if item.get('status') == 'running':
                        if st.button("🔍 查看进度", key=f"btn_{item['task_id']}", use_container_width=True):
                            show_progress_dialog(item['task_id'], item['prompt'], user_key)
                    elif item.get('status') == 'succeeded':
                        st.image(item['url'])
                        st.markdown(f"**[📥 点击下载原图]({item['url']})**")
                    elif item.get('status') == 'failed':
                        st.error("❌ 生成失败")
                    st.divider()
