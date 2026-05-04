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
st.set_page_config(page_title="AI Pro Studio V6.16", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

# 🌟 修复抖动、修复放大、修复圆角的全局 CSS
st.markdown("""
<style>
    @media (max-width: 768px) { .block-container { padding: 1rem 0.5rem !important; } }
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .result-thumb { width: 100%; border-radius: 8px; cursor: zoom-in; transition: transform 0.2s; box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-top: 10px; }
    .result-thumb:hover { transform: scale(1.02); }
    .img-modal-overlay { display: none; position: fixed; z-index: 99999; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.9); align-items: center; justify-content: center; cursor: zoom-out; text-decoration: none !important; }
    .img-modal-overlay:target { display: flex; opacity: 1; }
    .img-modal-overlay img { max-width: 95%; max-height: 95%; border-radius: 12px; box-shadow: 0 0 40px rgba(0,194,255,0.3); border: 1px solid rgba(0,194,255,0.2); }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 数据库与初始化
# ==========================================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("❌ 数据库连接失败。")
    st.stop()

BJ_TZ = pytz.timezone('Asia/Shanghai')
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
        return res.data[0] if res.data else None
    except: return None

def deduct_balance(card_key, amount):
    try:
        res = supabase.table("user_cards").select("used_points, final_points").eq("card_key", card_key).execute()
        if res.data:
            u, f = res.data[0]['used_points'], res.data[0]['final_points']
            supabase.table("user_cards").update({"used_points": u + amount, "final_points": f - amount}).eq("card_key", card_key).execute()
    except: pass

# ==========================================
# 2. 身份验证
# ==========================================
user_key = st.query_params.get("key", "")
card_info = get_card_info(user_key)

if not card_info:
    st.markdown("<br><br><br>", unsafe_allow_html=True) 
    c1, col2, c3 = st.columns([1, 2, 1]) 
    with col2:
        st.markdown("<h1 style='text-align:center;'>🚀 AI Pro Studio</h1>", unsafe_allow_html=True)
        u_input = st.text_input("激活码", type="password", placeholder="🔑 输入激活码解锁...")
        if st.button("立即解锁进入系统 ✨", type="primary", use_container_width=True):
            if get_card_info(u_input.strip()):
                st.query_params["key"] = u_input.strip(); st.rerun()
            else: st.error("❌ 激活码无效")
    st.stop() 

current_balance = card_info.get('final_points', 0)
total_pts = card_info.get('total_points', 0)
used_pts = card_info.get('used_points', 0)
GRSAI_API_KEY = st.secrets.get((card_info.get('api_secret_name') or "API_VIP888").strip("'").strip(), "")

# ==========================================
# 3. 任务管理
# ==========================================
if 'tasks' not in st.session_state:
    st.session_state.tasks = load_json(TASKS_FILE).get(user_key, [])

def clean_and_save_tasks():
    curr = time.time()
    # 自动清理 1 小时前的记录，保留最近 10 条
    st.session_state.tasks = [t for t in st.session_state.tasks if (curr - t['timestamp']) < 3600][-10:]
    all_h = load_json(TASKS_FILE); all_h[user_key] = st.session_state.tasks
    save_json(TASKS_FILE, all_h)
    return st.session_state.tasks

def pil_to_data_uri(img):
    buf = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)); img.save(buf, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

# ==========================================
# 自动轮询 (修正 ID 冲突 & 杜绝源码泄露)
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    
    # 格式化 ID 防止 CSS 语法错误
    safe_id = "".join(filter(str.isalnum, task_id))
    
    for i in range(60):
        p = min(5 + int(time.time() - start_time), 95)
        # 稳健渲染进度条
        placeholder.markdown(f'<div style="background:#1a1a1a;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:14px;border-radius:6px;background:linear-gradient(90deg,#00c2ff,#00ffd5);width:{p}%;"></div></div><div style="text-align:right;color:#00ffd5;font-size:12px;margin-top:4px;font-family:monospace;">⚡ 云端算力注入中... {p}%</div>', unsafe_allow_html=True)
        
        try:
            q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
            if q_res.get("code") == 0:
                status = q_res["data"]["status"]
                if status == "succeeded":
                    urls = [img["url"] for img in q_res["data"]["results"]]
                    with placeholder.container():
                        st.markdown(f'<div style="background:#1a1a1a;border-radius:10px;padding:4px;border:1px solid #333;"><div style="height:14px;border-radius:6px;background:linear-gradient(90deg,#00ff88,#00c2ff);width:100%;box-shadow:0 0 10px #00ff88;"></div></div><div style="text-align:right;color:#00ff88;font-size:12px;margin-top:4px;">✅ 绘制完成！</div>', unsafe_allow_html=True)
                        for idx, url in enumerate(urls):
                            m_id = f"m_poll_{safe_id}_{idx}"
                            st.markdown(f'<a href="#{m_id}"><img src="{url}" class="result-thumb" style="border:2px solid #00ff88;"></a><a href="#!" class="img-modal-overlay" id="{m_id}"><img src="{url}"></a>', unsafe_allow_html=True)
                    
                    # 🌟 计费双重锁定
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id and not t.get('is_deducted'):
                            deduct_balance(active_user_key, len(urls) * MODEL_COSTS.get(model_used, 600))
                            t.update({"status": "succeeded", "urls": urls, "is_deducted": True})
                    clean_and_save_tasks(); time.sleep(2); st.rerun(); return 
                elif status == "failed":
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id: t.update({"status": "failed", "reason": "触发安全审查"})
                    clean_and_save_tasks(); st.rerun(); return
        except: pass
        time.sleep(3)

# ==========================================
# 4. 主界面布局 (保持 7:3)
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
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("画面描述", height=150, placeholder="描述词...")
    else:
        st.markdown("#### 🖼️ 图生图模式")
        files = st.file_uploader("上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if files:
            cols = st.columns(6)
            for i, f in enumerate(files): cols[i%6].image(Image.open(f), use_container_width=True)
        canvas_result = None
        if not files: canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", height=300, key="cvs")
        prompt_txt = st.text_area("垫图指令", height=100, placeholder="基于原图的修改描述...")

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
            payload = {"model": selected_model, "prompt": prompt_txt, "aspectRatio": custom_size or aspect_ratio, "quality": quality, "shutProgress": True}
            if menu == "🖼️ 图生图":
                u_list = [pil_to_data_uri(Image.open(f)) for f in files] if files else [pil_to_data_uri(Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA'))] if canvas_result else []
                if not u_list: st.error("⚠️ 请提供参考图"); st.stop()
                payload["urls"] = u_list
            
            try:
                res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers={"Authorization": f"Bearer {GRSAI_API_KEY}"}, json=payload, verify=False).json()
                if res.get("code") == 0:
                    bj_now = datetime.now(BJ_TZ).strftime("%H:%M")
                    st.session_state.tasks.append({
                        "task_id": res["data"]["id"], "timestamp": time.time(), "time_str": bj_now, 
                        "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model, "is_deducted": False
                    })
                    clean_and_save_tasks()
                    st.success("🎉 任务已提交云端！"); time.sleep(0.5); st.rerun()
                else: st.error(f"❌ 失败: {res.get('msg')}")
            except: st.error("📡 网络异常，请检查配置")

with col_history:
    st.markdown("### 🗂️ 创作记录")
    tasks_list = clean_and_save_tasks() if 'tasks' in st.session_state else []
    with st.container(height=700):
        for item in reversed(tasks_list):
            m_badge = "👑 VIP" if item.get('model') == 'gpt-image-2-vip' else "普"
            st.markdown(f"**[{item['time_str']}]** `{m_badge}` 💡 {item['prompt'][:10]}...")
            with st.expander("📋 完整提示词"): st.code(item['prompt'], language="text")
            
            if item['status'] == 'running':
                auto_poll_task(item['task_id'], user_key, item['model'], item['timestamp'])
            elif item['status'] == 'succeeded':
                safe_item_id = "".join(filter(str.isalnum, item['task_id']))
                for idx, url in enumerate(item['urls']):
                    m_id = f"m_h_{safe_item_id}_{idx}"
                    st.markdown(f'<a href="#{m_id}"><img src="{url}" class="result-thumb"></a><a href="#!" class="img-modal-overlay" id="{m_id}"><img src="{url}"></a>', unsafe_allow_html=True)
            elif item['status'] == 'failed': st.error(f"❌ {item.get('reason', '生成失败')}")
            st.divider()
