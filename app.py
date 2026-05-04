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
import pytz 

# ==========================================
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.28", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    
    /* 放大模态框 CSS */
    .modal-checkbox { display: none !important; }
    .img-modal-overlay {
        display: none; position: fixed; z-index: 999999; top: 0; left: 0; 
        width: 100vw; height: 100vh; background-color: rgba(0,0,0,0.92); 
        align-items: center; justify-content: center; cursor: zoom-out; 
    }
    .modal-checkbox:checked + .img-modal-overlay { display: flex; }
    .img-modal-overlay img { max-width: 95vw; max-height: 95vh; border-radius: 12px; object-fit: contain; }
    
    /* 历史记录样式 */
    .task-card { border: 1px solid #333; background: #1e1e1e; padding: 12px; border-radius: 12px; margin-bottom: 15px; }
    .result-thumb { width: 100%; border-radius: 8px; cursor: zoom-in; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 数据库逻辑 (全云端同步)
# ==========================================
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("❌ 数据库连接失败"); st.stop()

BJ_TZ = pytz.timezone('Asia/Shanghai')
MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}

# 🌟 核心：从 Supabase 获取历史记录
def fetch_tasks_from_db(card_key):
    try:
        res = supabase.table("tasks").select("*").eq("card_key", card_key).order("created_at", desc=True).limit(10).execute()
        return res.data if res.data else []
    except: return []

# 🌟 核心：保存/更新记录到 Supabase
def sync_task_to_db(task_data, card_key):
    try:
        task_data["card_key"] = card_key
        # 检查是否已存在
        check = supabase.table("tasks").select("id").eq("task_id", task_data["task_id"]).execute()
        if check.data:
            supabase.table("tasks").update(task_data).eq("task_id", task_data["task_id"]).execute()
        else:
            supabase.table("tasks").insert(task_data).execute()
    except: pass

def get_card_info(card_key):
    try:
        res = supabase.table("user_cards").select("*").eq("card_key", card_key).execute()
        return res.data[0] if res.data else None
    except: return None

def deduct_balance(card_key, amount):
    try:
        info = get_card_info(card_key)
        if info:
            new_u, new_f = info['used_points'] + amount, info['final_points'] - amount
            supabase.table("user_cards").update({"used_points": new_u, "final_points": new_f}).eq("card_key", card_key).execute()
    except: pass

# ==========================================
# 2. 身份验证
# ==========================================
user_key = st.query_params.get("key", "")
card_info = get_card_info(user_key) if user_key else None

if not card_info:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🚀 AI Pro Studio")
        k_in = st.text_input("输入激活码", type="password")
        if st.button("进入系统", use_container_width=True):
            if get_card_info(k_in.strip()):
                st.query_params["key"] = k_in.strip(); st.rerun()
            else: st.error("激活码无效")
    st.stop()

GRSAI_API_KEY = st.secrets.get((card_info.get('api_secret_name') or "API_VIP888").strip("'").strip(), "")

# ==========================================
# 3. 轮询逻辑
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    
    for i in range(50):
        p = min(5 + int(time.time() - start_time), 95)
        placeholder.markdown(f'<div style="background:#111;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00c2ff,#00ffd5);width:{p}%;"></div></div><div style="text-align:right;color:#00ffd5;font-size:12px;margin-top:4px;">⚡ 生成中... {p}%</div>', unsafe_allow_html=True)
        
        try:
            resp = requests.post("https://grsai.dakka.com.cn/v1/draw/result", headers=headers, json={"id": task_id}, verify=False, timeout=15).json()
            if resp.get("code") == 0 and resp["data"]["status"] == "succeeded":
                urls = [img["url"] for img in resp["data"]["results"]]
                if urls:
                    deduct_balance(active_user_key, MODEL_COSTS.get(model_used, 600))
                    # 同步到数据库
                    sync_task_to_db({"task_id": task_id, "status": "succeeded", "urls": urls, "is_deducted": True}, active_user_key)
                    placeholder.success("🎉 绘制完成！")
                    time.sleep(1.5); st.rerun(); return
            elif resp.get("code") == 0 and resp["data"]["status"] == "failed":
                sync_task_to_db({"task_id": task_id, "status": "failed"}, active_user_key)
                st.rerun(); return
        except: pass
        time.sleep(3)

# ==========================================
# 4. 主界面
# ==========================================
st.sidebar.markdown(f"### 👤 用户: `{user_key}`")
st.sidebar.markdown(f"**可用余额: {card_info['final_points']}**")
if st.sidebar.button("退出登录"): st.query_params.clear(); st.rerun()

menu = st.sidebar.radio("导航", ["✍️ 文生图", "🖼️ 图生图"])

col_main, col_history = st.columns([7, 3])

with col_main:
    selected_model = st.selectbox("🤖 模型选择", ["gpt-image-2", "gpt-image-2-vip"])
    
    if menu == "🖼️ 图生图":
        files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if files:
            # 🌟 修复：使用 Streamlit 原生组件预览，解决“显示错误代码”问题
            cols = st.columns(5)
            for i, f in enumerate(files):
                img_data = f.getvalue()
                cols[i%5].image(img_data, caption=f"图{i+1}", use_container_width=True)
                # 隐藏的放大层 (仅在需要时通过 HTML 触发)
                b64 = base64.b64encode(img_data).decode()
                st.markdown(f'<input type="checkbox" id="zoom_{i}" class="modal-checkbox"><label for="zoom_{i}" class="img-modal-overlay"><img src="data:image/jpeg;base64,{b64}"></label>', unsafe_allow_html=True)
        
        prompt_txt = st.text_area("指令", height=100)
    else:
        prompt_txt = st.text_area("画面描述", height=150)

    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        if card_info['final_points'] < 600: st.error("积分不足")
        else:
            payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
            if menu == "🖼️ 图生图" and files:
                payload["urls"] = [f"data:image/jpeg;base64,{base64.b64encode(f.getvalue()).decode()}" for f in files]
            
            try:
                res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers={"Authorization": f"Bearer {GRSAI_API_KEY}"}, json=payload, verify=False).json()
                if res.get("code") == 0:
                    # 🌟 立即存入云端数据库
                    bj_now = datetime.now(BJ_TZ).strftime("%H:%M")
                    new_task = {"task_id": res["data"]["id"], "timestamp": time.time(), "time_str": bj_now, "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model}
                    sync_task_to_db(new_task, user_key)
                    st.rerun()
            except: st.error("网络异常")

with col_history:
    st.markdown("### 🗂️ 创作记录 (云端同步)")
    # 🌟 从云端读取最新记录
    tasks_list = fetch_tasks_from_db(user_key)
    
    for item in tasks_list:
        with st.container():
            st.markdown(f"**[{item['time_str']}]** `{item['model'][-3:]}` 💡 {item['prompt'][:10]}...")
            
            if item['status'] == 'running':
                auto_poll_task(item['task_id'], user_key, item['model'], item['timestamp'])
            elif item['status'] == 'succeeded' and item['urls']:
                url = item['urls'][0]
                safe_id = item['task_id'].replace("-","")
                # 渲染并提供放大功能
                st.markdown(f'''
                <label for="z_{safe_id}"><img src="{url}" class="result-thumb"></label>
                <input type="checkbox" id="z_{safe_id}" class="modal-checkbox">
                <label for="z_{safe_id}" class="img-modal-overlay"><img src="{url}"></label>
                ''', unsafe_allow_html=True)
            st.divider()
