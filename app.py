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
# 0. 网页基础配置与全局 CSS
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.29", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

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
        box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-top: 10px; display: block;
    }
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
# 1. 数据库逻辑 (全云端同步版)
# ==========================================
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except Exception as e:
    st.error(f"❌ 数据库配置异常: {e}"); st.stop()

BJ_TZ = pytz.timezone('Asia/Shanghai')
MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}

def fetch_tasks_from_db(card_key):
    try:
        res = supabase.table("tasks").select("*").eq("card_key", card_key).order("timestamp", desc=True).limit(10).execute()
        return res.data if res.data else []
    except Exception as e:
        st.sidebar.error(f"同步记录失败: {e}")
        return []

def sync_task_to_db(task_data, card_key):
    try:
        task_data["card_key"] = card_key
        supabase.table("tasks").upsert(task_data, on_conflict="task_id").execute()
    except Exception as e:
        st.error(f"数据库写入失败: {e}")

def get_card_info(card_key):
    try:
        res = supabase.table("user_cards").select("*").eq("card_key", card_key).execute()
        return res.data[0] if res.data else None
    except: return None

def deduct_balance(card_key, amount):
    try:
        info = get_card_info(card_key)
        if info:
            new_u, new_f = (info.get('used_points', 0) + amount), (info.get('final_points', 0) - amount)
            supabase.table("user_cards").update({"used_points": new_u, "final_points": new_f}).eq("card_key", card_key).execute()
    except: pass

