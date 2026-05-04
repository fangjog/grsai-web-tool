# 文件名: app.py
import streamlit as st
import requests
import time
from PIL import Image
import io
import base64
from datetime import datetime, timedelta
import json
import os
from streamlit_drawable_canvas import st_canvas
from supabase import create_client, Client
import pytz # 请确保 requirements.txt 里有 pytz

# ==========================================
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.14", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

# 🌟 全球最稳 CSS：修复抖动、修复放大、修复圆角
st.markdown("""
<style>
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.5rem !important; }
        h1 { font-size: 24px !important; }
        .stButton > button { width: 100% !important; padding: 15px !important; font-size: 16px !important; border-radius: 12px !important; }
    }
    /* 彻底防止右侧记录区抖动 */
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    
    /* HTML 模态框核心 CSS */
    .result-thumb {
        width: 100%; border-radius: 8px; cursor: zoom-in; 
        transition: transform 0.2s ease-in-out; 
        box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-bottom: 8px;
    }
    .result-thumb:hover { transform: scale(1.02); box-shadow: 0 6px 16px rgba(0,0,0,0.2); }
    .img-modal-overlay {
        display: none; position: fixed; z-index: 99999; top: 0; left: 0; 
        width: 100%; height: 100%; background-color: rgba(0,0,0,0.95); 
        align-items: center; justify-content: center; opacity: 0; transition: opacity 0.3s;
        cursor: zoom-out; text-decoration: none !important;
    }
    .img-modal-overlay:target { display: flex; opacity: 1; }
    .img-modal-overlay img {
        max-width: 95%; max-height: 95%; border-radius: 12px; 
        box-shadow: 0 0 40px rgba(0,194,255,0.3); border: 1px solid rgba(0,194,255,0.2); 
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
    st.error("❌ 数据库连接失败。")
    st.stop()

MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}
TASKS_FILE = "tasks_history.json"
ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2", "自定义像素"]
quality_opts = ["auto", "high", "medium", "low"]

def load_json(path, default=None):
    if default is None: default = {}
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

# 🌟 修复版扣费：认准 final_points
def deduct_balance(card_key, amount):
    try:
        res = supabase.table("user_cards").select("used_points, final_points").eq("card_key", card_key).execute()
        if res.data:
            new_used = res.data[0]['used_points'] + amount
            new_final = res.data[0]['final_points'] - amount
            supabase.table("user_cards").update({"used_points": new_used, "final_points": new_final}).eq("card_key", card_key).execute()
    except: pass

# ==========================================
# 2. 身份验证
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
            if get_card_info(user_key):
                st.query_params["key"] = user_key
                st.rerun()
            else: st.error("❌ 激活码无效。")
    st.stop() 

user_key = query_key
# 🌟 读取 final_points 为准
current_balance = card_info.get('final_points', 0)
total_pts = card_info.get('total_points', 0)
used_pts = card_info.get('used_points', 0)
clean_api_name = (card_info.get('api_secret_name') or "API_VIP888").strip("'").strip()
GRSAI_API_KEY = st.secrets.get(clean_api_name, "")

# ==========================================
# 3. 任务队列
# ==========================================
all_history = load_json(TASKS_FILE, default={})
if isinstance(all_history, list): all_history = {}
if 'tasks' not in st.session_state: st.session_state.tasks = all_history.get(user_key, [])

def clean_and_get_tasks(active_key):
    curr_time = time.time()
    valid = [t for t in st.session_state.tasks if (curr_time - t['timestamp']) < 3600]
    st.session_state.tasks = valid[-10:]
    global_history = load_json(TASKS_FILE, default={})
    global_history[active_key] = st.session_state.tasks
    save_json(TASKS_FILE, global_history)
    return st.session_state.tasks

def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

# ==========================================
# 自动轮询 (修复代码块输出 & 瞬间放大)
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    cost_per_img = MODEL_COSTS.get(model_used, 600)
    
    for i in range(40):
        elapsed_time = time.time() - start_time
        p = min(5 + int(elapsed_time), 95) 
        # 🌟 修复：紧凑 HTML 防止被识别为代码块
        html_bar = f'<div style="background-color: #1a1a1a; border-radius: 10px; padding: 4px; border: 1px solid #333;"><div style="height: 14px; border-radius: 6px; background: linear-gradient(90deg, #00c2ff, #00ffd5); width: {p}%; transition: width 0.5s ease-in-out; box-shadow: 0 0 10px #00ffd5;"></div></div><div style="text-align: right; color: #00ffd5; font-size: 13px; font-weight: bold; margin-top: 6px; font-family: monospace;">⚡ 云端算力注入中... {p}%</div>'
        placeholder.markdown(html_bar, unsafe_allow_html=True)
        
        try:
            q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
            if q_res.get("code") == 0:
                status = q_res["data"]["status"]
                if status == "succeeded":
                    results = q_res["data"]["results"]
                    urls = [img["url"] for img in results]
                    
                    # 生成充满状态 + 图片 HTML (紧凑版)
                    imgs_html = ""
                    for idx, url in enumerate(urls):
                        m_id = f"modal_p_{task_id}_{idx}"
                        imgs_html += f'<a href="#{m_id}"><img src="{url}" class="result-thumb" style="border: 2px solid #00ff88; margin-top:10px;"></a><a href="#!" class="img-modal-overlay" id="{m_id}"><img src="{url}"></a>'
                    
                    full_bar = f'<div style="background-color: #1a1a1a; border-radius: 10px; padding: 4px; border: 1px solid #333;"><div style="height: 14px; border-radius: 6px; background: linear-gradient(90deg, #00ff88, #00c2ff); width: 100%; box-shadow: 0 0 10px #00ff88;"></div></div><div style="text-align: right; color: #00ff88; font-size: 13px; font-weight: bold; margin-top: 6px;">✅ 绘制完成！</div>{imgs_html}'
                    placeholder.markdown(full_bar, unsafe_allow_html=True)
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id and not t.get('is_deducted'):
                            deduct_balance(active_user_key, len(results) * cost_per_img)
                            t.update({"status": "succeeded", "urls": urls, "is_deducted": True})
                    
                    clean_and_get_tasks(active_user_key)
                    time.sleep(1.5)
                    st.rerun()
                    return 
                elif status == "failed":
                    err = q_res["data"].get("error", q_res["data"].get("failure_reason", "未知错误"))
                    error_dict = {
                        "The current model has a high load, please use another model": "当前模型并发拥挤，请稍后再试",
                        "We are sorry, but the images we created may have violated our relevant policies...": "❌ 触发安全审查：请修改提示词"
                    }
                    cn_err = error_dict.get(err, f"系统异常: {err}")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id: t.update({"status": "failed", "reason": cn_err})
                    clean_and_get_tasks(active_user_key); st.rerun()
        except: pass
        time.sleep(3)
    st.rerun()

# ==========================================
# 4. 主界面
# ==========================================
st.sidebar.markdown(f'### 👤 用户中心\n`{user_key}`')
st.sidebar.markdown(f"""
<div style="background-color: #1e1e1e; padding: 15px; border-radius: 12px; border: 1px solid #333;">
    <div style="color: #888; font-size: 13px;">获取总额: {total_pts}</div>
    <div style="color: #ff4b4b; font-size: 13px;">累计消耗: -{used_pts}</div>
    <div style="margin-top: 10px; border-top: 1px dashed #444; padding-top: 10px;">
        <div style="color: #00ffd5; font-size: 28px; font-weight: bold;">{current_balance}</div>
    </div>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("🚪 退出登录", use_container_width=True):
    st.query_params.clear(); st.rerun()
    
st.sidebar.divider()
menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图"])

st.title("🚀 AI Pro Studio")
col_main, col_history = st.columns([7, 3])

with col_main:
    selected_model = st.selectbox("🤖 模型选择", ["gpt-image-2", "gpt-image-2-vip"])
    
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("画面描述", height=120)
    else:
        st.markdown("#### 🖼️ 图生图")
        files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if files:
            cols = st.columns(6)
            for i, f in enumerate(files): cols[i%6].image(Image.open(f), use_container_width=True)
        canvas_result = None
        if not files: canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", height=300, key="cvs")
        prompt_txt = st.text_area("垫图指令", height=80)

    # 统一参数面板
    c1, c2 = st.columns(2)
    with c1: 
        aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts, key=f"r_{menu}")
        custom_size = st.text_input("自定义像素 (WxH)", key=f"c_{menu}") if aspect_ratio == "自定义像素" else ""
    with c2: quality = st.selectbox("💎 图片质量", quality_opts, key=f"q_{menu}")
    
    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        cost = MODEL_COSTS.get(selected_model, 600)
        if current_balance < cost: st.error("❌ 积分不足")
        elif not prompt_txt and menu == "✍️ 文生图": st.error("❌ 请输入提示词")
        else:
            # 🌟 核心修复：时区锁定中国时间
            tz = pytz.timezone('Asia/Shanghai')
            china_now = datetime.now(tz)
            
            payload = {"model": selected_model, "prompt": prompt_txt, "aspectRatio": custom_size or aspect_ratio, "quality": quality, "shutProgress": True}
            if menu == "🖼️ 图生图":
                urls = [pil_to_data_uri(Image.open(f)) for f in files] if files else [pil_to_data_uri(Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA'))] if canvas_result else []
                payload["urls"] = urls
            
            try:
                res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers={"Authorization": f"Bearer {GRSAI_API_KEY}"}, json=payload, verify=False).json()
                if res.get("code") == 0:
                    st.session_state.tasks.append({"task_id": res["data"]["id"], "timestamp": time.time(), "time_str": china_now.strftime("%H:%M"), "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model, "is_deducted": False})
                    save_json(TASKS_FILE, {user_key: st.session_state.tasks})
                    st.success("🎉 已提交，请查看右侧进度"); time.sleep(0.5); st.rerun()
                else: st.error(f"❌ 失败: {res.get('msg')}")
            except: st.error("📡 网络异常")

with col_history:
    st.markdown("### 🗂️ 创作记录")
    tasks_list = clean_and_get_tasks(user_key)
    with st.container(height=700):
        for item in reversed(tasks_list):
            m_badge = "👑 VIP" if item.get('model') == 'gpt-image-2-vip' else "普"
            st.markdown(f"**[{item['time_str']}]** `{m_badge}` 💡 {item['prompt'][:10]}...")
            with st.expander("📋 完整提示词"): st.code(item['prompt'], language="text")
            
            if item['status'] == 'running':
                auto_poll_task(item['task_id'], user_key, item['model'], item['timestamp'])
            elif item['status'] == 'succeeded':
                for idx, url in enumerate(item['urls']):
                    m_id = f"m_h_{item['task_id']}_{idx}"
                    st.markdown(f'<a href="#{m_id}"><img src="{url}" class="result-thumb"></a><a href="#!" class="img-modal-overlay" id="{m_id}"><img src="{url}"></a>', unsafe_allow_html=True)
            elif item['status'] == 'failed': st.error(f"❌ {item.get('reason', '生成失败')}")
            st.divider()
