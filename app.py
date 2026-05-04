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

# ==========================================
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI Pro Studio V6.11", page_icon="🚀", layout="wide", initial_sidebar_state="auto")

st.markdown("""
<style>
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.5rem !important; }
        h1 { font-size: 24px !important; }
        .stButton > button { width: 100% !important; padding: 15px !important; font-size: 16px !important; border-radius: 12px !important; }
        footer { visibility: hidden; }
    }
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    [data-testid="stHorizontalBlock"] > div { min-width: 80px !important; }
    
    /* 🌟 核心 V6.9 修复：让所有原生图片都拥有高级悬浮特效，同时保留其原生的原网页遮罩全屏放大功能 🌟 */
    [data-testid="stImage"] img {
        border-radius: 8px !important;
        transition: transform 0.2s ease-in-out !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1) !important;
        cursor: zoom-in !important; /* 点击原网页放大观感 */
    }
    [data-testid="stImage"]:hover img {
        transform: scale(1.02) !important;
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
    st.error("❌ 数据库连接失败，请检查 Secrets 配置。")
    st.stop()

# V6.5 动态模型定价表
MODEL_COSTS = {
    "gpt-image-2": 600,
    "gpt-image-2-vip": 900
}

TASKS_FILE = "tasks_history.json"

def load_json(path, default={default={}}):
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
        res = supabase.table("user_cards").select("used_points").eq("card_key", card_key).execute()
        if res.data:
            new_val = res.data[0]['used_points'] + amount
            supabase.table("user_cards").update({"used_points": new_val}).eq("card_key", card_key).execute()
    except: pass

# ==========================================
# 2. 居中拦截式身份验证 (V6.2)
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
            check_info = get_card_info(user_key)
            if check_info:
                st.query_params["key"] = user_key
                st.rerun()
            else: st.error("❌ 激活码无效。")
    st.stop() 

user_key = query_key
current_balance = card_info['total_points'] - card_info['used_points']
clean_api_name = (card_info.get('api_secret_name') or "API_VIP888").strip("'").strip()
GRSAI_API_KEY = st.secrets.get(clean_api_name, "")

# ==========================================
# 3. 任务队列隔离 (V6.3)
# ==========================================
all_history = load_json(TASKS_FILE, default={})
if isinstance(all_history, list): all_history = {}
if 'tasks' not in st.session_state: st.session_state.tasks = all_history.get(user_key, [])

def clean_and_get_tasks(active_key):
    curr_time = time.time()
    valid = [t for t in st.session_state.tasks if (curr_time - t['timestamp']) < 3600]
    valid = valid[-10:]
    st.session_state.tasks = valid
    global_history = load_json(TASKS_FILE, default={})
    if isinstance(global_history, list): global_history = {}
    global_history[active_key] = valid
    save_json(TASKS_FILE, global_history)
    return valid

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
# V6.10 自动轮询 + 时间锚定充电条 (修复跳来跳去)
# ==========================================
def auto_poll_task(task_id, active_user_key, model_used, start_time):
    placeholder = st.empty()
    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
    cost_per_img = MODEL_COSTS.get(model_used, 600)
    
    for i in range(40):
        # 🌟 V6.10 修复 1：根据任务真实的已消耗时间来计算进度，彻底杜绝刷新回退跳乱跳！
        elapsed_time = time.time() - start_time
        p = min(5 + int(elapsed_time), 95) # 起步5%，每过1秒涨1%，最高停在95%
        
        html_bar = f"""<div style="background-color: #1a1a1a; border-radius: 10px; padding: 4px; box-shadow: inset 0 1px 3px rgba(0,0,0,0.5); border: 1px solid #333;"><div style="height: 14px; border-radius: 6px; background: linear-gradient(90deg, #00c2ff, #00ffd5); width: {p}%; transition: width 0.5s ease-in-out; box-shadow: 0 0 10px #00ffd5;"></div></div><div style="text-align: right; color: #00ffd5; font-size: 13px; font-weight: bold; margin-top: 6px; font-family: monospace;">⚡ 云端算力注入中... {p}%</div>"""
        placeholder.markdown(html_bar, unsafe_allow_html=True)
        
        try:
            q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
            if q_res.get("code") == 0:
                status = q_res["data"]["status"]
                if status == "succeeded":
                    progress_bar_reset_css = """<style>[data-testid="stMarkdownContainer"] [data-testid="stMarkdownContainer"] div { background-color: transparent !important; }</style>"""
                    results = q_res["data"]["results"]
                    urls = [img["url"] for img in results]
                    
                    # V6.10 修复 2：在绿色框渲染原图前，先把充电条也换成绿色充满状态
                    html_bar_succeeded = html_bar.replace(f"width: {p}%", "width: 100%").replace(f"{p}%", "100%").replace("background: linear-gradient(90deg, #00c2ff, #00ffd5)", "background: linear-gradient(90deg, #00ff88, #00c2ff)").replace("#00c2ff", "#00ff88").replace("云端算力注入中...", "✅ 绘制完成！").replace("box-shadow: 0 0 10px #00ffd5;", "box-shadow: 0 0 10px #00ff88;")
                    # 瞬间渲染绿色荧光边框原图，零延迟
                    imgs_html = "".join([f'<img src="{url}" class="result-thumb" style="border: 2px solid #00ff88; box-shadow: 0 0 20px rgba(0,255,136,0.2); transition: scale(1.02);">' for url in urls])
                    
                    # 瞬间充满
                    placeholder.markdown(f"{progress_bar_reset_css}{html_bar_succeeded}{imgs_html}", unsafe_allow_html=True)
                    
                    # 动态阶梯扣费
                    num_images = len(results)
                    total_cost = num_images * cost_per_img
                    deduct_balance(active_user_key, total_cost)
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id:
                            # V6.7 防重扣安全锁
                            t['status'] = 'succeeded'
                            t['urls'] = urls
                            t['is_deducted'] = True # 标记已扣款
                    clean_and_get_tasks(active_user_key)
                    
                    time.sleep(1.5) # 酷炫效果看清 1.5 秒
                    st.rerun()
                    return 
                    
                elif status == "failed":
                    # V6.6 智能错误捕获与自动翻译拦截器
                    raw_reason = q_res["data"].get("failure_reason", "")
                    raw_error = q_res["data"].get("error", "")
                    actual_err = raw_error if raw_error and raw_error != "error" else raw_reason
                    
                    error_dict = {
                        "The current model has a high load, please use another model": "当前模型并发排队拥挤，请稍后再试，或切换至 VIP 模型",
                        "We are sorry, but the images we created may have violated our relevant policies. If you think we made a mistake, please try again or edit your prompt.": "❌ 触发安全审查：生成的内容疑似包含违禁元素，请修改提示词后重试",
                        "error": "云端生成异常或触发安全审查，请调整提示词"
                    }
                    cn_error = error_dict.get(actual_err, f"系统异常: {actual_err}")
                    
                    for t in st.session_state.tasks:
                        if t['task_id'] == task_id: 
                            t['status'] = 'failed'
                            t['reason'] = cn_error # 把翻译后的中文原因存入历史记录
                    clean_and_get_tasks(active_user_key)
                    st.rerun()
        except: pass
        time.sleep(3)
        
    # 如果超时了
    for t in st.session_state.tasks:
        if t['task_id'] == task_id and t['status'] == 'running':
            t['status'] = 'failed'
            t['reason'] = "请求超时，请检查网络或稍后重试"
    clean_and_get_tasks(active_user_key)
    st.rerun()

# ==========================================
# 4. 主界面
# ==========================================
st.sidebar.markdown(f'### 👤 用户中心\n当前用户: `{user_key}`')
st.sidebar.markdown(f'剩余积分: <span style="color:#00c2ff; font-weight:bold; font-size:24px;">{current_balance}</span>', unsafe_allow_html=True)
st.sidebar.markdown(f'<div style="font-size:13px; color:#666;">标准模式约制 <b style="color:#333;">{current_balance//600}</b> 张<br>VIP 模式约制 <b style="color:#333;">{current_balance//900}</b> 张</div>', unsafe_allow_html=True)

if st.sidebar.button("🚪 退出登录", use_container_width=True):
    st.query_params.clear()
    if 'tasks' in st.session_state: del st.session_state.tasks
    st.rerun()
    
st.sidebar.divider()
menu = st.sidebar.radio("功能导航", ["✍️ 文生图", "🖼️ 图生图"])

st.title("🚀 AI Pro Studio")
col_main, col_history = st.columns([7, 3])

with col_main:
    # V6.4 模型切换功能
    selected_model = st.selectbox("🤖 选择创作模型", ["gpt-image-2", "gpt-image-2-vip"], help="VIP模型支持更高分辨率和更强细节")
    
    if menu == "✍️ 文生图":
        prompt_txt = st.text_area("输入画面详细描述", height=120, placeholder="赛博朋克繁华都市，雨夜，霓虹灯...")
        c1, c2 = st.columns(2)
        with c1: 
            # V6.4 画幅比例升级
            ratio_opts = ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "5:4", "4:5", "4:3", "3:4", "21:9", "9:21", "1:3", "3:1", "2:1", "1:2", "自定义像素"]
            aspect_ratio = st.selectbox("📏 画幅比例", ratio_opts)
            custom_size = ""
            if aspect_ratio == "自定义像素":
                custom_size = st.text_input("输入像素值 (例如: 1024x1024)", placeholder="WxH")
        with c2: quality = st.selectbox("💎 图片质量", quality_opts := ["auto", "high", "medium", "low"], key="quality_v")
        btn_submit = st.button("✨ 立即生成", type="primary", use_container_width=True)
        
    else: 
        st.markdown("#### 🖼️ 图生图模式")
        uploaded_files = st.file_uploader("📤 上传参考图", type=["png", "jpg"], accept_multiple_files=True)
        if uploaded_files:
            st.markdown("<p style='font-size:14px; color:#666;'>👁️ 已选参考图预览：</p>", unsafe_allow_html=True)
            cols = st.columns(6) 
            for i, file in enumerate(uploaded_files):
                img_preview = Image.open(io.BytesIO(file.getvalue()))
                # V6.9 修复 Bug：统一用全局 CSS 控制的原生图片组件，解决放大体验冲突
                cols[i % 6].image(img_preview, caption=f"图 {i+1}", use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
        
        canvas_result = None
        if not uploaded_files:
            st.info("💡 提示：在下方涂鸦也可作为生成参考。")
            canvas_result = st_canvas(fill_color="rgba(255,165,0,0.3)", stroke_width=3, stroke_color="#000", background_color="#fff", height=300, key="cvs")
            
        prompt_txt = st.text_area("指令/修改描述", height=80, placeholder="保持风格，背景换成森林...")
        with st.columns(2)[0]: quality = st.selectbox("💎 图片质量", quality_opts, key="quality_i")
        btn_submit = st.button("🚀 开始垫图生成", type="primary", use_container_width=True)

    if btn_submit:
        required_points = MODEL_COSTS.get(selected_model, 600)
        if current_balance < required_points: 
            st.error(f"❌ 额度不足，当前模型需要 {required_points} 积分。")
        elif not prompt_txt and menu == "✍️ 文生图": st.error("❌ 请输入提示词！")
        else:
            payload = {"model": selected_model, "prompt": prompt_txt, "webHook": "-1", "shutProgress": True}
            
            # 🌟 V6.10 修复 Bug：严格隔离图生图逻辑，防止 aspectRatio 未定义
            if menu == "🖼️ 图生图":
                urls = []
                if uploaded_files:
                    for f in uploaded_files: urls.append(pil_to_data_uri(Image.open(io.BytesIO(f.getvalue()))))
                elif canvas_result and canvas_result.image_data is not None:
                    urls.append(pil_to_data_uri(Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')))
                
                if not urls: st.error("⚠️ 请提供参考图。"); st.stop()
                payload["urls"] = urls
                payload["quality"] = quality
            else:
                # 文生图专有逻辑
                final_ratio = custom_size if aspect_ratio == "自定义像素" else aspect_ratio
                payload["aspectRatio"] = final_ratio
                payload["quality"] = quality

            headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
            
            # 🌟 V6.10 修复 Bug：将网络请求与页面刷新彻底分离，防止 rerun() 被 except 拦截误报异常
            sub_res = None
            try:
                sub_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
            except Exception as e:
                # 📡 V6.10 修复：只有连不上网时才显示，rerunException 不会到这里
                st.error("📡 网络连接异常，无法发起任务，请检查网络环境或稍后重试。")
                
            if sub_res:
                if sub_res.get("code") == 0:
                    add_task({"task_id": sub_res["data"]["id"], "timestamp": time.time(), "time_str": datetime.now().strftime("%H:%M"), "prompt": prompt_txt, "status": "running", "urls": [], "model": selected_model, "is_deducted": False}, user_key)
                    st.success("🎉 任务已提交云端！")
                    time.sleep(0.5)
                    st.rerun() 
                else: 
                    st.error(f"❌ 发起失败：{sub_res.get('msg')}")

with col_history:
    st.markdown("### 🗂️ 创作记录")
    tasks_list = clean_and_get_tasks(user_key)
    if not tasks_list: st.caption("暂无记录。")
    else:
        with st.container(height=700):
            for item in reversed(tasks_list):
                # V6.8 截断提示词+复制功能
                model_used_badge = "👑 VIP" if item.get('model') == 'gpt-image-2-vip' else "普"
                prompt_text = item.get('prompt', '')
                short_prompt = prompt_text[:10] + "..." if len(prompt_text) > 10 else prompt_text
                
                # 时间+模型+截断提示词
                st.markdown(f"**[{item['time_str']}]** `{model_used_badge}` 💡 {short_prompt}")
                
                with st.expander("📋 展开复制完整提示词"):
                    st.code(prompt_text, language="text")

                if item.get('status') == 'running':
                    # 🌟 V6.10 修复 Bug：只要状态是 running，刷新后自动重新轮询
                    auto_poll_task(item['task_id'], user_key, item.get('model', 'gpt-image-2'), item['timestamp'])
                    
                elif item.get('status') == 'succeeded':
                    for url in item.get('urls', []):
                        # V6.9 修复 Bug：换回原生 st.image，利用全局 CSS 控制悬浮和原网页内放大
                        st.image(url, use_container_width=True)
                        
                elif item.get('status') == 'failed': 
                    fail_msg = item.get('reason', '触发安全审查或云端接口异常')
                    # V6.8 失败原因
                    st.error(f"❌ 失败原因: {fail_msg}")
                    
                st.divider()
