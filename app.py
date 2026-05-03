# 文件名: app.py
import streamlit as st
import requests
import time
from PIL import Image
import io
import base64
from datetime import datetime
from supabase import create_client, Client

# ==========================================
# 0. 网页基础配置与移动端自适应 CSS
# ==========================================
st.set_page_config(page_title="AI Pro Studio 商业版", page_icon="🎨", layout="wide")

st.markdown("""
<style>
    /* 移动端 (手机) 深度适配 */
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.5rem !important; }
        .stButton > button { width: 100% !important; padding: 12px !important; font-size: 16px !important; border-radius: 12px !important; }
        h1 { font-size: 22px !important; }
        .stTextArea textarea { font-size: 14px !important; }
    }
    /* 侧边栏样式优化 */
    [data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    .stProgress > div > div > div > div { background-color: #00c2ff; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 云端数据库连接 (Supabase)
# ==========================================
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("❌ 数据库连接失败，请检查 Secrets 配置。")
    st.stop()

# 数据库操作函数
def get_card_data(card_key):
    res = supabase.table("user_cards").select("*").eq("card_key", card_key).eq("is_active", True).execute()
    return res.data[0] if res.data else None

def update_db_used_points(card_key, amount):
    res = supabase.table("user_cards").select("used_points").eq("card_key", card_key).execute()
    if res.data:
        new_val = res.data[0]['used_points'] + amount
        supabase.table("user_cards").update({"used_points": new_val}).eq("card_key", card_key).execute()

# ==========================================
# 2. 身份验证逻辑 (支持记住密码)
# ==========================================
st.sidebar.markdown("### 🪪 身份验证")
query_key = st.query_params.get("key", "")
user_key = st.sidebar.text_input("🔑 激活码", value=query_key, type="password", placeholder="输入激活码解锁...")

if user_key:
    card_info = get_card_data(user_key)
    if not card_info:
        st.sidebar.error("❌ 激活码无效或已停用")
        st.stop()
    else:
        st.query_params["key"] = user_key # 记住码到 URL
        balance = card_info['total_points'] - card_info['used_points']
        st.session_state.active_user_key = user_key
        st.session_state.current_balance = balance
else:
    st.sidebar.info("💡 提示：输入正确激活码并收藏本页，下次可免密登录。")
    st.stop()

# 显示余额
IMAGE_COST = 600
rem_imgs = int(st.session_state.current_balance // IMAGE_COST)
st.sidebar.markdown(f"剩余额度: <span style='color:#00c2ff; font-weight:bold; font-size:22px;'>{rem_imgs}</span> 张", unsafe_allow_html=True)
st.sidebar.divider()
menu = st.sidebar.radio("功能切换", ["✍️ 文生图", "🖼️ 图生图"])

# ==========================================
# 3. 核心 API 交互
# ==========================================
# 统一使用 API_VIP (之前建议的 secrets 命名)
API_KEY = st.secrets.get("API_VIP", "") 

def submit_task(payload):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
    return res

@st.experimental_dialog("🎨 正在绘制中...", width="large")
def poll_progress(task_id, prompt_txt):
    st.markdown(f"**任务描述:** `{prompt_txt}`")
    progress_bar = st.progress(0)
    status_msg = st.empty()
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    for _ in range(40):
        try:
            r = requests.post("https://grsai.dakka.com.cn/v1/draw/result", headers=headers, json={"id": task_id}, verify=False).json()
            if r.get("code") == 0:
                data = r["data"]
                if data["status"] == "succeeded":
                    progress_bar.progress(100)
                    # 🌟 关键：生成成功后扣除数据库积分
                    update_db_used_points(st.session_state.active_user_key, IMAGE_COST)
                    st.success("✅ 生成成功！已扣除 1 张额度。")
                    st.image(data["results"][0]["url"])
                    time.sleep(2)
                    st.rerun()
                elif data["status"] == "failed":
                    st.error(f"❌ 任务失败: {data.get('failure_reason')}")
                    break
            progress_bar.progress(30) # 模拟进度
        except: pass
        time.sleep(4)

# ==========================================
# 4. 主界面
# ==========================================
st.title("🚀 AI Pro 商业创作站")

if menu == "✍️ 文生图":
    prompt = st.text_area("输入创意指令", height=100)
    ratio = st.selectbox("画幅比例", ["1:1", "16:9", "9:16", "3:4", "4:3"])
    if st.button("✨ 开始生成", type="primary"):
        if st.session_state.current_balance < IMAGE_COST:
            st.error("余额不足，请联系管理员。")
        elif prompt:
            res = submit_task({"model": "gpt-image-2", "prompt": prompt, "aspectRatio": ratio, "shutProgress": True})
            if res.get("code") == 0:
                poll_progress(res["data"]["id"], prompt)
            else: st.error(res.get("msg"))

else: # 图生图
    uploaded = st.file_uploader("上传参考图", type=["jpg", "png"], accept_multiple_files=True)
    prompt = st.text_area("修改描述 (可选)")
    if st.button("🚀 垫图生成", type="primary"):
        if st.session_state.current_balance < IMAGE_COST:
            st.error("余额不足。")
        else:
            # 图片转 base64 逻辑... (同前)
            st.info("功能处理中...")
