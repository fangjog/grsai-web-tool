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
# 0. 网页基础配置 (必须是第一句) 
# ==========================================
st.set_page_config(page_title="image-2 V2", page_icon="🎨", layout="wide")

# ==========================================
# 1. 安全密钥读取与映射
# ==========================================
# 激活码与 secrets.toml 密钥变量名的对应关系 [cite: 18]
KEY_MAP = {
    "vip888": "API_VIP",
    "test1234": "API_TEST",
    "123": "API_123",
    "free_trial": "GRSAI_API_KEY"
}

# 激活码与积分余额的映射关系
KEY_POINTS = {
    "vip888": 10000,
    "test1234": 5000,
    "123": 5000,
    "free_trial": 600
}

st.sidebar.markdown("### 身份验证")
# 加入 .strip() 防止用户输入时带了空格导致验证失败
user_key_input = st.sidebar.text_input("🔑 请输入激活码/卡密", type="password")
user_key = user_key_input.strip() if user_key_input else ""

if not user_key or user_key not in KEY_MAP:
    st.warning("👈 请在左侧输入有效的激活码以解锁系统。")
    st.stop()

# 尝试获取 API Key，如果失败则给出更详细的提示 [cite: 20]
secret_name = KEY_MAP[user_key]
if secret_name in st.secrets:
    GRSAI_API_KEY = st.secrets[secret_name]
    st.sidebar.success(f"✅ 验证通过，已加载账户：{secret_name}")
else:
    st.error(f"⚠️ 找不到配置：请在 Secrets 中添加 `{secret_name} = \"你的SK密钥\"` 并保存。")
    st.stop()

# ==========================================
# 2. 增强版任务与积分持久化系统
# ==========================================
TASKS_FILE = "tasks_history.json"
POINTS_FILE = "points_data.json"

def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_tasks(task_list):
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(task_list, f, ensure_ascii=False)
    except:
        pass

def load_points():
    if os.path.exists(POINTS_FILE):
        try:
            with open(POINTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"cost": 600}

def clean_and_get_tasks():
    if 'tasks' not in st.session_state:
        st.session_state.tasks = load_tasks()
    current_time = time.time()
    valid_tasks = [t for t in st.session_state.tasks if (current_time - t['timestamp']) < 3600]
    valid_tasks = valid_tasks[-10:]
    if len(valid_tasks) != len(st.session_state.tasks):
        st.session_state.tasks = valid_tasks
        save_tasks(valid_tasks)
    return st.session_state.tasks

def add_task(item):
    tasks = clean_and_get_tasks()
    tasks.append(item)
    st.session_state.tasks = tasks
    save_tasks(tasks)

# ==========================================
# 3. 图像处理辅助函数 (100% HTML 兼容)
# ==========================================
def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    base64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{base64_str}"

# ==========================================
# 4. 弹窗子页面：实时追踪进度 (带动画)
# ==========================================
@st.experimental_dialog("🔍 实时生图进度", width="large")
def show_progress_dialog(task_id, prompt_text):
    st.markdown(f"**当前任务:** `{prompt_text}`")
    progress_bar = st.progress(0)
    status_text = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    
    for i in range(40):
        p = min(5 + i*2, 95)
        track_len = 25
        pos = int((p / 100) * track_len)
        track = "━" * pos + "🏃‍♂️" + "  " * (track_len - pos) + "🏁"
        status_text.markdown(f"**正在云端为您绘制中...**\n\n{track} **{p}%**")
        progress_bar.progress(p)
        try:
            q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
            if q_res.get("code") == 0:
                status = q_res["data"]["status"]
                if status == "succeeded":
                    progress_bar.progress(100)
                    img_url = q_res["data"]["results"][0]["url"]
                    status_text.success("✅ **生成成功！请关闭此弹窗即可查看结果。**")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'succeeded'
                            t['url'] = img_url
                    save_tasks(st.session_state.tasks)
                    time.sleep(1)
                    st.rerun()
                elif status == "failed":
                    reason = q_res["data"].get("failure_reason", "未知错误")
                    status_text.error(f"❌ **生成失败！原因:** {reason}")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'failed'
                            t['reason'] = reason
                    save_tasks(st.session_state.tasks)
                    break
        except:
            pass
        time.sleep(3)

# ==========================================
# 5. 前端网页 UI 布局
# ==========================================
st.title("🚀 image-2 V2")

current_points = KEY_POINTS.get(user_key, 600)
saved_pts = load_points()
cost_input = saved_pts.get("cost", 600)
max_images = current_points / cost_input

