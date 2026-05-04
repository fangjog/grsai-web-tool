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
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    
    /* 🌟 HTML 模态框核心 CSS (Checkbox Hack) */
    .modal-checkbox { display: none !important; }
    .result-thumb {
        width: 100%; border-radius: 8px; cursor: zoom-in; 
        transition: transform 0.2s ease-in-out; 
        box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-bottom: 8px;
        display: block; opacity: 1 !important;
    }
    .result-thumb:hover { transform: scale(1.02); }
    .img-modal-overlay {
        display: none; position: fixed; z-index: 999999; top: 0; left: 0; 
        width: 100vw; height: 100vh; background-color: rgba(0,0,0,0.92); 
        align-items: center; justify-content: center; cursor: zoom-out; 
    }
    .modal-checkbox:checked + .img-modal-overlay { display: flex; }
    .img-modal-overlay img { max-width: 95vw; max-height: 95vh; border-radius: 12px; object-fit: contain; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 数据库配置 (云端同步)
# ==========================================
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("❌ 数据库连接失败"); st.stop()

BJ_TZ = pytz.timezone('Asia/Shanghai')
MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}

# 🌟 从 Supabase 获取云端历史 (解决多电脑同步问题)
def fetch_tasks_from_db(card_key):
    try:
        res = supabase.table("tasks").select("*").eq("card_key", card_key).order("timestamp", desc=True).limit(10).execute()
        return res.data if res.data else []
    except: return []

# 🌟 同步任务状态到云端
def sync_task_to_db(task_data, card_key):
    try:
        task_data["card_key"] = card_key
        # 使用 upsert：根据 task_id 存在则更新，不存在则新增
        supabase.table("tasks").upsert(task_data, on_conflict="task_id").execute()
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
            u, f = info['used_points'] + amount, info['final_points'] - amount
            supabase.table("user_cards").update({"used_points": u, "final_points": f}).eq("card_key", card_key).execute()
    except: pass

# ==========================================
# 2. 身份验证
# ==========================================
user_key = st.query_params.get("key", "")
card_info = get_card_info(user_key) if user_key else None

if not card_info:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align:center;'>🚀 AI Pro Studio</h1>", unsafe_allow_html=True)
        u_in = st.text_input("🔑 输入激活码解锁创作台", type="password")
        if st.button("立即进入 ✨", type="primary", use_container_width=True):
            if get_card_info(u_in.strip()):
                st.query_params["key"] = u_in.strip(); st.rerun()
            else: st.error("激活码无效")
    st.stop()

GRSAI_API_KEY = st.secrets.get((card_info.get('api_secret_name') or "API_VIP888").strip("'").strip(), "")

# ==========================================
# 3. 任务与轮询 (同步至云端版)
# ==========================================
def pil_to_data_uri(img):
    buf = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)); img.save(buf, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

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
                    # 🌟 成功后同步云端状态
                    sync_task_to_db({"task_id": task_id, "status": "succeeded", "urls": urls, "is_deducted": True}, active_user_key)
                    placeholder.success("🎉 绘制完成！"); time.sleep(1.5); st.rerun(); return
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
if st.sidebar.button("🚪 退出登录"): st.query_params.clear(); st.rerun()

menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图"])

col_main, col_history = st.columns([7, 3])

with col_main:
    selected_model = st.selectbox("🤖 模型选择", ["gpt-image-2", "gpt-image-2-vip"])
    
    if menu == "🖼️ 图生图":
        files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if files:
            # 🌟 修复关键：采用分段渲染杜绝 HTML 代码漏出
            p_cols = st.columns(6)
            for i, f in enumerate(files):
                img_bytes = f.getvalue()
                data_uri = pil_to_data_uri(Image.open(io.BytesIO(img_bytes)))
                zm_id = f"zm_up_{i}"
                with p_cols[i % 6]:
                    # 渲染缩略图和隐藏的放大逻辑
                    st.markdown(f'''
                        <label for="{zm_id}"><img src="{data_uri}" class="result-thumb"><div style="text-align:center; font-size:11px; color:#aaa;">图 {i+1}</div></label>
                        <input type="checkbox" id="{zm_id}" class="modal-checkbox">
                        <label for="{zm_id}" class="img-modal-overlay"><img src="{data_uri}"></label>
                    ''', unsafe_allow_html=True)
        prompt_txt = st.text_area("修改指令", height=100)
    else:
        prompt_txt = st.text_area("画面描述", height=150)

    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        if card_info['final_points'] < 600: st.error("❌ 积分不足")
        elif not prompt_txt: st.error("❌ 请输入提示词")
        else:
            payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
            if menu == "🖼️ 图生图" and files:
                payload["urls"] = [pil_to_data_uri(Image.open(f)) for f in files]
            
            try:
                res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers={"Authorization": f"Bearer {GRSAI_API_KEY}"}, json=payload, verify=False).json()
                if res.get("code") == 0:
                    bj_now = datetime.now(BJ_TZ).strftime("%H:%M")
                    # 🌟 初始任务即刻同步到云端数据库 (解决同步问题)
                    sync_task_to_db({
                        "task_id": res["data"]["id"], "timestamp": time.time(), 
                        "time_str": bj_now, "prompt": prompt_txt, 
                        "status": "running", "urls": [], "model": selected_model
                    }, user_key)
                    st.rerun()
            except: st.error("📡 网络异常")

with col_history:
    st.markdown("### 🗂️ 创作记录 (云端同步)")
    # 🌟 直接从数据库拉取，保证电脑 A/B 同步
    tasks_list = fetch_tasks_from_db(user_key)
    total_len = len(tasks_list)
    
    for idx, item in enumerate(tasks_list):
        display_idx = total_len - idx
        st.markdown(f"**[{display_idx}]** **[{item['time_str']}]** `{item['model'][-3:]}` 💡 {item['prompt'][:10]}...")
        
        if item['status'] == 'running':
            auto_poll_task(item['task_id'], user_key, item['model'], item['timestamp'])
        elif item['status'] == 'succeeded' and item['urls']:
            url = item['urls'][0]
            safe_id = item['task_id'].replace("-","")
            # 渲染历史记录图片及放大
            st.markdown(f'''
                <label for="z_{safe_id}"><img src="{url}" class="result-thumb"></label>
                <input type="checkbox" id="z_{safe_id}" class="modal-checkbox">
                <label for="z_{safe_id}" class="img-modal-overlay"><img src="{url}"></label>
            ''', unsafe_allow_html=True)
        elif item['status'] == 'failed': st.error("❌ 失败")
        st.divider()
