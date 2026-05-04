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
st.set_page_config(page_title="AI Pro Studio V6.33", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    
    .modal-checkbox { display: none !important; }
    .result-thumb {
        width: 100%; border-radius: 8px; cursor: zoom-in; 
        transition: transform 0.2s ease-in-out; 
        box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-bottom: 8px;
        display: block; opacity: 1 !important;
    }
    .result-thumb:hover { transform: scale(1.02); box-shadow: 0 6px 16px rgba(0,0,0,0.2); }
    .img-modal-overlay {
        display: none; position: fixed; z-index: 999999; top: 0; left: 0; 
        width: 100vw; height: 100vh; background-color: rgba(0,0,0,0.92); 
        align-items: center; justify-content: center; cursor: zoom-out; 
    }
    .modal-checkbox:checked + .img-modal-overlay { display: flex; }
    .img-modal-overlay img {
        max-width: 95vw; max-height: 95vh; border-radius: 12px; 
        box-shadow: 0 0 40px rgba(0,194,255,0.3); border: 1px solid rgba(0,194,255,0.2); object-fit: contain;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 常量与数据库初始化
# ==========================================
MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}
ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2", "自定义像素"]
quality_opts = ["auto", "high", "medium", "low"]
BJ_TZ = pytz.timezone('Asia/Shanghai')

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("❌ 数据库连接失败。")
    st.stop()

# --- 核心：云端历史记录 (最多拉取30条) ---
def fetch_tasks_from_db(card_key):
    try:
        res = supabase.table("tasks").select("*").eq("card_key", card_key).order("timestamp", desc=True).limit(30).execute()
        return res.data if res.data else []
    except: return []

def sync_task_to_db(task_data, card_key):
    try:
        task_data["card_key"] = card_key
        supabase.table("tasks").upsert(task_data, on_conflict="task_id").execute()
        # 自动删除超过 30 条的老数据
        all_res = supabase.table("tasks").select("id").eq("card_key", card_key).order("timestamp", desc=True).execute()
        if len(all_res.data) > 30:
            old_ids = [r['id'] for r in all_res.data[30:]]
            supabase.table("tasks").delete().in_("id", old_ids).execute()
    except Exception as e: print(e)

def clear_history_db(card_key):
    try:
        supabase.table("tasks").delete().eq("card_key", card_key).execute()
        return True
    except: return False

# --- 核心：提示词模板库 ---
def fetch_templates(card_key):
    try:
        res = supabase.table("prompt_templates").select("*").eq("card_key", card_key).order("created_at", desc=True).execute()
        return res.data if res.data else []
    except: return []

def add_template(card_key, name, content, is_shortcut):
    try: supabase.table("prompt_templates").insert({"card_key": card_key, "name": name, "content": content, "is_shortcut": is_shortcut}).execute()
    except: pass

def delete_template(temp_id):
    try: supabase.table("prompt_templates").delete().eq("id", temp_id).execute()
    except: pass

# --- 基础工具 ---
def get_card_info(card_key):
    try:
        res = supabase.table("user_cards").select("*").eq("card_key", card_key).eq("is_active", True).execute()
        if res.data: return res.data[0]
    except: pass
    return None

def deduct_balance(card_key, amount):
    try:
        res = supabase.table("user_cards").select("used_points, final_points").eq("card_key", card_key).execute()
        if res.data:
            new_used = res.data[0]['used_points'] + amount
            new_final = res.data[0]['final_points'] - amount
            supabase.table("user_cards").update({"used_points": new_used, "final_points": new_final}).eq("card_key", card_key).execute()
    except: pass

def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

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
# 2. 身份验证 (恢复经典布局)
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
current_balance = card_info.get('final_points', 0)
total_pts = card_info.get('total_points', 0)
used_pts = card_info.get('used_points', 0)
clean_api_name = (card_info.get('api_secret_name') or "API_VIP888").strip("'").strip()
GRSAI_API_KEY = st.secrets.get(clean_api_name, "")

# ==========================================
# 3. 自动轮询 
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    
    for i in range(60):
        p = min(5 + int(time.time() - start_time), 95)
        placeholder.markdown(f'<div style="background:#111;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00c2ff,#00ffd5);width:{p}%;"></div></div><div style="text-align:right;color:#00ffd5;font-size:12px;margin-top:4px;">⚡ 生成中... {p}%</div>', unsafe_allow_html=True)
        try:
            resp = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False, timeout=15)
            q_res = parse_api_response(resp.text) 
            if q_res:
                status, urls = "", []
                if q_res.get("code") == 0 and "data" in q_res:
                    status = q_res["data"].get("status")
                    urls = [img.get("url") for img in q_res["data"].get("results", []) if img.get("url")]
                elif "status" in q_res:
                    status = q_res.get("status")
                    urls = [img.get("url") for img in q_res.get("results", []) if img.get("url")] if "results" in q_res else ([q_res.get("url")] if q_res.get("url") else [])

                if status == "succeeded" and urls:
                    placeholder.markdown(f'<div style="background:#111;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00ff88,#00c2ff);width:100%;"></div></div><div style="text-align:right;color:#00ff88;font-size:12px;margin-top:4px;">✅ 绘制完成！</div>', unsafe_allow_html=True)
                    deduct_balance(active_user_key, MODEL_COSTS.get(model_used, 600))
                    sync_task_to_db({"task_id": task_id, "status": "succeeded", "urls": [urls[0]], "is_deducted": True}, active_user_key)
                    time.sleep(1.5); st.rerun(); return 
                elif status == "failed":
                    sync_task_to_db({"task_id": task_id, "status": "failed"}, active_user_key)
                    st.rerun(); return
        except Exception as e: pass
        time.sleep(3)

