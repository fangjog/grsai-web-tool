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
# 激活码与 secrets.toml 密钥变量名的对应关系
KEY_MAP = {
    "vip888": "API_VIP",
    "test1234": "API_TEST",
    "123": "API_123"
}

# 激活码与积分余额的映射关系
KEY_POINTS = {
    "vip888": 10000,
    "test1234": 5000,
    "123": 5000,
    "free_trial": 600
}

# 侧边栏：输入激活码
user_key = st.sidebar.text_input("🔑 请输入激活码/卡密", type="password")

if not user_key or user_key not in KEY_MAP:
    st.warning("👈 请在左侧输入有效的激活码以解锁系统。")
    st.stop()

st.sidebar.success("✅ 验证通过，欢迎使用！")

try:
    secret_name = KEY_MAP[user_key]
    GRSAI_API_KEY = st.secrets[secret_name]
except:
    st.error("⚠️ 未在 Secrets 中找到该激活码对应的 API Key 配置。")
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

def save_points(cost):
    try:
        with open(POINTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"cost": cost}, f, ensure_ascii=False)
    except:
        pass

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
# 3. 图像处理辅助函数
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
# 4. 弹窗子页面：实时追踪进度 (带小人跑步动画)
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
                    status_text.success("✅ **生成成功！(请关闭此弹窗，即可在右侧大厅下载高清原图)**")
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'succeeded'
                            t['url'] = img_url
                    save_tasks(st.session_state.tasks)
                    time.sleep(2)
                    st.rerun()
                    
                elif status == "failed":
                    progress_bar.empty()
                    reason = q_res["data"].get("failure_reason", "未知错误")
                    if reason in ["output_moderation", "input_moderation"]: reason = "提示词或画面触发安全审查违规"
                    status_text.error(f"❌ **生成失败！原因:** {reason}")
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'failed'
                            t['reason'] = reason
                    save_tasks(st.session_state.tasks)
                    time.sleep(2)
                    st.rerun()
        except:
            pass
        time.sleep(3)
    status_text.warning("查询超时，请稍后直接在右侧任务大厅刷新状态。")

# ==========================================
# 5. 前端网页 UI 布局
# ==========================================
st.title("🚀 image-2 V2")

current_points = KEY_POINTS.get(user_key, 600)
saved_pts = load_points()
cost_input = saved_pts["cost"]
max_images = current_points / cost_input

st.sidebar.markdown("---")
st.sidebar.markdown("#### ⚙️ 积分管理后台")
st.sidebar.markdown(f"**您的当前可用总积分:** `{current_points}`")
st.sidebar.markdown(f"**单张图片消耗积分:** `{cost_input}`")
st.sidebar.markdown(f"**剩余可生成次数:** `{current_points} / {cost_input} = **{max_images:.5f}** 张图`")

col_main, col_history = st.columns([7, 3])

