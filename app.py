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
st.set_page_config(page_title="AI Pro 商业创作站", page_icon="🚀", layout="wide")

st.markdown("""
<style>
    /* 移动端 (手机) 深度适配 */
    @media (max-width: 768px) {
        .block-container { padding: 1rem 0.5rem !important; }
        .stButton > button { width: 100% !important; padding: 12px !important; font-size: 16px !important; border-radius: 12px !important; }
        h1 { font-size: 22px !important; }
        .stTextArea textarea { font-size: 14px !important; }
        /* 预览图在手机上两两排列 */
        [data-testid="stHorizontalBlock"] > div { min-width: 45% !important; }
    }
    /* PC端美化 */
    .stButton > button { border-radius: 8px; font-weight: bold; transition: all 0.3s; }
    [data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #eee; }
    .stProgress > div > div > div > div { background-color: #00c2ff; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 云端数据库连接 (Supabase)
# ==========================================
try:
    # 提醒：请确保在 Streamlit Cloud 的 Secrets 中配置了以下两项
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("❌ 数据库连接配置缺失，请检查 Secrets。")
    st.stop()

# 数据库操作函数
def get_card_data(card_key):
    try:
        res = supabase.table("user_cards").select("*").eq("card_key", card_key).eq("is_active", True).execute()
        return res.data[0] if res.data else None
    except:
        return None

def update_db_used_points(card_key, amount):
    try:
        res = supabase.table("user_cards").select("used_points").eq("card_key", card_key).execute()
        if res.data:
            new_val = res.data[0]['used_points'] + amount
            supabase.table("user_cards").update({"used_points": new_val}).eq("card_key", card_key).execute()
    except:
        pass

# ==========================================
# 2. 身份验证逻辑 (支持记住密码)
# ==========================================
st.sidebar.markdown("### 🪪 身份验证")
# 从 URL 获取 key 参数
query_key = st.query_params.get("key", "")
user_key = st.sidebar.text_input("🔑 激活码", value=query_key, type="password", placeholder="输入激活码解锁...")

if user_key:
    card_info = get_card_data(user_key)
    if not card_info:
        st.sidebar.error("❌ 激活码无效或已停用")
        st.stop()
    else:
        # 将激活码写入 URL，方便用户收藏网址免密登录
        st.query_params["key"] = user_key 
        balance = card_info['total_points'] - card_info['used_points']
        st.session_state.active_user_key = user_key
        st.session_state.current_balance = balance
else:
    st.sidebar.info("💡 提示：输入正确激活码并收藏本页，下次可免密登录。")
    st.stop()

# 计费标准
IMAGE_COST = 600
rem_imgs = int(st.session_state.current_balance // IMAGE_COST)
st.sidebar.markdown(f"剩余额度: <span style='color:#00c2ff; font-weight:bold; font-size:22px;'>{rem_imgs}</span> 张", unsafe_allow_html=True)
st.sidebar.divider()
menu = st.sidebar.radio("功能切换", ["✍️ 文生图", "🖼️ 图生图"])

# ==========================================
# 3. 核心 API 交互与进度展示 (兼容版)
# ==========================================
API_KEY = st.secrets.get("API_VIP", "") 

def submit_task(payload):
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
    return res

def poll_progress(task_id, prompt_txt):
    # 使用占位符容器，解决某些版本不支持弹窗的问题
    status_placeholder = st.empty()
    with status_placeholder.container():
        st.markdown("---")
        st.markdown(f"### 🎨 正在绘制中...\n**指令:** `{prompt_txt}`")
        progress_bar = st.progress(0)
        info_text = st.empty()
        
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    for i in range(40):
        try:
            r = requests.post("https://grsai.dakka.com.cn/v1/draw/result", headers=headers, json={"id": task_id}, verify=False).json()
            if r.get("code") == 0:
                data = r["data"]
                if data["status"] == "succeeded":
                    progress_bar.progress(100)
                    update_db_used_points(st.session_state.active_user_key, IMAGE_COST)
                    info_text.success("✅ 生成成功！已自动扣除 1 张额度。")
                    st.image(data["results"][0]["url"])
                    time.sleep(2)
                    st.rerun()
                elif data["status"] == "failed":
                    info_text.error(f"❌ 任务失败: {data.get('failure_reason')}")
                    break
            # 模拟进度走动
            progress_bar.progress(min(10 + i * 2, 95))
        except:
            pass
        time.sleep(4)

def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode != 'RGB': img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"

# ==========================================
# 4. 主界面交互
# ==========================================
st.title("🚀 AI Pro 商业创作站")

if menu == "✍️ 文生图":
    st.markdown("#### 📝 描述词生图")
    prompt = st.text_area("描述你想看到的画面...", height=150, placeholder="例如：赛博朋克风格的繁华都市，雨夜，霓虹灯倒影...")
    ratio = st.selectbox("画幅比例", ["1:1", "16:9", "9:16", "3:4", "4:3"])
    if st.button("✨ 开始生成", type="primary", use_container_width=True):
        if st.session_state.current_balance < IMAGE_COST:
            st.error("余额不足，请联系管理员充值。")
        elif not prompt:
            st.warning("请输入描述词。")
        else:
            res = submit_task({"model": "gpt-image-2", "prompt": prompt, "aspectRatio": ratio, "shutProgress": True})
            if res.get("code") == 0:
                poll_progress(res["data"]["id"], prompt)
            else:
                st.error(f"任务提交失败: {res.get('msg')}")

else: # 图生图
    st.markdown("#### 🖼️ 以图生图")
    uploaded_files = st.file_uploader("上传参考图 (支持多选)", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    # 🌟 预览图展示逻辑
    if uploaded_files:
        st.markdown("###### 👁️ 已上传的参考图")
        num_cols = min(len(uploaded_files), 4)
        cols = st.columns(num_cols)
        for i, file in enumerate(uploaded_files):
            col_idx = i % num_cols
            try:
                img_prev = Image.open(io.BytesIO(file.getvalue()))
                cols[col_idx].image(img_prev, caption=f"图 {i+1}", use_container_width=True)
            except:
                pass

    prompt = st.text_area("修改描述 (可选，若不填则保持原图风格)", placeholder="例如：把背景换成森林，增加阳光感...")
    
    if st.button("🚀 垫图生成", type="primary", use_container_width=True):
        if st.session_state.current_balance < IMAGE_COST:
            st.error("余额不足。")
        elif not uploaded_files:
            st.warning("请先上传参考图。")
        else:
            urls_list = []
            for file in uploaded_files:
                try:
                    urls_list.append(pil_to_data_uri(Image.open(io.BytesIO(file.getvalue()))))
                except:
                    pass
            
            payload = {
                "model": "gpt-image-2", 
                "prompt": prompt if prompt else "保持原图风格", 
                "urls": urls_list,
                "shutProgress": True
            }
            res = submit_task(payload)
            if res.get("code") == 0:
                poll_progress(res["data"]["id"], prompt if prompt else "图生图模式")
            else:
                st.error(f"接口报错: {res.get('msg')}")
