# 文件名: app.py
import streamlit as st
import streamlit.components.v1 as components
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
import urllib3
import warnings

# 🌟 绝杀烦人的日志警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*st.components.v1.html.*")

# ==========================================
# 0. 网页基础配置与全局 CSS
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.67", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    button[title="View fullscreen"] { display: none !important; }
    
    .thumb-img { border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); width: 100%; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 常量与数据库配置
# ==========================================
MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}
ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2"]
pixel_opts = ["默认", "1k", "2k", "4k", "自定义"]
quality_opts = ["auto", "high", "medium", "low"]
BJ_TZ = pytz.timezone('Asia/Shanghai')

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("❌ 数据库连接失败。")
    st.stop()

@st.cache_data(show_spinner=False, max_entries=20)
def process_cached_data_uri(img_bytes):
    img = Image.open(io.BytesIO(img_bytes))
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=82, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

def fetch_tasks_from_db(card_key):
    try:
        res = supabase.table("tasks").select("*").eq("card_key", card_key).order("timestamp", desc=True).limit(30).execute()
        return res.data if res.data else []
    except: return []

def sync_task_to_db(task_data, card_key):
    try:
        task_data["card_key"] = card_key
        supabase.table("tasks").upsert(task_data, on_conflict="task_id").execute()
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

