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
from supabase import create_client, Client

# ==========================================
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.5", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.5rem !important; }
        h1 { font-size: 24px !important; }
        .stButton > button { width: 100% !important; padding: 15px !important; font-size: 16px !important; border-radius: 12px !important; }
        footer { visibility: hidden; }
    }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    [data-testid="stHorizontalBlock"] > div { min-width: 80px !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 数据库与初始化
# ==========================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("❌ 数据库连接失败，请检查 Secrets 配置。")
    st.stop()

# 🌟 新增：动态模型定价表
MODEL_COSTS = {
    "gpt-image-2": 600,
    "gpt-image-2-vip": 900
}

TASKS_FILE = "tasks_history.json"

def load_json(path, default={}):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
    except: pass

def get_card_info(card_key):
    try:
        res = supabase.table("user_cards").select("*").eq("card_key", card_key).eq("is_active", True).execute()
        if res.data: return res.data[0]
    except: pass
    return None

def deduct_balance(card_key, amount):
    try:
        res = supabase.table("user_cards").select("used_points").eq("card_key", card_key).execute()
        if res.data:
            new_val = res.data[0]['used_points'] + amount
            supabase.table("user_cards").update({"used_points": new_val}).eq("card_key", card_key).execute()
    except: pass

# ==========================================
# 2. 居中拦截式身份验证
# ==========================================
query_key = st.query_params.get("key", "")
card_info = get_card_info(query_key) if query_key else None

if not card_info:
    st.markdown("<br><br><br>", unsafe_allow_html=True) 
    col1, col2, col3 = st.columns([1, 2, 1]) 
    with col2:
        st.markdown("<div style='text-align: center;'><h1>🚀 AI Pro Studio</h1><p>输入激活码解锁创作台</p></div>", unsafe_allow_html=True)
        user_key_input = st.text_input("激活码", type="password", placeholder="🔑 在此输入激活码...", label_visibility="collapsed")
        if st.button("立即解锁进入系统 ✨", type="primary", use_container_width=True):
            user_key = user_key_input.strip()
            check_info = get_card_info(user_key)
            if check_info:
                st.query_params["key"] = user_key
                st.rerun()
            else: st.error("❌ 激活码无效。")
    st.stop() 

user_key = query_key
current_balance = card_info['total_points'] - card_info['used_points']
clean_api_name = (card_info.get('api_secret_name') or "API_VIP888").strip("'").strip()
GRSAI_API_KEY = st.secrets.get(clean_api_name, "")

# ==========================================
# 3. 任务队列隔离
# ==========================================
all_history = load_json(TASKS_FILE, default={})
if isinstance(all_history, list): all_history = {}
if 'tasks' not in st.session_state: st.session_state.tasks = all_history.get(user_key, [])

def clean_and_get_tasks(active_key):
    curr_time = time.time()
    valid = [t for t in st.session_state.tasks if (curr_time - t['timestamp']) < 3600]
    valid = valid[-10:]
    st.session_state.tasks = valid
    global_history = load_json(TASKS_FILE, default={})
    if isinstance(global_history, list): global_history = {}
    global_history[active_key] = valid
    save_json(TASKS_FILE, global_history)
    return valid

def add_task(item, active_key):
    st.session_state.tasks.append(item)
    clean_and_get_tasks(active_key)

def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

# ==========================================
# 进度展示 (动态阶梯计费 + 智能中文报错版)
# ==========================================
def show_progress_dialog(task_id, prompt_text, active_user_key, model_used):
    with st.container():
        st.markdown("---")
        st.markdown(f"**🔍 实时生图进度**\n\n**任务描述:** `{prompt_text}`")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    
    cost_per_img = MODEL_COSTS.get(model_used, 600)
    
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
                    results = q_res["data"]["results"]
                    num_images = len(results)
                    
                    total_cost = num_images * cost_per_img
                    deduct_balance(active_user_key, total_cost)
                    status_text.success(f"✅ **生成成功！(共出 {num_images} 张，已扣除 {total_cost} 积分)**")
                    
                    urls = [img["url"] for img in results]
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'succeeded'
                            t['urls'] = urls
                    clean_and_get_tasks(active_user_key)
                    time.sleep(1.5)
                    st.rerun()
                elif status == "failed":
                    # 🌟 智能错误捕获与自动翻译拦截器 🌟
                    raw_reason = q_res["data"].get("failure_reason", "")
                    raw_error = q_res["data"].get("error", "")
                    
                    # 提取真正的报错信息（优先抓取 error 字段）
                    actual_err = raw_error if raw_error and raw_error != "error" else raw_reason
                    
                    # 常见英文报错本地翻译映射表（后续有新的英文报错，可以直接在这里加）
                    error_dict = {
                        "The current model has a high load, please use another model": "当前模型并发排队拥挤，请稍后再试，或切换至 其他 模型",
                        "error": "云端生成异常或触发安全审查，请调整提示词"
                    }
                    
                    # 匹配翻译，如果没有匹配到，就显示原英文
                    cn_error = error_dict.get(actual_err, f"系统异常: {actual_err}")
                    
                    status_text.error(f"❌ **任务失败:** {cn_error} (失败不扣除积分)")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id: t['status'] = 'failed'
                    clean_and_get_tasks(active_user_key)
                    break
        except: pass
        time.sleep(3)

# ==========================================
# 4. 主界面
# ==========================================
# 🌟 侧边栏展示升级：显示积分 + 预估张数
st.sidebar.markdown(f'### 👤 用户中心\n当前用户: `{user_key}`')
st.sidebar.markdown(f'剩余积分: <span style="color:#00c2ff; font-weight:bold; font-size:24px;">{current_balance}</span>', unsafe_allow_html=True)
st.sidebar.markdown(f'<div style="font-size:13px; color:#666;">标准模式约可制 <b style="color:#333;">{current_balance//600}</b> 张<br>VIP 模式约可制 <b style="color:#333;">{current_balance//900}</b> 张</div>', unsafe_allow_html=True)

if st.sidebar.button("🚪 退出登录", use_container_width=True):
    st.query_params.clear()
    if 'tasks' in st.session_state: del st.session_state.tasks
    st.rerun()
    
st.sidebar.divider()
menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图"])

st.title("🚀 AI Pro Studio")
col_main, col_history = st.columns([7, 3])

with col_main:
    selected_model = st.selectbox("🤖 选择创作模型", ["gpt-image-2", "gpt-image-2-vip"], help="VIP模型支持更高分辨率和更强细节")
    
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("输入画面详细描述", height=120, placeholder="描述词...")
        c1, c2 = st.columns(2)
        with c1: 
            ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2", "自定义像素"]
            aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts)
            custom_size = ""
            if aspect_ratio == "自定义像素":
                custom_size = st.text_input("输入像素值 (例如: 1024x1024)", placeholder="WxH")
        with c2: quality = st.selectbox("💎 图片质量", ["auto", "high", "medium", "low"])
        btn_submit = st.button("✨ 立即生成", type="primary", use_container_width=True)
        
    else: 
        st.markdown("#### 🖼️ 图生图模式")
        uploaded_files = st.file_uploader("📤 上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if uploaded_files:
            cols = st.columns(6) 
            for i, file in enumerate(uploaded_files):
                img_preview = Image.open(io.BytesIO(file.getvalue()))
                cols[i % 6].image(img_preview, caption=f"图 {i+1}", use_container_width=True)
        
        canvas_result = None
        if not uploaded_files:
            canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", stroke_width=3, background_color="#fff", height=300, key="cvs")
            
        prompt_txt = st.text_area("指令/修改描述", height=80)
        btn_submit = st.button("🚀 开始垫图生成", type="primary", use_container_width=True)

    if btn_submit:
        # 🌟 提交前校验：根据选择的模型查验余额
        required_points = MODEL_COSTS.get(selected_model, 600)
        if current_balance < required_points: 
            st.error(f"❌ 额度不足，当前模型需要 {required_points} 积分。")
        elif not prompt_txt and menu == "✍️ 文生图": st.error("❌ 请输入提示词！")
        else:
            final_ratio = custom_size if aspect_ratio == "自定义像素" else aspect_ratio
            payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
            
            if menu == "🖼️ 图生图":
                urls = []
                if uploaded_files:
                    for f in uploaded_files: urls.append(pil_to_data_uri(Image.open(io.BytesIO(f.getvalue()))))
                elif canvas_result and canvas_result.image_data is not None:
                    urls.append(pil_to_data_uri(Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')))
                
                if not urls: st.error("⚠️ 请提供参考图。"); st.stop()
                payload["urls"] = urls
            else:
                payload["aspectRatio"] = final_ratio
                payload["quality"] = quality

            headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
            try:
                sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                if sub_res.get("code") == 0:
                    # 🌟 提交时将选择的模型记入队列
                    add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": datetime.now().strftime("%H:%M"), "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model}, user_key)
                    st.success("🎉 任务已提交！")
                    time.sleep(1); st.rerun()
                else: st.error(f"失败：{sub_res.get('msg')}")
            except: st.error("网络异常")

with col_history:
    st.markdown("### 🗂️ 创作记录")
    tasks_list = clean_and_get_tasks(user_key)
    if not tasks_list: st.caption("暂无记录。")
    else:
        with st.container(height=700):
            for item in reversed(tasks_list):
                # 1. 模型标识
                model_used_badge = "👑 VIP" if item.get('model') == 'gpt-image-2-vip' else "普"
                
                # 2. 提示词截断处理 (超过10个字加省略号)
                prompt_text = item.get('prompt', '')
                short_prompt = prompt_text[:10] + "..." if len(prompt_text) > 10 else prompt_text
                
                # 3. 完美排版：时间 + 模型 + 短提示词
                st.markdown(f"**[{item['time_str']}]** `{model_used_badge}` 💡 {short_prompt}")
                
                # 4. 隐藏式一键复制折叠面板 (利用 st.code 自带的复制按钮)
                with st.expander("📋 展开复制完整提示词"):
                    st.code(prompt_text, language="text")

                if item.get('status') == 'running':
                    if st.button("🔍 查看进度", key=item['task_id'], use_container_width=True):
                        # 🌟 查看进度时，传入当时记录的模型参数
                        show_progress_dialog(item['task_id'], item['prompt'], user_key, item.get('model', 'gpt-image-2'))
                elif item.get('status') == 'succeeded':
                    for url in item.get('urls', []):
                        st.markdown(f'<a href="{url}" target="_blank"><img src="{url}" style="width:100%; border-radius:8px; cursor:zoom-in; transition: transform 0.2s; box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-bottom:8px;" onmouseover="this.style.transform=\'scale(1.02)\'" onmouseout="this.style.transform=\'scale(1)\'"></a>', unsafe_allow_html=True)
                elif item.get('status') == 'failed': 
                    st.error("❌ 生成失败")
                    
                st.divider()
