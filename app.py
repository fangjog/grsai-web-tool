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
# 0. 网页基础配置与全局 CSS
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.27", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    /* 基础优化：防止区域抖动 */
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    
    /* 🌟 HTML 模态框核心 CSS (Checkbox Hack) - 无缝放大无跳转 */
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
    
    /* 关键：Checkbox 被选中时，显示模态框 */
    .modal-checkbox:checked + .img-modal-overlay { display: flex; }
    
    .img-modal-overlay img {
        max-width: 95vw; max-height: 95vh; border-radius: 12px; 
        box-shadow: 0 0 40px rgba(0,194,255,0.3); border: 1px solid rgba(0,194,255,0.2); 
        object-fit: contain;
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
    if isinstance(global_history, list): global_history = {}
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
# 自动轮询 (修复代码块输出 & 中国时区同步)
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    cost_per_img = MODEL_COSTS.get(model_used, 600)
    
    for i in range(40):
        elapsed_time = time.time() - start_time
        p = min(5 + int(elapsed_time), 95) 
        html_bar = f'<div style="background-color: #1a1a1a; border-radius: 10px; padding: 4px; border: 1px solid #333;"><div style="height: 14px; border-radius: 6px; background: linear-gradient(90deg, #00c2ff, #00ffd5); width: {p}%; transition: width 0.5s ease-in-out; box-shadow: 0 0 10px #00ffd5;"></div></div><div style="text-align: right; color: #00ffd5; font-size: 13px; font-weight: bold; margin-top: 6px; font-family: monospace;">⚡ 云端算力注入中... {p}%</div>'
        placeholder.markdown(html_bar, unsafe_allow_html=True)
        
        try:
            q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
            if q_res.get("code") == 0:
                status = q_res["data"]["status"]
                if status == "succeeded":
                    results = q_res["data"]["results"]
                    urls = [img["url"] for img in results]
                    
                    imgs_html = ""
                    for idx, url in enumerate(urls):
                        modal_id = f"cb_{str(task_id).replace('-','')}_{idx}"
                        imgs_html += f'<label for="{modal_id}"><img src="{url}" class="result-thumb" style="border: 2px solid #00ff88; box-shadow: 0 0 20px rgba(0,255,136,0.2); margin-top: 10px;"></label><input type="checkbox" id="{modal_id}" class="modal-checkbox"><label for="{modal_id}" class="img-modal-overlay"><img src="{url}"></label>'
                    
                    full_bar = f'<div style="background-color: #1a1a1a; border-radius: 10px; padding: 4px; border: 1px solid #333;"><div style="height: 14px; border-radius: 6px; background: linear-gradient(90deg, #00ff88, #00c2ff); width: 100%; box-shadow: 0 0 10px #00ff88;"></div></div><div style="text-align: right; color: #00ff88; font-size: 13px; font-weight: bold; margin-top: 6px; font-family: monospace;">✅ 绘制完成！</div>{imgs_html}'
                    placeholder.markdown(full_bar, unsafe_allow_html=True)
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            deduct_balance(active_user_key, len(results) * cost_per_img)
                            t.update({"status": "succeeded", "urls": urls})
                    
                    clean_and_get_tasks(active_user_key); time.sleep(1.5); st.rerun(); return 
                elif status == "failed":
                    error_dict = {
                        "The current model has a high load, please use another model": "当前模型并发拥挤，请稍后再试",
                        "error": "触发安全审查：请修改提示词或更换垫图"
                    }
                    cn_error = error_dict.get(q_res["data"].get("failure_reason", q_res["data"].get("error")), f"系统异常: {q_res['data'].get('error')}")
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id: t.update({"status": "failed", "reason": cn_error})
                    clean_and_get_tasks(active_user_key); st.rerun(); return
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
    
    # 🌟 统一放大模态框容器（放在主界面底部，防止抖动）
    upload_zoom_container = st.empty()
    
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("画面描述", height=120)
    else:
        st.markdown("#### 🖼️ 图生图")
        uploaded_files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        
        preview_html = ""
        zoom_html_modals = ""
        
        if uploaded_files:
            # 🌟 核心修复：直接使用 st.columns 在循环中分段渲染，杜绝源码泄露
            p_cols = st.columns(6) 
            for i, file in enumerate(uploaded_files):
                img_bytes = file.getvalue()
                data_uri = pil_to_data_uri(Image.open(io.BytesIO(img_bytes)))
                zoom_id = f"zm_up_{i}" # 唯一锚点 ID
                
                with p_cols[i % 6]:
                    # 每一张图都是一个独立的独立 HTML 块，压力极小，100% 渲染成功
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
                
            # 渲染缩略图预览
            st.markdown(f'<div style="margin-top:10px;">{preview_html}</div>', unsafe_allow_html=True)
            # 渲染隐藏的模态框代码
            upload_zoom_container.markdown(zoom_html_modals, unsafe_allow_html=True)
        
        canvas_result = None
        if not uploaded_files:
            canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", height=300, key="cvs")
            
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
            final_ratio = custom_size if aspect_ratio == "自定义像素" else aspect_ratio
            payload = {"model": selected_model, "prompt": prompt_txt, "aspectRatio": final_ratio, "quality": quality, "webHook": "-1", "shutProgress": True}
            
            if menu == "🖼️ 图生图":
                urls = []
                if uploaded_files:
                    for f in uploaded_files: urls.append(pil_to_data_uri(Image.open(io.BytesIO(f.getvalue()))))
                elif canvas_result:
                    urls.append(pil_to_data_uri(Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')))
                
                if not urls: st.error("⚠️ 请提供参考图。"); st.stop()
                payload["urls"] = urls
            
            headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
            
            sub_res = None
            try:
                sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
            except Exception as e:
                st.error("📡 网络超时或异常")
                
            if sub_res:
                if sub_res.get("code") == 0:
                    tz = pytz.timezone('Asia/Shanghai') # 🌟 锁定中国时区存储
                    china_now = datetime.now(tz)
                    tasks_list = st.session_state.tasks
                    tasks_list.append({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": china_now.strftime("%H:%M"), "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model})
                    st.session_state.tasks = tasks_list
                    clean_and_get_tasks(user_key)
                    st.success("🎉 已提交"); time.sleep(0.5); st.rerun()
                else: 
                    st.error(f"❌ 失败：{sub_res.get('msg')}")

with col_history:
    st.markdown("### 🗂️ 创作记录")
    tasks_list = clean_and_get_tasks(user_key)
    with st.container(height=700):
        for item in reversed(tasks_list):
            m_badge = "👑 VIP" if item.get('model') == 'gpt-image-2-vip' else "普"
            st.markdown(f"**[{item['time_str']}]** `{m_badge}` 💡 {item['prompt'][:10]}...")
            with st.expander("📋 完整提示词"): st.code(item['prompt'], language="text")
            
            if item['status'] == 'running':
                auto_poll_task(item['task_id'], user_key, item.get('model','gpt-image-2'), item['timestamp'])
            elif item['status'] == 'succeeded':
                urls = item.get('urls', [])
                imgs_html = ""
                for idx, url in enumerate(urls):
                    modal_id = f"cb_{str(item['task_id']).replace('-','')}_{idx}"
                    # 🌟 使用Checkbox Hack实现历史图片丝滑放大
                    imgs_html += f'<label for="{modal_id}"><img src="{url}" class="result-thumb"></label><input type="checkbox" id="{modal_id}" class="modal-checkbox"><label for="{modal_id}" class="img-modal-overlay"><img src="{url}"></label>'
                st.markdown(imgs_html, unsafe_allow_html=True)
            elif item['status'] == 'failed': 
                st.error(f"❌ {item.get('reason', '触发安全审查')}")
            st.divider()