def toggle_template_shortcut(temp_id, current_status):
    try: supabase.table("prompt_templates").update({"is_shortcut": not current_status}).eq("id", temp_id).execute()
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
# 2. 核心：独立沙盒查阅引擎 (解决按钮没反应的问题)
# ==========================================
@st.dialog("🔍 图像细节查阅台", width="large")
def show_viewer_dialog(after_url, before_url=None):
    is_dual = before_url is not None
    panels_html = ""
    if is_dual:
        panels_html += f'<div class="panel left"><img class="sync-img" src="{before_url}" draggable="false"><div class="label">📤 原图 (Before)</div></div>'
    panels_html += f'<div class="panel"><img class="sync-img" src="{after_url}" draggable="false"><div class="label">✨ 成品 (After)</div></div>'

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ margin: 0; padding: 0; background: #0e1117; color: white; font-family: sans-serif; overflow: hidden; user-select: none; }}
            .toolbar {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #262730; border-bottom: 1px solid #444; }}
            .btn-group {{ display: flex; gap: 10px; }}
            .btn {{ background: #00ffd5; color: black; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 14px; transition: 0.2s; }}
            .btn:hover {{ background: #00c2ff; transform: scale(1.05); }}
            .viewer {{ display: flex; width: 100vw; height: calc(100vh - 60px); }}
            .panel {{ flex: 1; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; }}
            .panel.left {{ border-right: 2px solid #555; }}
            .panel img {{ max-width: 100%; max-height: 100%; cursor: zoom-in; transform-origin: 0 0; will-change: transform; }}
            .label {{ position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); padding: 8px 20px; border-radius: 20px; border: 1px solid #555; pointer-events: none; font-weight: bold; letter-spacing: 1px; }}
        </style>
    </head>
    <body>
        <div class="toolbar">
            <span style="font-size: 14px; color: #ccc;">💡 <b>点击图片</b>一键放大，<b>滚动轮</b>无极缩放，按住可随意拖拽。</span>
            <div class="btn-group">
                <button class="btn" onclick="zoomBtn(1.3)">➕ 放大</button>
                <button class="btn" onclick="zoomBtn(0.7)">➖ 缩小</button>
                <button class="btn" onclick="resetView()" style="background: #444; color: white;">🔄 还原</button>
            </div>
        </div>
        <div class="viewer" id="container">
            {panels_html}
        </div>

        <script>
            let scale = 1; let pointX = 0, pointY = 0; let start = {{ x: 0, y: 0 }}; 
            let isPanning = false; let hasMoved = false;
            const container = document.getElementById('container');
            const images = document.querySelectorAll('.sync-img');

            function setTransform(animated = false) {{
                images.forEach(img => {{
                    img.style.transition = animated ? 'transform 0.2s ease-out' : 'none';
                    img.style.transform = `translate(${{pointX}}px, ${{pointY}}px) scale(${{scale}})`;
                    img.style.cursor = scale > 1 ? (isPanning ? 'grabbing' : 'grab') : 'zoom-in';
                }});
            }}

            container.onmousedown = (e) => {{
                if (e.target.tagName !== 'IMG') return;
                e.preventDefault();
                start = {{ x: e.clientX - pointX, y: e.clientY - pointY }};
                isPanning = true; hasMoved = false;
                images.forEach(img => img.style.cursor = 'grabbing');
            }};

            window.onmousemove = (e) => {{
                if (!isPanning) return;
                hasMoved = true;
                pointX = e.clientX - start.x; pointY = e.clientY - start.y;
                setTransform(false);
            }};

            window.onmouseup = (e) => {{
                if (!isPanning) return;
                isPanning = false;
                if (!hasMoved) {{
                    const rect = e.target.getBoundingClientRect();
                    const mouseX = e.clientX - rect.left;
                    const mouseY = e.clientY - rect.top;
                    const xs = mouseX / scale;
                    const ys = mouseY / scale;
                    if (scale === 1) {{ scale = 2.5; pointX += xs * (1 - scale); pointY += ys * (1 - scale); }}
                    else {{ scale = 1; pointX = 0; pointY = 0; }}
                    setTransform(true);
                }} else {{
                    images.forEach(img => img.style.cursor = scale > 1 ? 'grab' : 'zoom-in');
                }}
            }};

            container.onwheel = (e) => {{
                e.preventDefault();
                const rect = images[0].getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                const xs = mouseX / scale;
                const ys = mouseY / scale;
                const delta = e.deltaY > 0 ? 0.85 : 1.15;
                let newScale = scale * delta;
                if (newScale <= 1) {{ scale = 1; pointX = 0; pointY = 0; }}
                else if (newScale > 20) newScale = 20;
                else {{
                    pointX += xs * (scale - newScale);
                    pointY += ys * (scale - newScale);
                    scale = newScale;
                }}
                setTransform(false);
            }};

            function zoomBtn(factor) {{
                const cx = container.clientWidth / 2;
                const cy = container.clientHeight / 2;
                const xs = (cx - pointX) / scale;
                const ys = (cy - pointY) / scale;
                let newScale = scale * factor;
                if (newScale < 1) {{ resetView(); return; }}
                if (newScale > 20) newScale = 20;
                pointX += xs * (scale - newScale);
                pointY += ys * (scale - newScale);
                scale = newScale;
                setTransform(true);
            }}

            function resetView() {{ scale = 1; pointX = 0; pointY = 0; setTransform(true); }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=750, scrolling=False)

# ==========================================
# 3. 身份验证与登录
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
# 4. 自动轮询 
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time, src_urls=None):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    
    for i in range(300):
        p = min(5 + int((time.time() - start_time) * 0.2), 98) 
        placeholder.markdown(f'<div style="background:#111;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00c2ff,#00ffd5);width:{p}%;"></div></div><div style="text-align:right;color:#00ffd5;font-size:12px;margin-top:4px;">⚡ 正在排队/生成中... {p}% (耗时较长请耐心等待)</div>', unsafe_allow_html=True)
        try:
            resp = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False, timeout=10)
            q_res = parse_api_response(resp.text) 
            if q_res and isinstance(q_res, dict):
                status = str(q_res.get("status", "")).lower()
                if "data" in q_res and isinstance(q_res["data"], dict):
                    status = str(q_res["data"].get("status", "")).lower()
                if str(q_res.get("code", "0")) != "0" and status not in ["running", "in_progress", "submitted"]:
                    status = "failed"

                if status in ["succeeded", "success"]:
                    deduct_balance(active_user_key, MODEL_COSTS.get(model_used, 600))
                    st.rerun(); return 
                elif status in ["failed", "fail", "error"]:
                    sync_task_to_db({"task_id": task_id, "status": "failed"}, active_user_key)
                    st.rerun(); return
        except Exception as e: pass
        time.sleep(3)

# ==========================================
# 5. 主界面布局
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
    
    if "current_prompt" not in st.session_state: st.session_state.current_prompt = ""
    all_temps = fetch_templates(user_key)
    shortcuts = [t for t in all_temps if t['is_shortcut']]
    
    if shortcuts:
        st.caption("✨ 快捷描述词模板")
        s_cols = st.columns(min(len(shortcuts), 5))
        for i, s_item in enumerate(shortcuts):
            if s_cols[i % 5].button(f"📌 {s_item['name']}", key=f"s_{s_item['id']}", use_container_width=True):
                st.session_state.current_prompt = s_item['content']; st.rerun()

    uploaded_b64_urls = [] 
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("画面描述", value=st.session_state.current_prompt, height=120)
    else:
        st.markdown("#### 🖼️ 图生图")
        uploaded_files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if uploaded_files:
            up_cols = st.columns(6)
            for i, file in enumerate(uploaded_files):
                uri = process_cached_data_uri(file.getvalue())
                uploaded_b64_urls.append(uri)
                up_cols[i % 6].image(uri, caption=f"图 {i+1}")
        prompt_txt = st.text_area("垫图指令", value=st.session_state.current_prompt, height=80)
        
    c1, c2, c3 = st.columns(3)
    with c1: aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts, key=f"r_{menu}")
    with c2: pixel_res = st.selectbox("🗜️ 像素精度", pixel_opts, key=f"px_{menu}")
    with c3: quality = st.selectbox("💎 图片质量", quality_opts, key=f"q_{menu}")

    custom_size = st.text_input("输入自定义像素 (例如: 1024x1024)", key=f"c_{menu}") if pixel_res == "自定义" else ""
    
    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        if card_info['final_points'] < 600: st.error("❌ 积分不足")
        elif not prompt_txt and menu == "✍️ 文生图": st.error("❌ 请输入描述词")
        else:
            with st.spinner("🚀 打包云端数据..."):
                try:
                    final_ratio = "auto"
                    if menu == "✍️ 文生图":
                        if pixel_res == "自定义" and custom_size: final_ratio = custom_size.strip()
                        elif pixel_res == "默认": final_ratio = aspect_ratio
                        else:
                            m = {"1k": 1, "2k": 2, "4k": 4}.get(pixel_res, 1)
                            if aspect_ratio == "auto": final_ratio = f"{1024*m}x{1024*m}"
                            else:
                                w_r, h_r = map(float, aspect_ratio.split(":"))
                                w = 1792 * m if w_r > h_r else 1024 * m
                                h = 1024 * m if w_r > h_r else 1792 * m
                                if w_r == h_r: w, h = 1024*m, 1024*m
                                final_ratio = f"{w}x{h}"
                    
                    payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True, "aspectRatio": final_ratio, "quality": quality if menu == "✍️ 文生图" else "auto"}
                    if menu == "🖼️ 图生图": payload["urls"] = uploaded_b64_urls 
                    
                    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
                    resp = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False, timeout=30)
                    if resp.status_code == 200:
                        api_res = parse_api_response(resp.text)
                        tid = api_res.get("data", {}).get("id") if api_res and api_res.get("code") == 0 else api_res.get("id") if api_res else None
                        if tid:
                            sync_task_to_db({"task_id": tid, "timestamp": time.time(), "time_str": datetime.now(BJ_TZ).strftime("%H:%M"), "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model, "src_urls": uploaded_b64_urls if menu=="🖼️ 图生图" else None}, user_key)
                            st.rerun() 
                    else: st.error("📡 API 服务器连接失败")
                except Exception as e: st.error(f"💥 错误: {str(e)}")

    with st.expander("📚 提示词模板管理"):
        tc1, tc2 = st.columns([1, 2])
        with tc1:
            name = st.text_input("模板名称")
            pin = st.checkbox("固定到快捷栏")
        with tc2: content = st.text_area("内容")
        if st.button("💾 保存"):
            if name and content: add_template(user_key, name, content, pin); st.rerun()
        if all_temps:
            st.divider()
            for t in all_temps:
                c_1, c_2, c_3, c_4 = st.columns([2, 4, 1.5, 1])
                c_1.write(f"**{t['name']}**")
                c_2.caption(t['content'][:30])
                if c_3.button("📍 固定" if not t['is_shortcut'] else "📌 取消", key=f"p_{t['id']}"): toggle_template_shortcut(t['id'], t['is_shortcut']); st.rerun()
                if c_4.button("🗑️", key=f"d_{t['id']}"): delete_template(t['id']); st.rerun()

with col_history:
    st.markdown("### 🗂️ 创作记录")
    if st.button("🗑️ 清空历史", use_container_width=True):
        if clear_history_db(user_key): st.rerun()
    
    tasks = fetch_tasks_from_db(user_key)
    if not tasks: st.info("暂无记录")
    else:
        with st.container(height=700):
            for item in tasks:
                st.markdown(f"**[{item['time_str']}]** `{item.get('model','')[:5]}` 💡 {item['prompt'][:12]}...")
                if item['status'] == 'running':
                    auto_poll_task(item['task_id'], user_key, item.get('model','gpt-image-2'), item['timestamp'], item.get('src_urls'))
                elif item['status'] == 'succeeded':
                    urls = item.get('urls', [])
                    srcs = item.get('src_urls', [])
                    for i, url in enumerate(urls):
                        st.image(url, use_container_width=True)
                        b1, b2 = st.columns(2)
                        # 🌟 统一使用 st.dialog 查阅台，确保缩放按钮 100% 有效
                        if b1.button("🔍 细节放大", key=f"z_{item['task_id']}_{i}", use_container_width=True):
                            show_viewer_dialog(url)
                        if srcs and i < len(srcs):
                            if b2.button("🪟 同步对比", key=f"c_{item['task_id']}_{i}", use_container_width=True):
                                show_viewer_dialog(url, srcs[i])
                elif item['status'] == 'failed': st.error("❌ 尺寸错误或生成失败")
                st.divider()