# ==========================================
# 4. 主界面
# ==========================================
# 🌟 恢复最高级的 HTML 积分侧边栏卡片！
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
    
    # 🌟 新增：快捷提示词模板按键
    if "current_prompt" not in st.session_state: 
        st.session_state.current_prompt = ""
        
    all_temps = fetch_templates(user_key)
    shortcuts = [t for t in all_temps if t['is_shortcut']]
    if shortcuts:
        st.caption("✨ 快捷描述词模板")
        s_cols = st.columns(min(len(shortcuts), 5))
        for i, s_item in enumerate(shortcuts):
            if s_cols[i % 5].button(f"📌 {s_item['name']}", key=f"s_{s_item['id']}", use_container_width=True):
                st.session_state.current_prompt = s_item['content']
                st.rerun()

    upload_zoom_container = st.empty()
    
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("画面描述", value=st.session_state.current_prompt, height=120)
    else:
        st.markdown("#### 🖼️ 图生图")
        uploaded_files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        
        if uploaded_files:
            p_cols = st.columns(6) 
            for i, file in enumerate(uploaded_files):
                img_bytes = file.getvalue()
                data_uri = pil_to_data_uri(Image.open(io.BytesIO(img_bytes)))
                zoom_id = f"zm_up_{i}" 
                with p_cols[i % 6]:
                    st.markdown(f'''
                        <label for="{zoom_id}">
                            <img src="{data_uri}" class="result-thumb" style="width:100%; border-radius:8px; cursor:zoom-in;">
                            <div style="text-align:center; font-size:11px; color:#aaa; margin-top:2px;">图 {i+1}</div>
                        </label>
                        <input type="checkbox" id="{zoom_id}" class="modal-checkbox">
                        <label for="{zoom_id}" class="img-modal-overlay">
                            <img src="{data_uri}">
                        </label>
                    ''', unsafe_allow_html=True)
        
        canvas_result = None
        if not uploaded_files:
            canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", height=300, key="cvs")
            
        prompt_txt = st.text_area("垫图指令", value=st.session_state.current_prompt, height=80)
        
    # 防止用户手动修改后被按钮覆盖
    if prompt_txt != st.session_state.current_prompt:
        st.session_state.current_prompt = prompt_txt

    c1, c2 = st.columns(2)
    with c1: 
        aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts, key=f"r_{menu}")
        custom_size = st.text_input("自定义像素 (WxH)", key=f"c_{menu}") if aspect_ratio == "自定义像素" else ""
    with c2: quality = st.selectbox("💎 图片质量", quality_opts, key=f"q_{menu}")
    
    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        if card_info['final_points'] < 600: 
            st.error("❌ 积分不足")
        elif not prompt_txt and menu == "✍️ 文生图": 
            st.error("❌ 请输入描述词")
        else:
            with st.spinner("🚀 正在注入云端算力..."):
                try:
                    final_ratio = custom_size if (menu == "✍️ 文生图" and aspect_ratio == "自定义像素") else (aspect_ratio if menu == "✍️ 文生图" else "auto")
                    payload = {
                        "model": selected_model, 
                        "prompt": prompt_txt, 
                        "webHook": "-1", 
                        "shutProgress": True,
                        "aspectRatio": final_ratio,
                        "quality": quality if menu == "✍️ 文生图" else "auto"
                    }
                    
                    if menu == "🖼️ 图生图":
                        if not uploaded_files: 
                            st.error("⚠️ 请先上传参考图"); st.stop()
                        try:
                            payload["urls"] = [pil_to_data_uri(Image.open(io.BytesIO(f.getvalue()))) for f in uploaded_files]
                        except Exception as img_err:
                            st.error(f"❌ 图片处理失败: {str(img_err)}"); st.stop()
                    
                    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
                    response = requests.post(
                        "https://grsai.dakka.com.cn/v1/draw/completions", 
                        headers=headers, json=payload, verify=False, timeout=30
                    )
                    
                    if response.status_code == 200:
                        api_res = parse_api_response(response.text)
                        task_id = api_res.get("data", {}).get("id") if api_res and api_res.get("code") == 0 else api_res.get("id") if api_res else None
                        
                        if task_id:
                            bj_now = datetime.now(BJ_TZ).strftime("%H:%M")
                            new_task = {"task_id": task_id, "timestamp": time.time(), "time_str": bj_now, "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model}
                            sync_task_to_db(new_task, user_key)
                            st.rerun() 
                        else:
                            st.error(f"❌ API未返回有效ID: {response.text[:100]}")
                    else:
                        st.error(f"📡 API 服务器报错: {response.text[:100]}")
                        
                except Exception as global_err:
                    st.error(f"💥 提交发生致命错误: {str(global_err)}")

    st.divider()
    # 🌟 新增：提示词库管理功能区 (隐藏在手风琴里，保持主界面清爽)
    with st.expander("📚 提示词库管理与自定义模板"):
        t_c1, t_c2 = st.columns([1, 2])
        with t_c1:
            new_t_name = st.text_input("模板名称", placeholder="如：爆款分镜描述")
            new_t_shortcut = st.checkbox("添加到上方快捷按钮")
        with t_c2:
            new_t_content = st.text_area("模板内容", placeholder="输入详细的提示词...")
        if st.button("💾 保存模板"):
            if new_t_name and new_t_content:
                add_template(user_key, new_t_name, new_t_content, new_t_shortcut)
                st.success("已保存！"); time.sleep(0.5); st.rerun()
        
        st.markdown("---")
        if not all_temps: st.caption("暂无模板。")
        else:
            for t in all_temps:
                tc1, tc2, tc3 = st.columns([2, 5, 1])
                tc1.write(f"**{t['name']}**" + (" (📌)" if t['is_shortcut'] else ""))
                tc2.caption(t['content'][:30] + "...")
                if tc3.button("🗑️", key=f"del_{t['id']}", help="删除模板"):
                    delete_template(t['id']); st.rerun()

with col_history:
    # 🌟 顶部增加一键清空按钮
    c_hist, c_clear = st.columns([3, 1])
    with c_hist: st.markdown("### 🗂️ 创作记录")
    with c_clear: 
        if st.button("🗑️ 清空", help="清空所有历史"):
            if clear_history_db(user_key): st.rerun()
            
    tasks_list = fetch_tasks_from_db(user_key)
    
    if not tasks_list:
        st.info("暂无记录")
    else:
        total_len = len(tasks_list)
        with st.container(height=700):
            for idx, item in enumerate(tasks_list):
                display_idx = total_len - idx
                m_badge = "👑 VIP" if item.get('model') == 'gpt-image-2-vip' else "普"
                st.markdown(f"**[{display_idx}]** **[{item['time_str']}]** `{m_badge}` 💡 {item['prompt'][:10]}...")
                with st.expander("📋 完整提示词"): st.code(item['prompt'], language="text")
                
                if item['status'] == 'running':
                    auto_poll_task(item['task_id'], user_key, item.get('model','gpt-image-2'), item['timestamp'])
                elif item['status'] == 'succeeded':
                    urls = item.get('urls', [])
                    imgs_html = ""
                    for i, url in enumerate(urls):
                        modal_id = f"cb_{str(item['task_id']).replace('-','')}_{i}"
                        imgs_html += f'<label for="{modal_id}"><img src="{url}" class="result-thumb"></label><input type="checkbox" id="{modal_id}" class="modal-checkbox"><label for="{modal_id}" class="img-modal-overlay"><img src="{url}"></label>'
                    st.markdown(imgs_html, unsafe_allow_html=True)
                elif item['status'] == 'failed': 
                    st.error(f"❌ 失败/未通过审查")
                st.divider()