with col_main:
    tab1, tab2 = st.tabs(["✍️ 文生图", "🖌️ 画布与图生图"])

    with tab1:
        st.markdown("#### 📝 输入描述直接生成画面")
        prompt_txt = st.text_area("画面详细描述 (支持中文直出)", height=120, key="txt2img_prompt")
        
        col1_1, col1_2 = st.columns(2)
        with col1_1:
            aspect_ratio_txt = st.selectbox("📏 画幅比例", ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "auto"], key="txt_ratio")
        with col1_2:
            quality_txt = st.selectbox("💎 图片质量", ["auto", "high", "medium", "low"], key="txt_quality")
            
        btn_txt2img = st.button("✨ 提交任务 (异步排队)", key="btn_submit_txt")

    with tab2:
        st.markdown("#### 🖌️ 上传参考图或在下方画布涂鸦")
        uploaded_files = st.file_uploader("支持一次性框选多张图上传", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        
        canvas_bg = None
        if uploaded_files:
            st.markdown("📎 **您上传的图片预览：**")
            html_snippets = []
            for idx, file in enumerate(uploaded_files):
                try:
                    if idx == 0:
                        canvas_bg = Image.open(io.BytesIO(file.getvalue()))
                        canvas_bg.thumbnail((1024, 1024))
                        
                    bytes_data = file.getvalue()
                    b64_str = base64.b64encode(bytes_data).decode("utf-8")
                    mime_type = file.type if file.type else "image/jpeg"
                    label = "图1 (画板底图)" if idx == 0 else f"图{idx+1} (附加参考)"
                    
                    html_img = f'''
                    <div style="display: inline-block; margin-right: 15px; margin-bottom: 10px; text-align: center; background: #f0f2f6; padding: 8px; border-radius: 8px; border: 1px solid #ddd;">
                        <div style="font-size: 13px; font-weight: bold; color: #444; margin-bottom: 6px;">{label}</div>
                        <img src="data:{mime_type};base64,{b64_str}" style="height: 80px; width: 80px; object-fit: cover; border-radius: 4px; border: 1px solid #ccc; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    </div>
                    '''
                    html_snippets.append(html_img)
                except:
                    pass
            if html_snippets:
                st.markdown("".join(html_snippets), unsafe_allow_html=True)

        st.caption("在下方区域使用鼠标绘制内容，它将作为主垫图参考：")
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)", 
            stroke_width=3,
            stroke_color="#000000",
            background_image=canvas_bg,
            update_streamlit=True,
            height=400,
            drawing_mode="freedraw",
            key="canvas",
        )
        
        prompt_img = st.text_area("画面描述 (修改指令或最终画面描述)", height=80, key="img2img_prompt")
        btn_img2img = st.button("✨ 提交任务 (异步排队)", key="btn_submit_img")

    if btn_txt2img or btn_img2img:
        mode = "txt2img" if btn_txt2img else "img2img"
        current_prompt = prompt_txt if mode == "txt2img" else prompt_img
        
        if not current_prompt:
            st.error("❌ 提示词描述不能为空！")
        else:
            payload = {
                "model": "gpt-image-2",
                "prompt": current_prompt,
                "webHook": "-1",
                "shutProgress": True
            }
            
            if mode == "img2img":
                urls_list = []
                if canvas_result.image_data is not None:
                    canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    urls_list.append(pil_to_data_uri(canvas_pil))
                
                if uploaded_files and len(uploaded_files) > 1:
                    for file in uploaded_files[1:]:
                        try:
                            img_extra = Image.open(io.BytesIO(file.getvalue()))
                            urls_list.append(pil_to_data_uri(img_extra))
                        except:
                            pass
                payload["urls"] = urls_list 
            else:
                payload["aspectRatio"] = aspect_ratio_txt
                payload["quality"] = quality_txt

            headers = {
                "Authorization": f"Bearer {GRSAI_API_KEY}",
                "Content-Type": "application/json"
            }
            submit_url = "https://grsai.dakka.com.cn/v1/draw/completions"
            
            try:
                sub_res = requests.post(submit_url, headers=headers, json=payload, verify=False).json()
                if sub_res.get("code") == 0:
                    task_id = sub_res["data"]["id"]
                    add_task({
                        "task_id": task_id,
                        "timestamp": time.time(),
                        "time_str": datetime.now().strftime("%H:%M:%S"),
                        "prompt": current_prompt,
                        "status": "running", 
                        "url": "",
                        "reason": ""
                    })
                    st.success("🎉 任务已极速发送至云端！请在右侧任务大厅点击【🔍 实时追踪】查看动画进度。")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error(f"⚠️ 提交接口报错：{sub_res.get('msg', sub_res)}")
            except Exception as e:
                st.error(f"❌ 网络或系统异常：{e}")

# ==========================================
# 6. 右侧任务大厅
# ==========================================
with col_history:
    st.markdown("### 🗂️ 任务大厅")
    st.caption("提示：队列仅保留1小时内任务。")
    
    tasks_list = clean_and_get_tasks()
    
    if not tasks_list:
        st.info("💡 暂无进行中的任务，快去左侧生成吧！")
    else:
        for item in reversed(tasks_list):
            with st.container():
                st.markdown(f"**[{item['time_str']}]**")
                short_prompt = item['prompt'][:15] + "..." if len(item['prompt']) > 15 else item['prompt']
                st.caption(f"✍️ {short_prompt}")
                
                if item.get('status') == 'running':
                    st.info("🔄 任务云端作画中...")
                    if st.button("🔍 实时追踪 / 查看动画", key=f"btn_{item['task_id']}", use_container_width=True):
                        show_progress_dialog(item['task_id'], item['prompt'])
                elif item.get('status') == 'failed':
                    st.error(f"❌ 失败: {item.get('reason', '未知')}")
                elif item.get('status') == 'succeeded':
                    html_result = f'''
                    <div style="border: 1px solid #ddd; padding: 4px; border-radius: 8px; background: #fff;">
                        <img src="{item["url"]}" style="width:100%; border-radius:4px; display: block; margin-bottom: 8px;">
                    </div>
                    '''
                    st.markdown(html_result, unsafe_allow_html=True)
                    st.markdown(f"**[📥 点击这里在浏览器打开并保存高清原图]({item['url']})**")
                st.divider()
