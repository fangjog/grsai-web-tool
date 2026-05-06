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
st.set_page_config(page_title="AI Pro Studio V6.60", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    button[title="View fullscreen"] { display: none !important; }
    
    .my-thumb { width: 100%; border-radius: 8px; transition: transform 0.2s; box-shadow: 0 2px 6px rgba(0,0,0,0.1); display: block; }
    @media (hover: hover) { .my-thumb:hover { transform: scale(1.02); box-shadow: 0 6px 16px rgba(0,0,0,0.2); } }
    .my-cb { display: none !important; }
    .my-overlay { display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.92); z-index: 999999; align-items: center; justify-content: center; overflow: hidden; }
    .my-cb:checked ~ .my-overlay { display: flex !important; }
    .my-bg { position: absolute; top:0; left:0; width:100%; height:100%; cursor: zoom-out; z-index: 1; }
    .my-modal-img { position: relative; z-index: 10; max-width: 90vw; max-height: 90vh; border-radius: 8px; box-shadow: 0 0 50px rgba(0,0,0,0.8); object-fit: contain; transform-origin: 0 0; will-change: transform; cursor: grab; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 常量、数据库与缓存加速引擎
# ==========================================
MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}
ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2"]
pixel_opts = ["默认", "1k", "2k", "4k", "6k", "自定义"]
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
# 2. 高级同步对比台
# ==========================================
@st.dialog("🔍 高级同步对比台", width="large")
def show_viewer_dialog(before_url, after_url):
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
            .panel img {{ max-width: 100%; max-height: 100%; cursor: grab; transform-origin: 0 0; will-change: transform; }}
            .label {{ position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); padding: 8px 20px; border-radius: 20px; border: 1px solid #555; pointer-events: none; font-weight: bold; letter-spacing: 1px; }}
        </style>
    </head>
    <body>
        <div class="toolbar">
            <span style="font-size: 14px; color: #ccc;">💡 指哪打哪：在目标位置<b>滚动鼠标滚轮</b>，按住左键平移。双视角完全同步。</span>
            <div class="btn-group">
                <button class="btn" onclick="zoomBtn(1.25)">➕ 放大</button>
                <button class="btn" onclick="zoomBtn(0.8)">➖ 缩小</button>
                <button class="btn" onclick="resetView()" style="background: #444; color: white;">🔄 1:1 还原</button>
            </div>
        </div>
        <div class="viewer" id="container">
            <div class="panel left"><img class="sync-img" src="{before_url}" draggable="false"><div class="label">📤 原图 (Before)</div></div>
            <div class="panel"><img class="sync-img" src="{after_url}" draggable="false"><div class="label">✨ 成品 (After)</div></div>
        </div>

        <script>
            let scale = 1; let pointX = 0, pointY = 0; let start = {{ x: 0, y: 0 }}; let isPanning = false;
            const container = document.getElementById('container');
            const images = document.querySelectorAll('.sync-img');

            function setTransform(animated = false) {{
                images.forEach(img => {{
                    img.style.transition = animated ? 'transform 0.15s ease-out' : 'none';
                    img.style.transform = `translate(${{pointX}}px, ${{pointY}}px) scale(${{scale}})`;
                }});
            }}

            container.onmousedown = (e) => {{
                if (e.target.tagName !== 'IMG' && !e.target.classList.contains('panel')) return;
                e.preventDefault();
                start = {{ x: e.clientX - pointX, y: e.clientY - pointY }};
                isPanning = true;
                images.forEach(img => img.style.cursor = 'grabbing');
            }};

            window.onmouseup = () => {{ isPanning = false; images.forEach(img => img.style.cursor = 'grab'); }};
            window.onmousemove = (e) => {{
                if (!isPanning) return;
                pointX = e.clientX - start.x; pointY = e.clientY - start.y;
                setTransform(false);
            }};

            container.onwheel = (e) => {{
                e.preventDefault();
                const panel = e.target.closest('.panel');
                if (!panel) return;
                const targetImg = panel.querySelector('.sync-img');
                if (!targetImg) return;

                images.forEach(img => img.style.transition = 'none');
                const rect = targetImg.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                const xs = mouseX / scale;
                const ys = mouseY / scale;

                const delta = e.deltaY > 0 ? 0.85 : 1.15; 
                let newScale = scale * delta;
                if (newScale < 0.2) newScale = 0.2;
                if (newScale > 20) newScale = 20;

                pointX += xs * (scale - newScale);
                pointY += ys * (scale - newScale);

                scale = newScale;
                setTransform(false);
            }};

            function zoomBtn(factor) {{
                const targetImg = images[images.length - 1]; 
                if (!targetImg) return;
                const rect = targetImg.getBoundingClientRect();
                const panelRect = targetImg.parentElement.getBoundingClientRect();
                const cx = panelRect.left + panelRect.width / 2;
                const cy = panelRect.top + panelRect.height / 2;
                const mouseX = cx - rect.left;
                const mouseY = cy - rect.top;
                const xs = mouseX / scale;
                const ys = mouseY / scale;

                let newScale = scale * factor;
                if (newScale < 0.2) newScale = 0.2;
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
# 3. 身份验证
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
                status, urls = "", []
                
                if "data" in q_res and isinstance(q_res["data"], dict):
                    status = str(q_res["data"].get("status", "")).lower()
                    results_list = q_res["data"].get("results", [])
                    if isinstance(results_list, list):
                        urls = [img.get("url") for img in results_list if isinstance(img, dict) and img.get("url")]
                elif "status" in q_res:
                    status = str(q_res.get("status", "")).lower()
                    results_list = q_res.get("results", [])
                    if isinstance(results_list, list):
                        urls = [img.get("url") for img in results_list if isinstance(img, dict) and img.get("url")]
                    elif q_res.get("url"):
                        urls = [q_res.get("url")]
                
                if str(q_res.get("code", "0")) != "0" and status not in ["running", "in_progress", "submitted"]:
                    status = "failed"

                if status in ["succeeded", "success"] and urls:
                    placeholder.markdown(f'<div style="background:#111;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00ff88,#00c2ff);width:100%;"></div></div><div style="text-align:right;color:#00ff88;font-size:12px;margin-top:4px;">✅ 绘制完成！</div>', unsafe_allow_html=True)
                    deduct_balance(active_user_key, MODEL_COSTS.get(model_used, 600))
                    task_update = {"task_id": task_id, "status": "succeeded", "urls": [urls[0]], "is_deducted": True}
                    if src_urls: task_update["src_urls"] = src_urls 
                    sync_task_to_db(task_update, active_user_key)
                    time.sleep(1.0); st.rerun(); return 
                
                elif status in ["failed", "fail", "error", "timeout", "rejected"]:
                    sync_task_to_db({"task_id": task_id, "status": "failed"}, active_user_key)
                    st.rerun(); return
                    
        except Exception as e: pass
        time.sleep(3)

# ==========================================
# 5. 主界面
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
    
    def render_shortcut_buttons():
        if shortcuts:
            st.caption("✨ 快捷描述词模板")
            s_cols = st.columns(min(len(shortcuts), 5) if len(shortcuts) > 0 else 1)
            for i, s_item in enumerate(shortcuts):
                if s_cols[i % 5].button(f"📌 {s_item['name']}", key=f"s_{s_item['id']}", use_container_width=True):
                    st.session_state.current_prompt = s_item['content']
                    st.rerun()

    uploaded_b64_urls = [] 
    
    if menu == "✍️ 文生图":
        render_shortcut_buttons()
        prompt_txt = st.text_area("画面描述", value=st.session_state.current_prompt, height=120)
    else:
        st.markdown("#### 🖼️ 图生图")
        uploaded_files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        
        if uploaded_files:
            p_cols = st.columns(6) 
            for i, file in enumerate(uploaded_files):
                data_uri = process_cached_data_uri(file.getvalue())
                uploaded_b64_urls.append(data_uri) 
                zoom_id = f"zm_up_{i}" 
                with p_cols[i % 6]:
                    html_str = (
                        f'<div style="position:relative; margin-bottom:10px;">'
                        f'<label for="{zoom_id}" style="display:block; cursor:zoom-in;">'
                        f'<img src="{data_uri}" class="my-thumb">'
                        f'<div style="text-align:center;font-size:11px;color:#aaa;margin-top:4px;">图 {i+1} (点击放大)</div>'
                        f'</label>'
                        f'<input type="checkbox" id="{zoom_id}" class="my-cb">'
                        f'<div class="my-overlay">'
                        f'<label for="{zoom_id}" class="my-bg"></label>'
                        f'<div style="position:absolute; top:20px; color:#fff; background:rgba(0,0,0,0.6); padding:6px 16px; border-radius:20px; font-size:13px; pointer-events:none; z-index:20;">💡 点击图片 或 滚动滚轮 均可缩放，按住拖拽</div>'
                        f'<img src="{data_uri}" class="my-modal-img" draggable="false">'
                        f'</div>'
                        f'</div>'
                    )
                    st.markdown(html_str, unsafe_allow_html=True)
        
        canvas_result = None
        if not uploaded_files: canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", height=300, key="cvs")
        
        render_shortcut_buttons() 
        prompt_txt = st.text_area("垫图指令", value=st.session_state.current_prompt, height=80)
        
    if prompt_txt != st.session_state.current_prompt: st.session_state.current_prompt = prompt_txt

    c1, c2, c3 = st.columns(3)
    with c1: 
        aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts, key=f"r_{menu}")
    with c2: 
        pixel_res = st.selectbox("🗜️ 像素精度", pixel_opts, key=f"px_{menu}")
    with c3: 
        quality = st.selectbox("💎 图片质量", quality_opts, key=f"q_{menu}")

    custom_size = ""
    if pixel_res == "自定义":
        custom_size = st.text_input("输入自定义像素 (例如: 2560x1440)", key=f"c_{menu}")
    
    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        if card_info['final_points'] < 600: st.error("❌ 积分不足")
        elif not prompt_txt and menu == "✍️ 文生图": st.error("❌ 请输入描述词")
        else:
            with st.spinner("🚀 打包云端数据..."):
                try:
                    final_ratio = "auto"
                    
                    if menu == "✍️ 文生图":
                        if pixel_res == "自定义" and custom_size:
                            final_ratio = custom_size
                        elif pixel_res == "默认":
                            final_ratio = aspect_ratio
                        else:
                            # 🌟 核心修复：64 像素强制对齐引擎！
                            res_map = {"1k": 1024, "2k": 2048, "4k": 4096, "6k": 6144}
                            max_dim = res_map.get(pixel_res, 1024)
                            
                            if aspect_ratio == "auto":
                                final_ratio = f"{max_dim}x{max_dim}"
                            else:
                                try:
                                    w_r, h_r = map(float, aspect_ratio.split(":"))
                                    if w_r >= h_r:
                                        w = max_dim
                                        h = max_dim * (h_r / w_r)
                                    else:
                                        h = max_dim
                                        w = max_dim * (w_r / h_r)
                                    
                                    # 严密的 64 整数倍强制对齐算法
                                    w = int(max(64, round(w / 64) * 64))
                                    h = int(max(64, round(h / 64) * 64))
                                    
                                    final_ratio = f"{w}x{h}"
                                except:
                                    final_ratio = aspect_ratio
                    
                    payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True, "aspectRatio": final_ratio, "quality": quality if menu == "✍️ 文生图" else "auto"}
                    
                    if menu == "🖼️ 图生图":
                        if not uploaded_files: st.error("⚠️ 请先上传参考图"); st.stop()
                        payload["urls"] = uploaded_b64_urls 
                    
                    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
                    response = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False, timeout=30)
                    
                    if response.status_code == 200:
                        api_res = parse_api_response(response.text)
                        task_id = api_res.get("data", {}).get("id") if api_res and api_res.get("code") == 0 else api_res.get("id") if api_res else None
                        if task_id:
                            bj_now = datetime.now(BJ_TZ).strftime("%H:%M")
                            new_task = {"task_id": task_id, "timestamp": time.time(), "time_str": bj_now, "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model}
                            if menu == "🖼️ 图生图": new_task["src_urls"] = uploaded_b64_urls
                            sync_task_to_db(new_task, user_key)
                            st.rerun() 
                        else: st.error(f"❌ API未返回有效ID")
                    else: st.error(f"📡 API 服务器报错")
                except Exception as global_err: st.error(f"💥 提交发生致命错误: {str(global_err)}")

    st.divider()
    with st.expander("📚 提示词库管理与自定义模板"):
        t_c1, t_c2 = st.columns([1, 2])
        with t_c1:
            new_t_name = st.text_input("模板名称", placeholder="如：爆款分镜描述")
            new_t_shortcut = st.checkbox("添加到上方快捷按钮")
        with t_c2: new_t_content = st.text_area("模板内容", placeholder="输入详细的提示词...")
        if st.button("💾 保存模板"):
            if new_t_name and new_t_content:
                add_template(user_key, new_t_name, new_t_content, new_t_shortcut)
                st.success("已保存！"); time.sleep(0.5); st.rerun()
        
        st.markdown("---")
        if not all_temps: st.caption("暂无模板。")
        else:
            for t in all_temps:
                tc1, tc2, tc3, tc4 = st.columns([2, 4, 1.5, 1])
                tc1.write(f"**{t['name']}**")
                tc2.caption(t['content'][:30] + "...")
                is_pinned = t['is_shortcut']
                if tc3.button("📌 取消固定" if is_pinned else "📍 固定快捷", key=f"pin_{t['id']}", use_container_width=True):
                    toggle_template_shortcut(t['id'], is_pinned); st.rerun()
                if tc4.button("🗑️ 删除", key=f"del_{t['id']}", use_container_width=True):
                    delete_template(t['id']); st.rerun()

with col_history:
    c_hist, c_clear = st.columns([3, 1])
    with c_hist: st.markdown("### 🗂️ 创作记录")
    with c_clear: 
        if st.button("🗑️ 清空", help="清空所有历史"):
            if clear_history_db(user_key): st.rerun()
            
    tasks_list = fetch_tasks_from_db(user_key)
    
    if not tasks_list: st.info("暂无记录")
    else:
        total_len = len(tasks_list)
        with st.container(height=700):
            for idx, item in enumerate(tasks_list):
                display_idx = total_len - idx
                m_badge = "👑 VIP" if item.get('model') == 'gpt-image-2-vip' else "普"
                st.markdown(f"**[{display_idx}]** **[{item['time_str']}]** `{m_badge}` 💡 {item['prompt'][:10]}...")
                with st.expander("📋 完整提示词"): st.code(item['prompt'], language="text")
                
                if item['status'] == 'running':
                    src_u = item.get('src_urls') 
                    auto_poll_task(item['task_id'], user_key, item.get('model','gpt-image-2'), item['timestamp'], src_u)
                elif item['status'] == 'succeeded':
                    urls = item.get('urls', [])
                    src_urls = item.get('src_urls', []) 
                    
                    for i, url in enumerate(urls):
                        modal_id = f"cb_{str(item['task_id']).replace('-','')}_{i}"
                        
                        html_str = (
                            f'<div style="position:relative; margin-bottom:10px;">'
                            f'<label for="{modal_id}" style="display:block; cursor:zoom-in;">'
                            f'<img src="{url}" class="my-thumb">'
                            f'<div style="text-align:center;font-size:11px;color:#aaa;margin-top:4px;">图 {i+1} (点击查看)</div>'
                            f'</label>'
                            f'<input type="checkbox" id="{modal_id}" class="my-cb">'
                            f'<div class="my-overlay">'
                            f'<label for="{modal_id}" class="my-bg"></label>'
                            f'<div style="position:absolute; top:20px; color:#fff; background:rgba(0,0,0,0.6); padding:6px 16px; border-radius:20px; font-size:13px; pointer-events:none; z-index:20;">💡 点击图片 或 滚动滚轮 均可缩放，按住拖拽</div>'
                            f'<img src="{url}" class="my-modal-img" draggable="false">'
                            f'</div>'
                            f'</div>'
                        )
                        st.markdown(html_str, unsafe_allow_html=True)
                        
                        if src_urls and i < len(src_urls):
                            if st.button("🪟 开启高级对比 (原图 vs 成品)", key=f"btn_comp_{item['task_id']}_{i}", use_container_width=True):
                                show_viewer_dialog(src_urls[i], url)
                            
                elif item['status'] == 'failed': st.error(f"❌ 尺寸被拒绝 或 生成失败")
                st.divider()

# ==========================================
# 6. 单图双模放大计算引擎
# ==========================================
components.html("""
<script>
    const parentDoc = window.parent.document;
    if (!parentDoc.getElementById('global-single-zoom-v2')) {
        const marker = parentDoc.createElement('div');
        marker.id = 'global-single-zoom-v2';
        parentDoc.body.appendChild(marker);

        let isDragging = false;
        let hasMoved = false; 
        let startX, startY;
        let activeImg = null;

        const updateImg = (img, scale, tx, ty, animate) => {
            img.setAttribute('data-scale', scale);
            img.setAttribute('data-tx', tx);
            img.setAttribute('data-ty', ty);
            img.style.transformOrigin = '0 0';
            img.style.transition = animate ? 'transform 0.2s ease-out' : 'none';
            img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
            img.style.cursor = scale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'zoom-in';
        };

        parentDoc.addEventListener('wheel', function(e) {
            if (window.innerWidth <= 768) return; 
            const img = e.target;
            if (img.tagName === 'IMG' && img.classList.contains('my-modal-img')) {
                e.preventDefault();
                let scale = parseFloat(img.getAttribute('data-scale')) || 1;
                let tx = parseFloat(img.getAttribute('data-tx')) || 0;
                let ty = parseFloat(img.getAttribute('data-ty')) || 0;
                
                const rect = img.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                const xs = mouseX / scale;
                const ys = mouseY / scale;

                const delta = e.deltaY > 0 ? 0.85 : 1.15; 
                let newScale = scale * delta;
                
                if (newScale <= 1) { newScale = 1; tx = 0; ty = 0; }
                else if (newScale > 20) newScale = 20;
                else {
                    tx += xs * (scale - newScale);
                    ty += ys * (scale - newScale);
                }
                updateImg(img, newScale, tx, ty, false); 
            }
        }, {passive: false});

        parentDoc.addEventListener('mousedown', (e) => {
            if (window.innerWidth <= 768) return; 
            const img = e.target;
            if (img.tagName === 'IMG' && img.classList.contains('my-modal-img')) {
                e.preventDefault();
                let scale = parseFloat(img.getAttribute('data-scale')) || 1;
                isDragging = true;
                hasMoved = false; 
                activeImg = img;
                startX = e.clientX - (parseFloat(img.getAttribute('data-tx')) || 0);
                startY = e.clientY - (parseFloat(img.getAttribute('data-ty')) || 0);
                
                if (scale > 1) {
                    img.style.cursor = 'grabbing';
                    img.style.transition = 'none';
                }
            }
        });

        parentDoc.addEventListener('mousemove', (e) => {
            if (!isDragging || !activeImg) return;
            hasMoved = true; 
            let scale = parseFloat(activeImg.getAttribute('data-scale')) || 1;
            if (scale > 1) {
                let tx = e.clientX - startX;
                let ty = e.clientY - startY;
                updateImg(activeImg, scale, tx, ty, false);
            }
        });

        const stopDrag = (e) => {
            if (isDragging && activeImg) {
                isDragging = false;
                let img = activeImg;
                activeImg = null;
                
                if (!hasMoved) {
                    let scale = parseFloat(img.getAttribute('data-scale')) || 1;
                    if (scale === 1) {
                        let newScale = 2.5;
                        const rect = img.getBoundingClientRect();
                        const mouseX = e.clientX - rect.left;
                        const mouseY = e.clientY - rect.top;
                        
                        let tx = mouseX - mouseX * newScale;
                        let ty = mouseY - mouseY * newScale;
                        
                        updateImg(img, newScale, tx, ty, true); 
                    } else {
                        updateImg(img, 1, 0, 0, true);
                    }
                } else {
                    let scale = parseFloat(img.getAttribute('data-scale')) || 1;
                    img.style.cursor = scale > 1 ? 'grab' : 'zoom-in';
                }
            }
        };

        parentDoc.addEventListener('mouseup', stopDrag);
        parentDoc.addEventListener('mouseleave', stopDrag);

        parentDoc.addEventListener('click', function(e) {
            if (e.target.classList.contains('my-bg')) {
                parentDoc.querySelectorAll('.my-modal-img').forEach(img => {
                    updateImg(img, 1, 0, 0, false);
                });
            }
        });
    }
</script>
""", height=0, width=0)