def pil_to_data_uri(img):
    buf = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)); img.save(buf, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

def parse_api_response(text):
    if not text: return None
    try: return json.loads(text)
    except:
        for line in text.split('\n'):
            if line.strip().startswith('data:'):
                try: return json.loads(line.strip()[5:])
                except: pass
    return None

# ==========================================
# 2. 身份验证
# ==========================================
user_key = st.query_params.get("key", "")
card_info = get_card_info(user_key) if user_key else None

if not card_info:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align:center;'>🚀 AI Pro Studio</h1>", unsafe_allow_html=True)
        u_in = st.text_input("🔑 输入激活码解锁", type="password")
        if st.button("进入创作空间 ✨", use_container_width=True):
            if get_card_info(u_in.strip()):
                st.query_params["key"] = u_in.strip(); st.rerun()
            else: st.error("激活码无效")
    st.stop()

GRSAI_API_KEY = st.secrets.get((card_info.get('api_secret_name') or "API_VIP888").strip("'").strip(), "")

# ==========================================
# 3. 异步轮询逻辑
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    for i in range(60):
        p = min(5 + int(time.time() - start_time), 95)
        placeholder.markdown(f'<div style="background:#111;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00c2ff,#00ffd5);width:{p}%;"></div></div><div style="text-align:right;color:#00ffd5;font-size:12px;margin-top:4px;">⚡ 生成中... {p}%</div>', unsafe_allow_html=True)
        try:
            resp = requests.post("https://grsai.dakka.com.cn/v1/draw/result", headers=headers, json={"id": task_id}, verify=False, timeout=15)
            q_res = parse_api_response(resp.text)
            if q_res:
                status, urls = "", []
                if q_res.get("code") == 0 and "data" in q_res:
                    status, urls = q_res["data"].get("status"), [img.get("url") for img in q_res["data"].get("results", []) if img.get("url")]
                elif "status" in q_res:
                    status = q_res.get("status")
                    urls = [img.get("url") for img in q_res.get("results", []) if img.get("url")] if "results" in q_res else ([q_res.get("url")] if q_res.get("url") else [])

                if status == "succeeded" and urls:
                    deduct_balance(active_user_key, MODEL_COSTS.get(model_used, 600))
                    sync_task_to_db({"task_id": task_id, "status": "succeeded", "urls": urls, "is_deducted": True}, active_user_key)
                    placeholder.success("✅ 绘制完成！"); time.sleep(1.5); st.rerun(); return
                elif status == "failed":
                    sync_task_to_db({"task_id": task_id, "status": "failed"}, active_user_key); st.rerun(); return
        except: pass
        time.sleep(3)

# ==========================================
# 4. 主界面
# ==========================================
st.sidebar.markdown(f"### 👤 用户: `{user_key}`")
st.sidebar.markdown(f"**可用余额: {card_info.get('final_points', 0)}**")
if st.sidebar.button("🚪 退出登录"): st.query_params.clear(); st.rerun()

menu = st.sidebar.radio("导航", ["✍️ 文生图", "🖼️ 图生图"])

col_main, col_history = st.columns([7, 3])

with col_main:
    selected_model = st.selectbox("🤖 模型选择", ["gpt-image-2", "gpt-image-2-vip"])
    if menu == "🖼️ 图生图":
        files = st.file_uploader("📤 上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if files:
            p_cols = st.columns(6)
            for i, f in enumerate(files):
                img_data = f.getvalue()
                data_uri = pil_to_data_uri(Image.open(io.BytesIO(img_data)))
                zm_id = f"zm_up_{i}"
                with p_cols[i % 6]:
                    st.markdown(f'''
                        <label for="{zm_id}"><img src="{data_uri}" class="result-thumb"><div style="text-align:center; font-size:11px; color:#aaa;">图 {i+1}</div></label>
                        <input type="checkbox" id="{zm_id}" class="modal-checkbox">
                        <label for="{zm_id}" class="img-modal-overlay"><img src="{data_uri}"></label>
                    ''', unsafe_allow_html=True)
        prompt_txt = st.text_area("修改指令", height=100)
    else:
        prompt_txt = st.text_area("画面描述", height=150)

    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        if card_info.get('final_points', 0) < 600: st.error("❌ 积分不足")
        elif not prompt_txt and menu == "✍️ 文生图": st.error("❌ 请输入提示词")
        else:
            with st.spinner("🚀 正在注入云端算力..."):
                try:
                    payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
                    if menu == "🖼️ 图生图" and files:
                        payload["urls"] = [pil_to_data_uri(Image.open(io.BytesIO(f.getvalue()))) for f in files]
                    
                    res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers={"Authorization": f"Bearer {GRSAI_API_KEY}"}, json=payload, verify=False, timeout=30)
                    api_res = parse_api_response(res.text)
                    task_id = api_res.get("data", {}).get("id") if api_res and api_res.get("code") == 0 else api_res.get("id") if api_res else None
                    
                    if task_id:
                        bj_now = datetime.now(BJ_TZ).strftime("%H:%M")
                        sync_task_to_db({"task_id": task_id, "timestamp": time.time(), "time_str": bj_now, "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model}, user_key)
                        st.rerun()
                    else:
                        st.error(f"❌ API未返回有效ID: {res.text[:150]}")
                except Exception as e:
                    st.error(f"📡 提交失败: {str(e)}")

with col_history:
    st.markdown("### 🗂️ 创作记录 (云端同步)")
    tasks_list = fetch_tasks_from_db(user_key)
    if not tasks_list:
        st.info("暂无历史记录")
    else:
        total_len = len(tasks_list)
        for idx, item in enumerate(tasks_list):
            with st.container():
                st.markdown(f"**[{total_len - idx}]** **[{item['time_str']}]** `{item['model'][-3:]}` 💡 {item['prompt'][:10]}...")
                if item['status'] == 'running':
                    auto_poll_task(item['task_id'], user_key, item['model'], item['timestamp'])
                elif item['status'] == 'succeeded' and item.get('urls'):
                    url = item['urls'][0]
                    safe_id = str(item['task_id']).replace("-","")
                    st.markdown(f'''
                        <label for="z_{safe_id}"><img src="{url}" class="result-thumb"></label>
                        <input type="checkbox" id="z_{safe_id}" class="modal-checkbox">
                        <label for="z_{safe_id}" class="img-modal-overlay"><img src="{url}"></label>
                    ''', unsafe_allow_html=True)
                elif item['status'] == 'failed': st.error("❌ 未通过内容审查")
                st.divider()
