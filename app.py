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

# 🌟 屏蔽 HTTPS 不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

# ==========================================
# 0. 网页基础配置与全局 CSS
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.72", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

# 🌟 绝技：将按钮样式强制重塑为“图片容器”
st.markdown("""
<style>
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    button[title="View fullscreen"] { display: none !important; }
    
    /* 核心：图片按钮样式 */
    .stButton.image-btn-container > button {
        width: 100% !important;
        padding: 0 !important;
        border: 2px solid #333 !important;
        border-radius: 12px !important;
        background-color: #0e1117 !important;
        overflow: hidden !important;
        transition: 0.3s ease !important;
        display: flex !important;
        flex-direction: column !important;
    }
    .stButton.image-btn-container > button:hover {
        border-color: #00ffd5 !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(0,255,213,0.3) !important;
    }
    .stButton.image-btn-container img {
        width: 100%;
        display: block;
        object-fit: contain;
    }
    .stButton.image-btn-container .btn-hint {
        background: rgba(0,255,213,0.1);
        color: #00ffd5;
        font-size: 11px;
        padding: 6px 0;
        width: 100%;
        text-align: center;
        border-top: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 常量与数据库连接
# ==========================================
MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}
ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2"]
pixel_opts = ["默认", "1k", "2k", "4k", "自定义"]
quality_opts = ["auto", "high", "medium", "low"]
BJ_TZ = pytz.timezone('Asia/Shanghai')

try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("❌ 数据库连接失败"); st.stop()

@st.cache_data(show_spinner=False, max_entries=20)
def process_cached_data_uri(img_bytes):
    img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=82)
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
    except: pass

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
            new_pts = res.data[0]['used_points'] + amount
            new_fin = res.data[0]['final_points'] - amount
            supabase.table("user_cards").update({"used_points": new_pts, "final_points": new_fin}).eq("card_key", card_key).execute()
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
# 2. 核心查阅引擎 (iframe 隔离版)
# ==========================================
@st.dialog("🔍 图像细节查阅台", width="large")
def show_viewer_dialog(after_url, before_url=None):
    is_dual = before_url is not None
    panels_html = f'<div class="panel left"><img class="sync-img" src="{before_url}" draggable="false"><div class="label">📤 原图 (Before)</div></div>' if is_dual else ""
    panels_html += f'<div class="panel"><img class="sync-img" src="{after_url}" draggable="false"><div class="label">✨ {"成品 (After)" if is_dual else "查看细节"}</div></div>'

    html_code = f"""
    <!DOCTYPE html><html><head><style>
        body {{ margin: 0; background: #0e1117; color: white; font-family: sans-serif; overflow: hidden; user-select: none; }}
        .toolbar {{ display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; background: #262730; border-bottom: 1px solid #444; }}
        .btn {{ background: #00ffd5; color: black; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: 0.2s; }}
        .btn:hover {{ transform: scale(1.05); }}
        .viewer {{ display: flex; width: 100vw; height: calc(100vh - 60px); }}
        .panel {{ flex: 1; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; }}
        .panel.left {{ border-right: 2px solid #555; }}
        .panel img {{ max-width: 100%; max-height: 100%; cursor: zoom-in; transform-origin: 0 0; will-change: transform; }}
        .label {{ position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); padding: 8px 20px; border-radius: 20px; font-weight: bold; pointer-events: none; }}
    </style></head><body>
        <div class="toolbar">
            <span>💡 <b>点击图片</b>一键放大，<b>滚轮</b>缩放，按住可平移。双图视角实时同步。</span>
            <div><button class="btn" onclick="zoomBtn(1.3)">➕ 放大</button> <button class="btn" onclick="zoomBtn(0.7)">➖ 缩小</button> <button class="btn" onclick="resetView()" style="background:#444;color:#fff;">🔄 还原</button></div>
        </div>
        <div class="viewer" id="container">{panels_html}</div>
        <script>
            let s = 1, x = 0, y = 0, start={{x:0,y:0}}, pan=false, mov=false;
            const cnt=document.getElementById('container'), imgs=document.querySelectorAll('.sync-img');
            function upd(a=false){{ imgs.forEach(i=>{{ i.style.transition=a?'transform 0.2s':'none'; i.style.transform=`translate(${{x}}px,${{y}}px) scale(${{s}})`; i.style.cursor=s>1?(pan?'grabbing':'grab'):'zoom-in'; }}); }}
            cnt.onmousedown=(e)=>{{ if(e.target.tagName!='IMG')return; e.preventDefault(); start={{x:e.clientX-x,y:e.clientY-y}}; pan=true; mov=false; upd(); }};
            window.onmousemove=(e)=>{{ if(!pan)return; mov=true; x=e.clientX-start.x; y=e.clientY-start.y; upd(); }};
            window.onmouseup=(e)=>{{
                if(!pan)return; pan=false;
                if(!mov){{
                    const r=e.target.getBoundingClientRect(); const mx=(e.clientX-r.left)/s,my=(e.clientY-r.top)/s;
                    if(s==1){{s=2.5;x+=mx*(1-s);y+=my*(1-s);}}else{{s=1;x=0;y=0;}} upd(true);
                }} else upd();
            }};
            cnt.onwheel=(e)=>{{
                e.preventDefault(); const r=imgs[0].getBoundingClientRect();
                const mx=(e.clientX-r.left)/s,my=(e.clientY-r.top)/s;
                let ns=s*(e.deltaY>0?0.85:1.15); if(ns<=1){{s=1;x=0;y=0;}} else if(ns<20){{x+=mx*(s-ns);y+=my*(s-ns);s=ns;}} upd();
            }};
            function zoomBtn(f){{ const cx=cnt.clientWidth/2,cy=cnt.clientHeight/2,mx=(cx-x)/s,my=(cy-y)/s,ns=s*f; if(ns<1){{resetView();return;}} x+=mx*(s-ns);y+=my*(s-ns);s=ns; upd(true); }}
            function resetView(){{ s=1;x=0;y=0; upd(true); }}
        </script></body></html>
    """
    components.html(html_code, height=750, scrolling=False)

# ==========================================
# 3. 登录与超强固自动轮询
# ==========================================
query_key = st.query_params.get("key", "")
card_info = get_card_info(query_key) if query_key else None

if not card_info:
    st.markdown("<br><br><br><div style='text-align: center;'><h1>🚀 AI Pro Studio</h1><p>输入激活码解锁创作台</p></div>", unsafe_allow_html=True)
    user_key_input = st.text_input("激活码", type="password", placeholder="🔑 在此输入激活码...", label_visibility="collapsed")
    if st.button("立即解锁进入系统 ✨", type="primary", use_container_width=True):
        if get_card_info(user_key_input.strip()):
            st.query_params["key"] = user_key_input.strip(); st.rerun()
        else: st.error("❌ 激活码无效")
    st.stop()

user_key = query_key
GRSAI_API_KEY = st.secrets.get((card_info.get('api_secret_name') or "API_VIP888").strip("'").strip(), "")

def auto_poll_task(task_id, active_user_key, model_used, start_time, src_urls=None):
    ph = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    for i in range(300):
        p = min(5 + int((time.time() - start_time) * 0.2), 98) 
        ph.markdown(f'<div style="background:#111;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:12px;border-radius:6px;background:linear-gradient(90deg,#00c2ff,#00ffd5);width:{p}%;"></div></div><div style="text-align:right;color:#00ffd5;font-size:12px;margin-top:4px;">⚡ 任务执行中... {p}%</div>', unsafe_allow_html=True)
        try:
            resp = requests.post("https://grsai.dakka.com.cn/v1/draw/result", headers=headers, json={"id": task_id}, verify=False, timeout=10)
            q_res = parse_api_response(resp.text)
            if q_res and isinstance(q_res, dict):
                # 🌟 1. 安全获取基础 status
                status = str(q_res.get("status", "")).lower()
                
                # 🌟 2. 安全解析 data 块 (防 null 指针异常)
                data_obj = q_res.get("data")
                if isinstance(data_obj, dict):
                    status = str(data_obj.get("status", status)).lower()
                
                # 🌟 3. 错误兜底机制：只要出现 error 或 failure_reason 有值，强制判定失败！
                if str(q_res.get("error", "")) or str(q_res.get("failure_reason", "")):
                    status = "failed"
                if isinstance(data_obj, dict) and (str(data_obj.get("error", "")) or str(data_obj.get("failure_reason", ""))):
                    status = "failed"
                    
                # 🌟 4. 异常 code 兜底
                if str(q_res.get("code", "0")) != "0" and status not in ["running", "in_progress"]: 
                    status = "failed"

                if status in ["succeeded", "success"]:
                    deduct_balance(active_user_key, MODEL_COSTS.get(model_used, 600)); st.rerun(); return 
                elif status in ["failed", "fail", "error"]:
                    sync_task_to_db({"task_id": task_id, "status": "failed"}, active_user_key); st.rerun(); return
        except Exception as e:
            pass # 静默容错，下一次循环继续
        time.sleep(3)

# ==========================================
# 4. 主界面布局
# ==========================================
st.sidebar.markdown(f'### 👤 用户中心\n`{user_key}`')
st.sidebar.markdown(f'<div style="background:#1e1e1e;padding:15px;border-radius:12px;border:1px solid #333;"><div style="color:#888;font-size:13px;">获取总额: {card_info.get("total_points",0)}</div><div style="color:#ff4b4b;font-size:13px;">累计消耗: -{card_info.get("used_points",0)}</div><hr style="margin:10px 0;border-color:#444;"><div style="color:#00ffd5;font-size:28px;font-weight:bold;">{card_info.get("final_points",0)}</div></div>', unsafe_allow_html=True)
if st.sidebar.button("🚪 退出登录", use_container_width=True): st.query_params.clear(); st.rerun()
menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图"])

st.title("🚀 AI Pro Studio")
col_main, col_history = st.columns([7, 3])

with col_main:
    selected_model = st.selectbox("🤖 模型选择", ["gpt-image-2", "gpt-image-2-vip"])
    if "current_prompt" not in st.session_state: st.session_state.current_prompt = ""
    all_temps = fetch_templates(user_key)
    sc = [t for t in all_temps if t['is_shortcut']]
    if sc:
        st.caption("✨ 快捷描述词模板")
        s_cols = st.columns(min(len(sc), 5))
        for i, s_item in enumerate(sc):
            if s_cols[i % 5].button(f"📌 {s_item['name']}", key=f"s_{s_item['id']}", use_container_width=True):
                st.session_state.current_prompt = s_item['content']; st.rerun()

    uploaded_b64_urls = [] 
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("画面描述", value=st.session_state.current_prompt, height=120)
    else:
        st.markdown("#### 🖼️ 图生图")
        up_files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if up_files:
            up_cols = st.columns(6)
            for i, f in enumerate(up_files):
                uri = process_cached_data_uri(f.getvalue()); uploaded_b64_urls.append(uri)
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
            with st.spinner("🚀 任务分发中..."):
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
                                final_ratio = f"{int(w)}x{int(h)}"
                    payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True, "aspectRatio": final_ratio, "quality": quality if menu == "✍️ 文生图" else "auto"}
                    if menu == "🖼️ 图生图": payload["urls"] = uploaded_b64_urls 
                    resp = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers={"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}, json=payload, verify=False, timeout=30)
                    if resp.status_code == 200:
                        api_res = parse_api_response(resp.text)
                        tid = api_res.get("data", {}).get("id") if api_res and api_res.get("code") == 0 else api_res.get("id") if api_res else None
                        if tid:
                            sync_task_to_db({"task_id": tid, "timestamp": time.time(), "time_str": datetime.now(BJ_TZ).strftime("%H:%M"), "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model, "src_urls": uploaded_b64_urls if menu=="🖼️ 图生图" else None}, user_key)
                            st.rerun() 
                except: st.error("💥 提交任务失败")

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
                    for i, url in enumerate(item.get('urls', [])):
                        # 🌟 核心：将按钮标签重塑为图片
                        btn_label = f'<img src="{url}"><div class="btn-hint">🔍 点击查看详情</div>'
                        st.markdown('<div class="image-btn-container">', unsafe_allow_html=True)
                        if st.button(btn_label, key=f"img_btn_{item['task_id']}_{i}"):
                            srcs = item.get('src_urls', [])
                            if srcs and i < len(srcs): show_viewer_dialog(url, srcs[i])
                            else: show_viewer_dialog(url)
                        st.markdown('</div>', unsafe_allow_html=True)
                elif item['status'] == 'failed': st.error("❌ API拒绝: 图像上传失败 / 格式错误")
                st.divider()