st.sidebar.markdown("---")
st.sidebar.markdown("#### ⚙️ 积分状态")
st.sidebar.markdown(f"**可用总积分:** `{current_points}`")
st.sidebar.markdown(f"**消耗/张:** `{cost_input}`")
st.sidebar.markdown(f"**剩余张数:** `≈ **{int(max_images)}** 张`")

col_main, col_history = st.columns([7, 3])

with col_main:
    tab1, tab2 = st.tabs(["✍️ 文生图", "🖌️ 画布与图生图"])
    with tab1:
        st.markdown("#### 📝 输入描述直接生成画面")
        prompt_txt = st.text_area("画面详细描述", height=120, key="txt2img_prompt")
        col1_1, col1_2 = st.columns(2)
        with col1_1:
            aspect_ratio_txt = st.selectbox("📏 画幅比例", ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "auto"], key="txt_ratio")
        with col1_2:
            quality_txt = st.selectbox("💎 图片质量", ["auto", "high", "medium", "low"], key="txt_quality")
        btn_txt2img = st.button("✨ 提交任务 (异步排队)", key="btn_submit_txt")

    with tab2:
        st.markdown("#### 🖌️ 上传参考图或在下方画布涂鸦")
        uploaded_files = st.file_uploader("支持多张上传", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
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
                    label = "图1 (底图)" if idx == 0 else f"图{idx+1}"
                    html_img = f'''
                    <div style="display: inline-block; margin-right: 10px; text-align: center;">
                        <div style="font-size: 11px; color: #666;">{label}</div>
                        <img src="data:image/jpeg;base64,{b64_str}" style="height: 60px; border-radius: 4px;">
                    </div>
                    '''
                    html_snippets.append(html_img)
                except:
                    pass
            st.markdown("".join(html_snippets), unsafe_allow_html=True)

        canvas_result = st_canvas(
            stroke_width=3, stroke_color="#000000", background_image=canvas_bg,
            height=400, drawing_mode="freedraw", key="canvas",
        )
        prompt_img = st.text_area("修改指令或画面描述", height=80, key="img2img_prompt")
        btn_img2img = st.button("✨ 提交任务 (异步排队)", key="btn_submit_img")

    if btn_txt2img or btn_img2img:
        mode = "txt2img" if btn_txt2img else "img2img"
        current_prompt = prompt_txt if mode == "txt2img" else prompt_img
        if not current_prompt:
            st.error("❌ 请输入提示词！")
        else:
            payload = {"model": "gpt-image-2", "prompt": current_prompt, "webHook": "-1", "shutProgress": True}
            if mode == "img2img":
                urls_list = []
                if canvas_result.image_data is not None:
                    canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    urls_list.append(pil_to_data_uri(canvas_pil))
                if uploaded_files and len(uploaded_files) > 1:
                    for file in uploaded_files[1:]:
                        try:
                            urls_list.append(pil_to_data_uri(Image.open(io.BytesIO(file.getvalue()))))
                        except: pass
                payload["urls"] = urls_list 
            else:
                payload["aspectRatio"] = aspect_ratio_txt
                payload["quality"] = quality_txt

            headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
            try:
                sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                if sub_res.get("code") == 0:
                    add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": datetime.now().strftime("%H:%M:%S"), "prompt": current_prompt, "status": "running", "url": "", "reason": ""})
                    st.success("🎉 任务已提交！请在右侧点击查看动画。")
                    time.sleep(1)
                    st.rerun()
                else: st.error(f"接口报错：{sub_res.get('msg', '未知')}")
            except Exception as e: st.error(f"网络异常：{e}")

# ==========================================
# 6. 右侧任务大厅
# ==========================================
with col_history:
    st.markdown("### 🗂️ 任务大厅")
    tasks_list = clean_and_get_tasks()
    if not tasks_list:
        st.info("💡 暂无任务。")
    else:
        for item in reversed(tasks_list):
            with st.container():
                st.markdown(f"**[{item['time_str']}]**")
                if item.get('status') == 'running':
                    if st.button("🔍 追踪动画", key=f"btn_{item['task_id']}", use_container_width=True):
                        show_progress_dialog(item['task_id'], item['prompt'])
                elif item.get('status') == 'succeeded':
                    st.markdown(f'<img src="{item["url"]}" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
                    st.markdown(f"**[📥 下载高清原图]({item['url']})**")
                elif item.get('status') == 'failed':
                    st.error(f"❌ 失败: {item.get('reason', '未知')}")
                st.divider()
