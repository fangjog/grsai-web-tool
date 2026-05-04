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
import pytz # 确保 requirements.txt 里有这一行

# ==========================================
# 0. 网页基础配置与防抖 CSS
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.15", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    /* 彻底防止右侧记录区抖动 */
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    
    /* HTML 模态框核心 CSS - 紧凑版 */
    .result-thumb {
        width: 100%; border-radius: 8px; cursor: zoom-in; 
        transition: transform 0.2s; box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-top: 10px;
    }
    .img-modal-overlay {
        display: none; position: fixed; z-index: 99999; top: 0; left: 0; 
        width: 100%; height: 100%; background-color: rgba(0,0,0,0.9); 
        align-items: center; justify-content: center; cursor: zoom-out;
    }
    .img-modal-overlay:target { display: flex; opacity: 1; }
    .img-modal-overlay img { max-width: 95%; max-height: 95%; border-radius: 12px; box-shadow: 0 0 30px rgba(0,194,255,0.3); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 数据库与工具函数
# ==========================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("❌ 数据库连接失败")
    st.stop()

# 🌟 全局时区设置
BJ_TZ = pytz.timezone('Asia/Shanghai')

def get_now_str():
    return datetime.now(BJ_TZ).strftime("%H:%M")

MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}
TASKS_FILE = "tasks_history.json"

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
        return res.data[0] if res.data else None
    except: return None

def deduct_balance(card_key, amount):
    try:
        res = supabase.table("user_cards").select("used_points, final_points").eq("card_key", card_key).execute()
        if res.data:
            u, f = res.data[0]['used_points'], res.data[0]['final_points']
            supabase.table("user_cards").update({"used_points": u + amount, "final_points": f - amount}).eq("card_key", card_key).execute()
    except: pass

# ==========================================
# 2. 身份验证
# ==========================================
user_key = st.query_params.get("key", "")
card_info = get_card_info(user_key)

if not card_info:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align:center;'>🚀 AI Pro Studio</h2>", unsafe_allow_html=True)
        key_input = st.text_input("输入激活码", type="password")
        if st.button("进入系统", use_container_width=True):
            if get_card_info(key_input.strip()):
                st.query_params["key"] = key_input.strip()
                st.rerun()
            else: st.error("无效激活码")
    st.stop()

current_balance = card_info.get('final_points', 0)
clean_api_name = (card_info.get('api_secret_name') or "API_VIP888").strip("'").strip()
GRSAI_API_KEY = st.secrets.get(clean_api_name, "")

# ==========================================
# 3. 轮询函数 (修复代码块 & 瞬间显示)
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    
    for i in range(60):
        p = min(5 + int(time.time() - start_time), 95)
        # 稳健的进度条渲染
        placeholder.markdown(f'<div style="background:#1a1a1a;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00c2ff,#00ffd5);width:{p}%;"></div></div><div style="text-align:right;color:#00ffd5;font-size:12px;margin-top:4px;">⚡ 注入中... {p}%</div>', unsafe_allow_html=True)
        
        try:
            q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
            if q_res.get("code") == 0:
                status = q_res["data"]["status"]
                if status == "succeeded":
                    urls = [img["url"] for img in q_res["data"]["results"]]
                    # 🌟 成功后：直接使用 placeholder.container 杜绝源码泄露
                    with placeholder.container():
                        st.markdown(f'<div style="background:#1a1a1a;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00ff88,#00c2ff);width:100%;"></div></div><div style="text-align:right;color:#00ff88;font-size:12px;margin-top:4px;">✅ 绘制完成！</div>', unsafe_allow_html=True)
                        for idx, url in enumerate(urls):
                            m_id = f"m_p_{task_id[:8]}_{idx}"
                            st.markdown(f'<a href="#{m_id}"><img src="{url}" class="result-thumb" style="border:2px solid #00ff88;"></a><a href="#!" class="img-modal-overlay" id="{m_id}"><img src="{url}"></a>', unsafe_allow_html=True)
                    
                    # 扣费与记录
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id and not t.get('is_deducted'):
                            deduct_balance(active_user_key, len(urls) * MODEL_COSTS.get(model_used, 600))
                            t.update({"status": "succeeded", "urls": urls, "is_deducted": True})
                    
                    save_json(TASKS_FILE, {active_user_key: st.session_state.tasks})
                    time.sleep(2)
                    st.rerun()
                    return
                elif status == "failed":
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id: t.update({"status": "failed", "reason": "生成失败或触发审查"})
                    st.rerun()
        except: pass
        time.sleep(3)

# ==========================================
# 4. 主界面
# ==========================================
st.sidebar.markdown(f"### 👤 `{user_key}`")
st.sidebar.markdown(f"**可用余额: {current_balance}**")
if st.sidebar.button("退出登录"): st.query_params.clear(); st.rerun()
st.sidebar.divider()
menu = st.sidebar.radio("导航", ["文生图", "图生图"])

col_main, col_history = st.columns([7, 3])

with col_main:
    selected_model = st.selectbox("模型", ["gpt-image-2", "gpt-image-2-vip"])
    prompt = st.text_area("提示词", height=150)
    
    # 统一参数面板
    c1, c2 = st.columns(2)
    with c1: ratio = st.selectbox("比例", ["auto","1:1","16:9","9:16","3:4","4:3"])
    with c2: quality = st.selectbox("质量", ["auto","high","medium"])
    
    if st.button("✨ 开始生成", type="primary", use_container_width=True):
        if current_balance < 600: st.error("积分不足")
        else:
            payload = {"model": selected_model, "prompt": prompt, "aspectRatio": ratio, "quality": quality, "shutProgress": True}
            try:
                res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers={"Authorization": f"Bearer {GRSAI_API_KEY}"}, json=payload, verify=False).json()
                if res.get("code") == 0:
                    # 🌟 关键：创建时立即记录北京时间
                    new_task = {"task_id": res["data"]["id"], "timestamp": time.time(), "time_str": get_now_str(), "prompt": prompt, "status": "running", "urls": [], "model": selected_model, "is_deducted": False}
                    if 'tasks' not in st.session_state: st.session_state.tasks = []
                    st.session_state.tasks.append(new_task)
                    save_json(TASKS_FILE, {user_key: st.session_state.tasks})
                    st.success("🎉 已提交"); time.sleep(0.5); st.rerun()
            except: st.error("📡 网络异常")

with col_history:
    st.markdown("### 🗂️ 创作记录")
    if 'tasks' not in st.session_state: st.session_state.tasks = load_json(TASKS_FILE).get(user_key, [])
    
    for item in reversed(st.session_state.tasks[-10:]):
        st.markdown(f"**[{item['time_str']}]** `{item['model'][-3:]}` 💡 {item['prompt'][:10]}...")
        if item['status'] == 'running':
            auto_poll_task(item['task_id'], user_key, item['model'], item['timestamp'])
        elif item['status'] == 'succeeded':
            for idx, url in enumerate(item['urls']):
                m_id = f"m_h_{item['task_id'][:8]}_{idx}"
                st.markdown(f'<a href="#{m_id}"><img src="{url}" class="result-thumb"></a><a href="#!" class="img-modal-overlay" id="{m_id}"><img src="{url}"></a>', unsafe_allow_html=True)
        st.divider()
