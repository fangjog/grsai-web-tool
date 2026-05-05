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

# 🌟 绝杀烦人的日志警告：屏蔽底层的 HTTPS 证书未验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 0. 网页基础配置与全局 CSS
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.51", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

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
    @media (hover: hover) { .result-thumb:hover { transform: scale(1.02); box-shadow: 0 6px 16px rgba(0,0,0,0.2); } }
    
    .img-modal-overlay {
        display: none; position: fixed; z-index: 999999; top: 0; left: 0; 
        width: 100vw; height: 100vh; align-items: center; justify-content: center; 
    }
    .modal-checkbox:checked ~ .img-modal-overlay { display: flex !important; }
    
    .modal-close-bg {
        position: absolute; top:0; left:0; width:100%; height:100%; 
        background: rgba(0,0,0,0.92); cursor: zoom-out; z-index: 1;
    }
    
    .single-view {
        position: relative; z-index: 10; max-width: 90vw; max-height: 90vh; 
        border-radius: 12px; overflow: hidden; display: flex; align-items: center; justify-content: center;
    }
    .single-view img {
        max-width: 90vw; max-height: 90vh; border-radius: 12px; 
        box-shadow: 0 0 50px rgba(0,0,0,0.8); object-fit: contain; cursor: zoom-in;
    }
    
    .toggle-compare-btn {
        position: absolute; left: 20px; bottom: 20px; z-index: 15;
        background: rgba(0,255,213,0.8); color: #000; padding: 10px 20px; 
        border-radius: 8px; font-weight: bold; cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,255,213,0.3); transition: 0.2s;
    }
    @media (hover: hover) { .toggle-compare-btn:hover { background: #00ffd5; transform: translateY(-2px); } }
    
    .compare-radio { display: none; }
    .compare-view { display: none; }
    
    .compare-radio:checked ~ .single-view { display: none; } 
    .compare-radio:checked ~ .compare-view { display: flex; } 
    
    .compare-view {
        position: relative; z-index: 10;
        width: 85vw; max-width: 1400px; height: 85vh; 
        background: #1e1e1e; border-radius: 12px;
        flex-direction: column; box-shadow: 0 0 50px rgba(0,0,0,0.8);
        border: 1px solid #444;
    }
    
    .compare-header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 15px 20px; background: #2a2a2a; border-radius: 12px 12px 0 0; border-bottom: 1px solid #444;
    }
    
    .back-btn { background: #444; color: #fff; padding: 6px 16px; border-radius: 6px; cursor: pointer; transition: 0.2s; }
    @media (hover: hover) { .back-btn:hover { background: #555; } }
    .close-btn { color: #aaa; font-size: 32px; cursor: pointer; font-weight: bold; line-height: 0.8; margin-left:10px;}
    @media (hover: hover) { .close-btn:hover { color: #ff4b4b; } }
    
    .view-side { flex: 1; display: flex; gap: 2px; background: #111; border-radius: 0 0 12px 12px; overflow: hidden; flex-direction: row;}
    .side-panel { flex: 1; position: relative; background: #0b0b0b; display: flex; align-items: center; justify-content: center; overflow: hidden;}
    .side-panel img { width: 100%; height: 100%; object-fit: contain; cursor: zoom-in; }
    .side-label { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.8); color: #fff; padding: 8px 18px; border-radius: 20px; font-size: 15px; font-weight:bold; border: 1px solid #555; pointer-events: none;}

    /* 📱 === 手机端自适应 === */
    @media screen and (max-width: 768px) {
        .compare-wrapper { width: 95vw !important; height: 90vh !important; }
        .view-side { flex-direction: column !important; } 
        .compare-header { padding: 10px 12px !important; }
        .compare-header span { font-size: 14px !important; }
        .back-btn { font-size: 12px !important; padding: 4px 10px !important; }
        .close-btn { font-size: 26px !important; }
        .side-label { font-size: 12px !important; bottom: 10px !important; padding: 4px 12px !important; }
        .toggle-compare-btn { left: 50% !important; bottom: 15px !important; transform: translateX(-50%) !important; width: auto !important; text-align: center; font-size: 14px !important; padding: 8px 24px !important; }
    }
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
# 3. 自动轮询 
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
                        f'<div class="modal-wrapper" style="position:relative;">'
                        f'<label for="{zoom_id}"><img src="{data_uri}" class="result-thumb" style="width:100%; border-radius:8px; cursor:zoom-in;"><div style="text-align:center; font-size:11px; color:#aaa; margin-top:2px;">图 {i+1} (点击放大)</div></label>'
                        f'<input type="checkbox" id="{zoom_id}" class="modal-checkbox">'
                        f'<div class="img-modal-overlay"><label for="{zoom_id}" class="modal-close-bg"></label><div class="single-view"><img src="{data_uri}"></div></div>'
                        f'</div>'
                    )
                    st.markdown(html_str, unsafe_allow_html=True)
        
        canvas_result = None
        if not uploaded_files: canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", height=300, key="cvs")
        
        render_shortcut_buttons() 
        prompt_txt = st.text_area("垫图指令", value=st.session_state.current_prompt, height=80)
        
    if prompt_txt != st.session_state.current_prompt: st.session_state.current_prompt = prompt_txt

    c1, c2 = st.columns(2)
    with c1: aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts, key=f"r_{menu}")
    custom_size = st.text_input("自定义像素 (WxH)", key=f"c_{menu}") if aspect_ratio == "自定义像素" else ""
    with c2: quality = st.selectbox("💎 图片质量", quality_opts, key=f"q_{menu}")
    
    if st.button("✨ 立即生成", type="primary", use_container_width=True):
        if card_info['final_points'] < 600: st.error("❌ 积分不足")
        elif not prompt_txt and menu == "✍️ 文生图": st.error("❌ 请输入描述词")
        else:
            with st.spinner("🚀 打包云端数据..."):
                try:
                    final_ratio = custom_size if (menu == "✍️ 文生图" and aspect_ratio == "自定义像素") else (aspect_ratio if menu == "✍️ 文生图" else "auto")
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
                        
                        if src_urls and i < len(src_urls):
                            before_url = src_urls[i]
                            after_url = url
                            html_str = (
                                f'<div class="modal-wrapper" style="position:relative;">'
                                f'<label for="{modal_id}" style="cursor:zoom-in;display:block;">'
                                f'<img src="{after_url}" class="result-thumb" style="width:100%;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,0.1);">'
                                f'<div style="text-align:center;font-size:11px;color:#aaa;margin-top:4px;">图 {i+1} (点击对比)</div>'
                                f'</label>'
                                f'<input type="checkbox" id="{modal_id}" class="modal-checkbox">'
                                f'<div class="img-modal-overlay">'
                                    f'<label for="{modal_id}" class="modal-close-bg"></label>'
                                    f'<input type="checkbox" id="compare_{modal_id}" class="compare-radio">'
                                    f'<div class="single-view">'
                                        f'<img src="{after_url}">'
                                        f'<label for="compare_{modal_id}" class="toggle-compare-btn">✨ 左右对比原图</label>'
                                    f'</div>'
                                    f'<div class="compare-view">'
                                        f'<div class="compare-header">'
                                            f'<div><label for="compare_{modal_id}" class="back-btn">⬅️ 返回</label></div>'
                                            f'<span style="color:#fff;font-size:16px;font-weight:bold;">🪟 图像优化对比 (滚轮放大，鼠标拖拽)</span>'
                                            f'<label for="{modal_id}" class="close-btn">&times;</label>'
                                        f'</div>'
                                        f'<div class="view-side">'
                                            f'<div class="side-panel"><img src="{before_url}"><div class="side-label">原图 (Before)</div></div>'
                                            f'<div class="side-panel"><img src="{after_url}"><div class="side-label">成品 (After)</div></div>'
                                        f'</div>'
                                    f'</div>'
                                f'</div>'
                                f'</div>'
                            )
                            st.markdown(html_str, unsafe_allow_html=True)
                        else:
                            html_str = (
                                f'<div class="modal-wrapper" style="position:relative;">'
                                f'<label for="{modal_id}" style="cursor:zoom-in;display:block;">'
                                f'<img src="{url}" class="result-thumb" style="width:100%;border-radius:8px;box-shadow:0 2px 6px rgba(0,0,0,0.1);">'
                                f'</label>'
                                f'<input type="checkbox" id="{modal_id}" class="modal-checkbox">'
                                f'<div class="img-modal-overlay">'
                                f'<label for="{modal_id}" class="modal-close-bg"></label>'
                                f'<div class="single-view"><img src="{url}"></div>'
                                f'</div>'
                                f'</div>'
                            )
                            st.markdown(html_str, unsafe_allow_html=True)
                            
                elif item['status'] == 'failed': st.error(f"❌ 失败/未通过审查")
                st.divider()

# ==========================================
# 5. 全局注入：防屏蔽版 (恢复为绝对有效的 components.html)
# ==========================================
components.html("""
<script>
const parentDoc = window.parent.document;
if (!parentDoc.getElementById('global-zoom-pan')) {
    const marker = parentDoc.createElement('div');
    marker.id = 'global-zoom-pan';
    parentDoc.body.appendChild(marker);

    let isDragging = false;
    let startX, startY;
    let activeImg = null;

    parentDoc.addEventListener('wheel', function(e) {
        if (window.innerWidth <= 768) return; 
        const img = e.target;
        if (img.tagName === 'IMG' && (img.closest('.side-panel') || img.closest('.single-view'))) {
            e.preventDefault();
            let scale = parseFloat(img.getAttribute('data-scale')) || 1;
            let tx = parseFloat(img.getAttribute('data-tx')) || 0;
            let ty = parseFloat(img.getAttribute('data-ty')) || 0;
            
            let delta = e.deltaY > 0 ? -0.3 : 0.3; 
            if (scale === 1 && delta < 0) return; 
            
            if (scale === 1 && delta > 0) {
                const rect = img.getBoundingClientRect();
                const x = ((e.clientX - rect.left) / rect.width) * 100;
                const y = ((e.clientY - rect.top) / rect.height) * 100;
                img.style.transformOrigin = `${x}% ${y}%`;
            }

            scale += delta;
            if (scale <= 1) { scale = 1; tx = 0; ty = 0; img.style.transformOrigin = `center center`; }
            if (scale > 8) scale = 8; 

            img.setAttribute('data-scale', scale);
            img.setAttribute('data-tx', tx);
            img.setAttribute('data-ty', ty);
            
            img.style.transition = 'transform 0.1s ease-out';
            img.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
            img.style.cursor = scale > 1 ? 'grab' : 'zoom-in';
        }
    }, {passive: false});

    parentDoc.addEventListener('mousedown', (e) => {
        if (window.innerWidth <= 768) return; 
        const img = e.target;
        if (img.tagName === 'IMG' && (img.closest('.side-panel') || img.closest('.single-view'))) {
            let scale = parseFloat(img.getAttribute('data-scale')) || 1;
            if (scale > 1) {
                isDragging = true;
                activeImg = img;
                startX = e.clientX - (parseFloat(img.getAttribute('data-tx')) || 0);
                startY = e.clientY - (parseFloat(img.getAttribute('data-ty')) || 0);
                img.style.transition = 'none'; 
                img.style.cursor = 'grabbing';
                e.preventDefault();
            }
        }
    });

    parentDoc.addEventListener('mousemove', (e) => {
        if (!isDragging || !activeImg) return;
        let tx = e.clientX - startX;
        let ty = e.clientY - startY;
        let scale = parseFloat(activeImg.getAttribute('data-scale')) || 1;
        
        activeImg.setAttribute('data-tx', tx);
        activeImg.setAttribute('data-ty', ty);
        activeImg.style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
    });

    const stopDrag = () => {
        if (isDragging && activeImg) {
            isDragging = false;
            activeImg.style.cursor = 'grab';
            activeImg.style.transition = 'transform 0.1s ease-out';
            activeImg = null;
        }
    };
    parentDoc.addEventListener('mouseup', stopDrag);
    parentDoc.addEventListener('mouseleave', stopDrag);

    parentDoc.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal-close-bg') || e.target.classList.contains('close-btn') || e.target.classList.contains('back-btn')) {
            parentDoc.querySelectorAll('.side-panel img, .single-view img').forEach(img => {
                img.setAttribute('data-scale', 1);
                img.setAttribute('data-tx', 0);
                img.setAttribute('data-ty', 0);
                img.style.transform = 'translate(0px, 0px) scale(1)';
                img.style.cursor = 'zoom-in';
            });
        }
    });
}
</script>
""", height=0, width=0)
