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
st.set_page_config(page_title="AI Pro Studio V6.6", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

# 🌟 全新的 CSS 赛博朋克模态框全屏放大系统
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
    
    /* 1. 缩略图样式 & 悬浮特效 */
    .result-thumb {
        width: 100%; border-radius: 8px; cursor: zoom-in; 
        transition: transform 0.2s ease-in-out; 
        box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-bottom: 8px;
    }
    .result-thumb:hover { transform: scale(1.02); }

    /* 2. 模态框（遮罩层）样式 */
    .img-modal-overlay {
        display: none; position: fixed; z-index: 99999; top: 0; left: 0; 
        width: 100%; height: 100%; background-color: rgba(0,0,0,0.9); 
        align-items: center; justify-content: center; opacity: 0; transition: opacity 0.3s;
        cursor: zoom-out; /* 点击空白处关闭 */
    }
    /* 模态框激活时的状态（利用 :target 伪类实现零 JS 点击） */
    .img-modal-overlay:target { display: flex; opacity: 1; }

    /* 3. 模态框内的大图样式 - 赛博朋克光晕 */
    .img-modal-overlay img {
        max-width: 90%; max-height: 90%; border-radius: 12px; 
        box-shadow: 0 0 30px rgba(0,194,255,0.4); 
        border: 2px solid rgba(0,194,255,0.2); 
        cursor: zoom-out; /* 点击图片关闭 */
    }
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
# 自动轮询与炫酷动态充电条 (已整合新图片预览)
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    cost_per_img = MODEL_COSTS.get(model_used, 600)
    
    for i in range(40):
        elapsed_time = time.time() - start_time
        p = min(5 + int(elapsed_time), 95) 
        
        html_bar = f"""<div style="background-color: #1a1a1a; border-radius: 10px; padding: 4px; box-shadow: inset 0 1px 3px rgba(0,0,0,0.5); border: 1px solid #333;"><div style="height: 14px; border-radius: 6px; background: linear-gradient(90deg, #00c2ff, #00ffd5); width: {p}%; transition: width 0.5s ease-in-out; box-shadow: 0 0 10px #00ffd5;"></div></div><div style="text-align: right; color: #00ffd5; font-size: 13px; font-weight: bold; margin-top: 6px; font-family: monospace;">⚡ 云端算力注入中... {p}%</div>"""
        
        placeholder.markdown(html_bar, unsafe_allow_html=True)
        
        try:
            q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
            if q_res.get("code") == 0:
                status = q_res["data"]["status"]
                if status == "succeeded":
                    results = q_res["data"]["results"]
                    urls = [img["url"] for img in results]
                    
                    # 生成瞬间加载时的 HTML
                    imgs_html = "".join([f'<img src="{url}" class="result-thumb" style="border: 2px solid #00ff88; box-shadow: 0 0 20px rgba(0,255,136,0.2);">' for url in urls])
                    full_bar = f"""<div style="background-color: #1a1a1a; border-radius: 10px; padding: 4px; border: 1px solid #333;"><div style="height: 14px; border-radius: 6px; background: linear-gradient(90deg, #00ff88, #00c2ff); width: 100%; box-shadow: 0 0 10px #00ff88;"></div></div><div style="text-align: right; color: #00ff88; font-size: 13px; font-weight: bold; margin-top: 6px; font-family: monospace;">✅ 绘制完成！</div>{imgs_html}"""
                    placeholder.markdown(full_bar, unsafe_allow_html=True)
                    
                    num_images = len(results)
                    total_cost = num_images * cost_per_img
                    deduct_balance(active_user_key, total_cost)
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            t['status'] = 'succeeded'
                            t['urls'] = urls
                    clean_and_get_tasks(active_user_key)
                    
                    time.sleep(1.5)
                    st.rerun()
                    return 
                    
                elif status == "failed":
                    raw_reason = q_res["data"].get("failure_reason", "")
                    raw_error = q_res["data"].get("error", "")
                    actual_err = raw_error if raw_error and raw_error != "error" else raw_reason
                    
                    error_dict = {
                        "The current model has a high load, please use another model": "当前模型并发排队拥挤，请稍后再试，或切换至 VIP 模型",
                        "We are sorry, but the images we created may have violated our relevant policies. If you think we made a mistake, please try again or edit your prompt.": "❌ 触发安全审查：生成的内容疑似包含违禁元素，请修改提示词后重试",
                        "error": "云端生成异常或触发安全审查，请调整提示词"
                    }
                    cn_error = error_dict.get(actual_err, f"系统异常: {actual_err}")
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id: 
                            t['status'] = 'failed'
                            t['reason'] = cn_error
                    clean_and_get_tasks(active_user_key)
                    st.rerun()
        except: pass
        time.sleep(3)
        
    for t in st.session_state.tasks:
        if t['task_id'] == task_id and t['status'] == 'running':
            t['status'] = 'failed'
            t['reason'] = "请求超时，请检查网络或稍后重试"
    clean_and_get_tasks(active_user_key)
    st.rerun()

# ==========================================
# 4. 主界面
# ==========================================
st.sidebar.markdown(f'### 👤 用户中心\n当前用户: `{user_key}`')
st.sidebar.markdown(f'剩余积分: <span style="color:#00c2ff; font-weight:bold; font-size:24px;">{current_balance}</span>', unsafe_allow_html=True)
st.sidebar.markdown(f'<div style="font-size:13px; color:#666;">标准模式约可制 <b style="color:#333;">{current_balance//600}
