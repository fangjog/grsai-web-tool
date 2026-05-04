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
# 0. 网页基础配置与防抖 CSS
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.25", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    @media (max-width: 768px) { .block-container { padding: 1rem 0.5rem !important; } }
    [data-testid="stVerticalBlock"] { overflow-x: hidden !important; }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    
    .thumb-img { 
        width: 100%; border-radius: 8px; cursor: zoom-in; box-shadow: 0 2px 6px rgba(0,0,0,0.1); 
        margin-top: 10px; transition: transform 0.2s; display: block; opacity: 1 !important; 
    }
    .thumb-img:hover { transform: scale(1.02); }
    .zoom-modal { 
        display: none; position: fixed; z-index: 999999; top: 0; left: 0; 
        width: 100vw; height: 100vh; background: rgba(0,0,0,0.92); 
        align-items: center; justify-content: center; cursor: zoom-out; text-decoration: none !important; 
    }
    .zoom-modal:target { display: flex; }
    .zoom-modal img { 
        max-width: 95vw; max-height: 95vh; border-radius: 12px; 
        box-shadow: 0 0 40px rgba(0,194,255,0.4); border: 2px solid rgba(0,194,255,0.2); object-fit: contain; 
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
except:
    st.error("❌ 数据库连接失败。")
    st.stop()

BJ_TZ = pytz.timezone('Asia/Shanghai')
MODEL_COSTS = {"gpt-image-2": 600, "gpt-image-2-vip": 900}
TASKS_FILE = "tasks_history.json"
ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2", "自定义像素"]
quality_opts = ["auto", "high", "medium", "low"]

def parse_api_response(text):
    if not text: return None
    try: return json.loads(text)
    except: pass
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('data:'):
            try: return json.loads(line[5:].strip())
            except: pass
    return None

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
    except: pass
    return None

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
query_key = st.query_params.get("key", "")
card_info = get_card_info(query_key) if query_key else None

if not card_info:
    st.markdown("<br><br><br>", unsafe_allow_html=True) 
    c1, col2, c3 = st.columns([1, 2, 1]) 
    with col2:
        st.markdown("<h1 style='text-align:center;'>🚀 AI Pro Studio</h1><p style='text-align:center;'>输入激活码解锁创作台</p>", unsafe_allow_html=True)
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
# 3. 任务队列隔离与异步更新
# ==========================================
all_history = load_json(TASKS_FILE, default={})
if isinstance(all_history, list): all_history = {}
if 'tasks' not in st.session_state: st.session_state.tasks = all_history.get(user_key, [])

def clean_and_get_tasks(active_key):
    curr_time = time.time()
    valid = [t for t in st.session_state.tasks if (curr_time - t['timestamp']) < 3600]
    st.session_state.tasks = valid[-10:] # 保证最多且只显示 10 条
    global_history = load_json(TASKS_FILE, default={})
    if isinstance(global_history, list): global_history = {}
    global_history[active_key] = st.session_state.tasks
    save_json(TASKS_FILE, global_history)
    return st.session_state.tasks

def add_task(item, active_key):
    st.session_state.tasks.append(item)
    clean_and_get_tasks(active_key)

def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

# ==========================================
# 自动轮询 + 异步并行任务状态追踪
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
                    
                    imgs_html = "".join([f'<img src="{url}" class="result-thumb" style="border: 2px solid #00ff88; box-shadow: 0 0 20px rgba(0,255,136,0.2); margin-top: 10px;">' for url in urls])
                    full_bar = f'<div style="background-color: #1a1a1a; border-radius: 10px; padding: 4px; border: 1px solid #333;"><div style="height: 14px; border-radius: 6px; background: linear-gradient(90deg, #00ff88, #00c2ff); width: 100%; box-shadow: 0 0 10px #00ff88;"></div></div><div style="text-align: right; color: #00ff88; font-size: 13px; font-weight: bold; margin-top: 6px; font-family: monospace;">✅ 绘制完成！</div>{imgs_html}'
                    placeholder.markdown(full_bar, unsafe_allow_html=True)
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            if not t.get('is_deducted', False):
                                num_images = len(results)
                                total_cost = num_images * cost_per_img
                                deduct_balance(active_userkey, total_cost)
                                t['is_deducted'] = True
                            t['status'] = 'succeeded'
                            t['urls'] = urls
                    
                    clean_and_get_tasks(active_userkey)
                    time.sleep(1.5)
                    st.rerun()
                    return 
                    
                elif status == "failed":
                    raw_reason = q_res["data"].get("failure_reason", "")
                    raw_error = q_res["data"].get("error", "")
                    actual_err = raw_error if raw_error and raw_error != "error" else raw_reason
                    
                    error_dict = {
                        "The current model has a high load, please use another model": "当前模型并发排队拥挤，请稍后再试",
                        "error": "云端生成异常或触发安全审查，请调整提示词"
                    }
                    cn_error = error_dict.get(actual_err, f"系统异常: {actual_err}")
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id: 
                            t['status'] = 'failed'
                            t['reason'] = cn_error
                    clean_and_get_tasks(active_userkey)
                    st.rerun()
        except: pass
        time.sleep(3)
        
    for t in st.session_state.tasks:
        if t['task_id'] == task_id and t['status'] == 'running':
            t['status'] = 'failed'
            t['reason'] = "请求超时，请检查网络或稍后重试"
    clean_and_get_tasks(active_userkey)
    st.rerun()

# ==========================================
# 4. 主界面
# ==========================================
st.sidebar.markdown(f'### 👤 用户中心\n当前用户: `{user_key}`')
st.sidebar.markdown(f"""
<div style="background-color: #1e1e1e; padding: 15px; border-radius: 12px; border: 1px solid #333; box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);">
    <div style="color: #888; font-size: 13px; margin-bottom: 8px;">💳 额度账户明细</div>
    <div style="display: flex; justify-content: space-between; font-size: 14px; color: #ddd;">
        <span>获取总额:</span><span>{total_pts}</span>
    </div>
    <div style="display: flex; justify-content: space-between; font-size: 14px; color: #ff4b4b; margin-top: 4px;">
        <span>累计消耗:</span><span>- {used_pts}</span>
    </div>
    <div style="margin-top: 10px; padding-top: 10px; border-top: 1px dashed #444;">
        <div style="color: #888; font-size: 12px;">可用余额 (最终积分)</div>
        <div style="color: #00ffd5; font-size: 28px; font-weight: bold; text-shadow: 0 0 10px rgba(0,255,213,0.3);">{current_balance}</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown(f'<div style="font-size:12px; color:#666; margin-top:10px; text-align:center;">标准模式约 {current_balance//600} 张 | VIP模式约 {current_balance//900} 张</div>', unsafe_allow_html=True)

if st.sidebar.button("🚪 退出登录", use_container_width=True):
    st.query_params.clear()
    if 'tasks' in st.session_state: del st.session_state.tasks
    st.rerun()
    
st.sidebar.divider()
menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图"])

st.title("🚀 AI Pro Studio")
col_main, col_history = st.columns([7, 3])

with col_main:
    selected_model = st.selectbox("🤖 选择创作模型", ["gpt-image-2", "gpt-image-2-vip"], help="VIP模型支持更高分辨率和更强细节")
    
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("输入画面详细描述", height=120, placeholder="描述词...")
        c1, c2 = st.columns(2)
        with c1: 
            ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2", "自定义像素"]
            aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts)
            custom_size = ""
            if aspect_ratio == "自定义像素":
                custom_size = st.text_input("输入像素值 (例如: 1024x1024)", placeholder="WxH")
        with c2: quality = st.selectbox("💎 图片质量", ["auto", "high", "medium", "low"])
        btn_submit = st.button("✨ 立即生成", type="primary", use_container_width=True)
        
    else: 
        st.markdown("#### 🖼️ 图生图模式")
        uploaded_files = st.file_uploader("📤 上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if uploaded_files:
            cols = st.columns(6) 
            for i, file in enumerate(uploaded_files):
                img_preview = Image.open(io.BytesIO(file.getvalue()))
                cols[i % 6].image(img_preview, caption=f"图 {i+1}", use_container_width=True)
        
        canvas_result = None
        if not uploaded_files:
            canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", stroke_width=3, background_color="#fff", height=300, key="cvs")
            
        prompt_txt = st.text_area("指令/修改描述", height=80)
        btn_submit = st.button("🚀 开始垫图生成", type="primary", use_container_width=True)

    if btn_submit:
        required_points = MODEL_COSTS.get(selected_model, 600)
        if current_balance < required_points: 
            st.error(f"❌ 额度不足，当前模型需要 {required_points} 积分。")
        elif not prompt_txt and menu == "✍️ 文生图": st.error("❌ 请输入提示词！")
        else:
            final_ratio = custom_size if aspect_ratio == "自定义像素" else aspect_ratio
            payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
            
            if menu == "🖼️ 图生图":
                urls = []
                if uploaded_files:
                    for f in uploaded_files: urls.append(pil_to_data_uri(Image.open(io.BytesIO(f.getvalue()))))
                elif canvas_result and canvas_result.image_data is not None:
                    urls.append(pil_to_data_uri(Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')))
                
                if not urls: st.error("⚠️ 请提供参考图。"); st.stop()
                payload["urls"] = urls
            else:
                payload["aspectRatio"] = final_ratio
                payload["quality"] = quality

            headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
            
            sub_res = None
            try:
                sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
            except Exception as e:
                st.error("📡 网络连接异常，无法发起任务，请检查网络或稍后重试。")
                
            if sub_res:
                if sub_res.get("code") == 0:
                    tz = pytz.timezone('Asia/Shanghai')
                    china_time_str = datetime.now(tz).strftime("%H:%M")
                    add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": china_time_str, "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model, "is_deducted": False}, user_key)
                    st.success("🎉 任务已提交云端！")
                    time.sleep(0.5)
                    st.rerun() 
                else: 
                    st.error(f"❌ 发起失败：{sub_res.get('msg')}")

with col_history:
    st.markdown("### 🗂️ 创作记录")
    tasks_list = clean_and_get_tasks(user_key)
    if not tasks_list:
        st.caption("暂无记录。")
    else:
        # 🌟 修复：多任务进度并行展示区域 (顶部显示所有进行中的任务进度)
        running_tasks = [t for t in reversed(tasks_list) if t.get('status') == 'running']
        if running_tasks:
            st.markdown("##### ⏳ 正在并行处理任务")
            for r_item in running_tasks:
                st.markdown(f"`{r_item['time_str']}` 💡 {r_item['prompt'][:10] + '...' if len(r_item['prompt']) > 10 else r_item['prompt']}")
                auto_poll_task(r_item['task_id'], user_key, r_item.get('model', 'gpt-image-2'), r_item['timestamp'])
                st.divider()

        # 底部最多只展示 10 条历史记录，并排好倒序序号
        total_items_count = len(tasks_list)
        st.markdown("##### 📜 历史完成记录")
        with st.container(height=700):
            for index, item in enumerate(reversed(tasks_list)):
                if item.get('status') != 'running':
                    current_idx = total_items_count - index
                    model_used_badge = "👑 VIP" if item.get('model') == 'gpt-image-2-vip' else "普"
                    prompt_text = item.get('prompt', '')
                    short_prompt = prompt_text[:10] + "..." if len(prompt_text) > 10 else prompt_text
                    
                    st.markdown(f"**[{current_idx}]** **[{item['time_str']}]** `{model_used_badge}` 💡 {short_prompt}")
                    
                    with st.expander("📋 展开复制完整提示词"):
                        st.code(prompt_text, language="text")
                        
                    if item.get('status') == 'succeeded':
                        urls = item.get('urls', [])
                        for idx, url in enumerate(urls):
                            if url:
                                modal_id = f"modal_{item['task_id']}_{idx}"
                                html_content = f"""
                                <a href="#{modal_id}" title="点击放大">
                                    <img src="{url}" class="result-thumb">
                                </a>
                                <a href="#" class="img-modal-overlay" id="{modal_id}">
                                    <img src="{url}">
                                </a>
                                """
                                st.markdown(html_content, unsafe_allow_html=True)
                    elif item.get('status') == 'failed': 
                        fail_msg = item.get('reason', '触发安全审查或云端接口异常')
                        st.error(f"❌ 失败原因: {fail_msg}")
                        
                    st.divider()
