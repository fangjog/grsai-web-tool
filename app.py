import streamlit as st
import requests
import time
from PIL import Image
import io
import base64
from datetime import datetime
from streamlit_drawable_canvas import st_canvas

# ==========================================
# 1. 基础配置与安全密钥读取
# ==========================================
try:
    GRSAI_API_KEY = st.secrets["GRSAI_API_KEY"]
except:
    st.error("⚠️ 请先在 Streamlit 后台的 Settings -> Secrets 中配置 GRSAI_API_KEY")
    st.stop()

VALID_KEYS = ["vip888", "test1234"]

# 【修改点】网页标签栏名称极简
st.set_page_config(page_title="image-2 V2", page_icon="🎨", layout="wide")

# ==========================================
# 2. 历史记录系统 (1小时有效期，最多10条)
# ==========================================
if 'history' not in st.session_state:
    st.session_state.history = []

def clean_and_get_history():
    current_time = time.time()
    valid_history = [item for item in st.session_state.history if (current_time - item['timestamp']) < 3600]
    st.session_state.history = valid_history[-10:]
    return st.session_state.history

# ==========================================
# 3. 图像处理辅助函数 (转为 Base64 Data URI)
# ==========================================
def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    img.save(buffered, format="JPEG")
    base64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{base64_str}"

# ==========================================
# 4. 前端网页 UI 布局
# ==========================================
# 【修改点】主标题极简
st.title("🚀 image-2 V2")

st.sidebar.markdown("### 身份验证")
user_key = st.sidebar.text_input("🔑 请输入激活码/卡密", type="password")

if user_key not in VALID_KEYS:
    st.warning("👈 请在左侧输入有效的激活码以解锁系统。")
    st.stop()
st.sidebar.success("✅ 验证通过，欢迎使用！")

col_main, col_history = st.columns([7, 3])

with col_main:
    tab1, tab2 = st.tabs(["✍️ 文生图", "🖌️ 画板与图生图"])

    with tab1:
        st.markdown("#### 📝 输入描述直接生成画面")
        prompt_txt = st.text_area("画面详细描述 (支持中文直出)", height=120, key="txt2img_prompt")
        
        col1_1, col1_2 = st.columns(2)
        with col1_1:
            aspect_ratio_txt = st.selectbox("📏 画幅比例", ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "auto"], key="txt_ratio")
        with col1_2:
            quality_txt = st.selectbox("💎 图片质量", ["auto", "high", "medium", "low"], key="txt_quality")
            
        btn_txt2img = st.button("✨ 立即生成 (文生图)")

    with tab2:
        st.markdown("#### 🖌️ 上传底图或在下方画布涂鸦")
        bg_image = st.file_uploader("1. 可选：上传一张参考图作为背景", type=["png", "jpg", "jpeg"])
        
        # 处理底图，防止超大尺寸图片卡死画板
        canvas_bg = None
        if bg_image:
            try:
                canvas_bg = Image.open(bg_image)
                canvas_bg.thumbnail((1024, 1024)) # 限制最大尺寸
            except Exception as e:
                st.error("图片读取失败，请换一张图片尝试。")

        st.caption("在下方区域使用鼠标绘制内容，它将作为垫图参考：")
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)", 
            stroke_width=3,
            stroke_color="#000000",
            background_image=canvas_bg,
            update_streamlit=True,
            height=400,
            drawing_mode="freedraw",
            key="canvas",
        )
        
        prompt_img = st.text_area("2. 画面描述 (修改指令或最终画面描述)", height=80, key="img2img_prompt")
        btn_img2img = st.button("✨ 立即生成 (图生图)")

    # ==========================================
    # 5. 核心 API 交互与请求逻辑
    # ==========================================
    if btn_txt2img or btn_img2img:
        mode = "txt2img" if btn_txt2img else "img2img"
        current_prompt = prompt_txt if mode == "txt2img" else prompt_img
        
        if not current_prompt:
            st.error("❌ 提示词描述不能为空！")
        else:
            status_text = st.empty()
            progress_bar = st.progress(0)
            status_text.info("📡 正在封装数据提交给服务器...")
            
            payload = {
                "model": "gpt-image-2",
                "prompt": current_prompt,
                "webHook": "-1",
                "shutProgress": True
            }
            
            if mode == "img2img":
                if canvas_result.image_data is not None:
                    canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    data_uri = pil_to_data_uri(canvas_pil)
                    payload["urls"] = [data_uri] 
            else:
                payload["aspectRatio"] = aspect_ratio_txt
                payload["quality"] = quality_txt

            headers = {
                "Authorization": f"Bearer {GRSAI_API_KEY}",
                "Content-Type": "application/json"
            }
            submit_url = "https://grsai.dakka.com.cn/v1/draw/completions"
            
            try:
                sub_res = requests.post(submit_url, headers=headers, json=payload, verify=False).json()
                
                if sub_res.get("code") == 0:
                    task_id = sub_res["data"]["id"]
                    status_text.warning("⏳ 任务提交成功，云端作画中...")
                    progress_bar.progress(20)
                    
                    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
                    
                    for i in range(40):
                        time.sleep(3)
                        progress_bar.progress(min(20 + i*2, 95))
                        
                        q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
                        
                        if q_res.get("code") == 0:
                            status = q_res["data"]["status"]
                            
                            if status == "succeeded":
                                img_url = q_res["data"]["results"][0]["url"]
                                status_text.success("✅ 图片生成完毕！")
                                progress_bar.progress(100)
                                
                                img_data = requests.get(img_url, verify=False).content
                                final_image = Image.open(io.BytesIO(img_data))
                                st.image(final_image, caption="AI 生成结果")
                                st.download_button(label="💾 下载高清原图", data=img_data, file_name=f"AI_Draw_{task_id}.jpg", mime="image/jpeg")
                                
                                st.session_state.history.append({
                                    "timestamp": time.time(),
                                    "time_str": datetime.now().strftime("%H:%M:%S"),
                                    "prompt": current_prompt,
                                    "url": img_url
                                })
                                break
                            elif status == "failed":
                                reason = q_res["data"].get("failure_reason", "未知")
                                error_msg = q_res["data"].get("error", "")
                                status_text.error(f"❌ 生成失败！原因: {reason} - {error_msg}")
                                break
                else:
                    status_text.error(f"⚠️ 提交接口报错：{sub_res.get('msg', sub_res)}")
            except Exception as e:
                status_text.error(f"❌ 网络或系统异常：{e}")

# ==========================================
# 6. 右侧画廊：历史记录面板
# ==========================================
with col_history:
    st.markdown("### 🕰️ 生成历史")
    st.caption("记录保留1小时内最新的10条。")
    
    history_list = clean_and_get_history()
    
    if not history_list:
        st.info("💡 暂无历史记录。")
    else:
        for item in reversed(history_list):
            with st.container():
                st.markdown(f"**[{item['time_str']}]**")
                short_prompt = item['prompt'][:20] + "..." if len(item['prompt']) > 20 else item['prompt']
                st.caption(f"✍️ {short_prompt}")
                st.image(item['url'], use_container_width=True)
                st.divider()
