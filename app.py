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
st.set_page_config(page_title="AI Pro Studio V6.57", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    /* 隐藏原生图片的全屏按钮，引导用户点击我们的高级查阅台 */
    button[title="View fullscreen"] { display: none !important; }
    
    /* 缩略图增强 */
    .thumb-img { border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 常量、数据库与缓存加速引擎
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
# 2. 独立沙盒引擎：单图/双图 高级查阅台
# ==========================================
@st.dialog("🔍 高级图像查阅台", width="large")
def show_viewer_dialog(after_url, before_url=None):
    # 根据是否传入 before_url 自动切换 单图 / 双图并排
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
            <span style="font-size: 14px; color: #ccc;">💡 <b>点击左键</b>一键放大，<b>滚轮</b>无极缩放，按住可拖拽平移。</span>
            <div class="btn-group">
                <button class="btn" onclick="zoomBtn(1.25)">➕ 放大</button>
                <button class="btn" onclick="zoomBtn(0.8)">➖ 缩小</button>
                <button class="btn" onclick="resetView()" style="background: #444; color: white;">🔄 1:1 还原</button>
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
                    img.style.transition = animated ? 'transform 0.15s ease-out' : 'none';
                    img.style.transform = `translate(${{pointX}}px, ${{pointY}}px) scale(${{scale}})`;
                    // 更新鼠标样式
                    img.style.cursor = scale > 1 ? (isPanning ? 'grabbing' : 'grab') : 'zoom-in';
                }});
            }}

            container.onmousedown = (e) => {{
                if (e.target.tagName !== 'IMG' && !e.target.classList.contains('panel')) return;
                e.preventDefault();
                start = {{ x: e.clientX - pointX, y: e.clientY - pointY }};
                isPanning = true;
                hasMoved = false;
                images.forEach(img => img.style.cursor = 'grabbing');
            }};

            window.onmousemove = (e) => {{
                if (!isPanning) return;
                hasMoved = true;
                pointX = e.clientX - start.x; pointY = e.clientY - start.y;
                setTransform(false);
            }};

            window.onmouseup = (e) => {{
                if (isPanning) {{
                    isPanning = false;
                    
                    // 如果没有移动，就是点击事件！执行一键放大/缩小
                    if (!hasMoved) {{
                        const targetImg = e.target.closest('.panel')?.querySelector('img');
                        if (targetImg) {{
                            if (scale === 1) {{
                                // 放大到 2.5倍
                                const rect = targetImg.getBoundingClientRect();
                                const mouseX = e.clientX - rect.left;
                                const mouseY = e.clientY - rect.top;
                                const xs = mouseX / scale;
                                const ys = mouseY / scale;

                                scale = 2.5;
                                pointX += xs * (1 - scale);
                                pointY += ys * (1 - scale);
                                setTransform(true);
                            }} else {{
                                // 还原到 1倍
                                scale = 1; pointX = 0; pointY = 0;
                                setTransform(true);
                            }}
                            return; // 结束，不执行拖拽游标更新
                        }}
                    }}
                    
                    // 仅更新鼠标样式
                    images.forEach(img => img.style.cursor = scale > 1 ? 'grab' : 'zoom-in');
                }}
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
                if (newScale <= 1) {{ newScale = 1; pointX = 0; pointY = 0; }}
                else if (newScale > 20) newScale = 20;
                else {{
                    pointX += xs * (scale - newScale);
                    pointY += ys * (scale - newScale);
                }}

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
                    task_update = {"task_id": task_id, "status": "succeeded", "urls": [urls[0]], "is_deducted": True}
                    if src_urls: task_update["src_urls"] = src_urls 
                    sync_task_to_db(task_update, active_user_key)
                    time.sleep(1.0); st.rerun(); return 
                elif status == "failed":
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
        prompt_txt = st.text_area("画面描述", key="current_prompt", height=120)
    else:
        st.markdown("#### 🖼️ 图生图")
        uploaded_files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        
        if uploaded_files:
            p_cols = st.columns(6) 
            for i, file in enumerate(uploaded_files):
                data_uri = process_cached_data_uri(file.getvalue())
                uploaded_b64_urls.append(data_uri) 
                with p_cols[i % 6]:
                    st.image(data_uri, caption=f"图 {i+1}")
        
        canvas_result = None
        if not uploaded_files: canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", height=300, key="cvs")
        
        render_shortcut_buttons() 
        prompt_txt = st.text_area("垫图指令", key="current_prompt", height=80)
        


    c1, c2 = st.columns(2)
    with c1: aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts, key=f"r_{menu}")
    custom_size = st.text_input("自定义像素 (WxH)", key=f"c_{menu}") if aspect_ratio == "自定义像素" else ""
    with c2: quality = st.selectbox("💎 图片质量", quality_opts, key=f"q_{menu}")
    
    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        if card_info['final_points'] < 600: st.error("❌ 积分不足")
        elif not st.session_state.current_prompt and menu == "✍️ 文生图": st.error("❌ 请输入描述词")
        else:
            with st.spinner("🚀 打包云端数据..."):
                try:
                    final_ratio = custom_size if (menu == "✍️ 文生图" and aspect_ratio == "自定义像素") else (aspect_ratio if menu == "✍️ 文生图" else "auto")
                    payload = {"model": selected_model, "prompt": st.session_state.current_prompt, "webHook": "-1", "shutProgress": True, "aspectRatio": final_ratio, "quality": quality if menu == "✍️ 文生图" else "auto"}
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
                            new_task = {"task_id": task_id, "timestamp": time.time(), "time_str": bj_now, "prompt": st.session_state.current_prompt, "status": "running", "urls": [], "model": selected_model}
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
                        # 直接使用最稳定的原生缩略图展示
                        st.image(url, use_container_width=True)
                        
                        # 🌟 无论是看单图，还是双图对比，统一使用极其稳定的沙盒弹窗！
                        if src_urls and i < len(src_urls):
                            btn_cols = st.columns(2)
                            with btn_cols[0]:
                                if st.button("🔍 放大单图", key=f"btn_single_{item['task_id']}_{i}", use_container_width=True):
                                    show_viewer_dialog(url) # 传一个参数，自动变成高级单图模式
                            with btn_cols[1]:
                                if st.button("🪟 左右对比", key=f"btn_comp_{item['task_id']}_{i}", use_container_width=True):
                                    show_viewer_dialog(url, src_urls[i]) # 传两个参数，自动变成高级双图模式
                        else:
                            if st.button("🔍 放大查看细节", key=f"btn_single_{item['task_id']}_{i}", use_container_width=True):
                                show_viewer_dialog(url) # 文生图：仅显示高级单图模式
                            
                elif item['status'] == 'failed': st.error(f"❌ 失败/未通过审查")
                st.divider()
