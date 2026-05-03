import streamlit as st
import requests
import time
from PIL import Image
import io
import base64
from datetime import datetime
from streamlit_drawable_canvas import st_canvas

# 1. 基础配置与密钥 (已改为自动读取保险箱)
try:
    GRSAI_API_KEY = st.secrets["GRSAI_API_KEY"]
except:
    st.error("请先在 Streamlit 后台 Secrets 配置 GRSAI_API_KEY")
    st.stop()

VALID_KEYS = ["vip888", "test1234"]

st.set_page_config(page_title="AI 极速分镜生成器 V2", page_icon="🎨", layout="wide")

# 2. 历史记录初始化 (使用 session_state，刷新页面或过时后消失)
if 'history' not in st.session_state:
    st.session_state.history = []

def clean_and_get_history():
    """清理过期历史（1小时=3600秒），并确保最多只留10条"""
    current_time = time.time()
    # 过滤掉超过1小时的记录
    valid_history = [item for item in st.session_state.history if (current_time - item['timestamp']) < 3600]
    # 保留最新的10条
    st.session_state.history = valid_history[-10:]
    return st.session_state.history

# 3. 辅助函数：将图片转为Base64供API读取
def pil_to_base64(img):
    buffered = io.BytesIO()
    # 如果是RGBA模式（画布默认），转为RGB防止API报错
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# --- 界面渲染开始 ---
st.title("🚀 爆款信息流分镜生成器 V2")

# 登录验证
user_key = st.sidebar.text_input("🔑 请输入激活码/卡密", type="password")
if user_key not in VALID_KEYS:
    st.warning("👈 请在左侧侧边栏输入有效的激活码以使用系统。")
    st.stop()
st.sidebar.success("✅ 验证通过！")

# 页面布局：左侧主功能，右侧历史记录
col_main, col_history = st.columns([7, 3])

with col_main:
    # 建立标签页
    tab1, tab2 = st.tabs(["✍️ 文生图", "🖌️ 画布 / 图生图"])

    with tab1:
        st.markdown("### 📝 输入描述生成画面")
        prompt_txt = st.text_area("画面描述 (支持中文)", height=150, key="txt2img_prompt")
        aspect_ratio_txt = st.selectbox("📏 画幅比例", ["16:9", "9:16", "1:1", "3:4", "4:3"], key="txt2img_ratio")
        btn_txt2img = st.button("✨ 立即生成 (文生图)")

    with tab2:
        st.markdown("### 🖌️ 上传底图或在画布上涂鸦")
        bg_image = st.file_uploader("1. 可选：上传一张参考底图 (背景)", type=["png", "jpg", "jpeg"])
        
        # 渲染画布
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)", 
            stroke_width=3,
            stroke_color="#000000",
            background_image=Image.open(bg_image) if bg_image else None,
            update_streamlit=True,
            height=400,
            drawing_mode="freedraw",
            key="canvas",
        )
        
        prompt_img = st.text_area("2. 画面描述 (需要变成什么样)", height=100, key="img2img_prompt")
        btn_img2img = st.button("✨ 立即生成 (图生图)")

    # --- 统一的生成逻辑 ---
    if btn_txt2img or btn_img2img:
        mode = "txt2img" if btn_txt2img else "img2img"
        current_prompt = prompt_txt if mode == "txt2img" else prompt_img
        
        if not current_prompt:
            st.error("描述不能为空！")
        else:
            status_text = st.empty()
            progress_bar = st.progress(0)
            status_text.info("📡 正在向服务器提交任务...")
            
            # 构建基础 Payload
            payload = {
                "model": "gpt-image-2",
                "prompt": current_prompt,
                "webHook": "-1",
                "shutProgress": True
            }
            
            # 如果是图生图，提取画布图像转为 Base64
            if mode == "img2img":
                if canvas_result.image_data is not None:
                    # 画布输出的是 numpy 数组，需转为 PIL 图像
                    canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    img_base64 = pil_to_base64(canvas_pil)
                    
                    # ⚠️ 关键注意：这里的 "image" 字段需要根据 Grsai API 的官方文档进行核对！
                    # 有的平台叫 "init_image", 有的叫 "image", 有的叫 "base_image"
                    payload["image"] = img_base64 
            else:
                payload["aspectRatio"] = aspect_ratio_txt

            # 提交请求
            submit_url = "https://grsai.dakka.com.cn/v1/draw/completions"
            headers = {
                "Authorization": f"Bearer {GRSAI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            try:
                sub_res = requests.post(submit_url, headers=headers, json=payload, verify=False).json()
                if sub_res.get("code") == 0:
                    task_id = sub_res["data"]["id"]
                    
                    # 轮询查询结果
                    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
                    for i in range(30):
                        progress_bar.progress(min(10 + i*3, 90))
                        q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
                        
                        if q_res.get("code") == 0 and q_res["data"]["status"] == "succeeded":
                            img_url = q_res["data"]["results"][0]["url"]
                            status_text.success("✅ 图片生成完毕！")
                            progress_bar.progress(100)
                            
                            # 展示大图
                            img_data = requests.get(img_url, verify=False).content
                            final_image = Image.open(io.BytesIO(img_data))
                            st.image(final_image, caption="为您生成的画面")
                            st.download_button(label="💾 下载原图", data=img_data, file_name=f"{task_id}.jpg", mime="image/jpeg")
                            
                            # ✨ 写入历史记录
                            st.session_state.history.append({
                                "timestamp": time.time(),
                                "time_str": datetime.now().strftime("%H:%M:%S"),
                                "prompt": current_prompt,
                                "url": img_url
                            })
                            break
                        elif q_res.get("code") == 0 and q_res["data"]["status"] == "failed":
                            status_text.error("❌ 生成失败。")
                            break
                        time.sleep(3)
                else:
                    status_text.error(f"提交失败：{sub_res}")
            except Exception as e:
                status_text.error(f"网络错误：{e}")

# --- 右侧：历史记录面板 ---
with col_history:
    st.markdown("### 🕰️ 生成历史 (1小时内)")
    history_list = clean_and_get_history()
    
    if not history_list:
        st.info("暂无记录，快去生成第一张图吧！")
    else:
        # 倒序展示，最新的在最上面
        for item in reversed(history_list):
            st.markdown(f"**[{item['time_str']}]**")
            st.caption(f"_{item['prompt'][:20]}..._") # 提示词太长只截取前20个字
            st.image(item['url'], use_container_width=True)
            st.divider()
