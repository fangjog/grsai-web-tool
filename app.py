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

# ==========================================
# 0. 网页基础配置 (必须是第一句)
# ==========================================
st.set_page_config(page_title="image-2 V2", page_icon="🎨", layout="wide")

# ==========================================
# 1. 安全密钥读取
# ==========================================
try:
    GRSAI_API_KEY = st.secrets["GRSAI_API_KEY"]
except:
    st.error("⚠️ 请先在 Streamlit 后台的 Settings -> Secrets 中配置 GRSAI_API_KEY")
    st.stop()

VALID_KEYS = ["vip888", "test1234"]

# ==========================================
# 2. 异步任务与历史记录持久化系统
# ==========================================
HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history_list):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_list, f, ensure_ascii=False)
    except:
        pass

def clean_and_get_history():
    if 'history' not in st.session_state:
        st.session_state.history = load_history()
        
    current_time = time.time()
    # 过滤掉超过 3600 秒（1小时）的记录
    valid_history = [item for item in st.session_state.history if (current_time - item['timestamp']) < 3600]
    # 保留最近的 10 条
    valid_history = valid_history[-10:]
    
    if len(valid_history) != len(st.session_state.history):
        st.session_state.history = valid_history
        save_history(valid_history)
        
    return st.session_state.history

def add_history(item):
    history = clean_and_get_history()
    history.append(item)
    st.session_state.history = history
    save_history(history)

# ==========================================
# 3. 图像处理辅助函数
# ==========================================
def pil_to_data_uri(img):
    buffered = io.BytesIO()
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail((1024, 1024)) 
    img.save(buffered, format="JPEG")
    base64_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{base64_str}"

# ==========================================
# 4. 前端网页 UI 布局
# ==========================================
st.title("🚀 image-2 V2")

st.sidebar.markdown("### 身份验证")
user_key = st.sidebar.text_input("🔑 请输入激活码/卡密", type="password")

if user_key not in VALID_KEYS:
    st.warning("👈 请在左侧输入有效的激活码以解锁系统。")
    st.stop()
st.sidebar.success("✅ 验证通过，欢迎使用！")

# 左侧功能区 占7成， 右侧任务区 占3成
col_main, col_history = st.columns([7, 3])

with col_main:
    tab1, tab2 = st.tabs(["✍️ 文生图", "🖌️ 画布与图生图"])

    with tab1:
        st.markdown("#### 📝 输入描述直接生成画面")
        prompt_txt = st.text_area("画面详细描述 (支持中文直出)", height=120, key="txt2img_prompt")
        
        col1_1, col1_2 = st.columns(2)
        with col1_1:
            aspect_ratio_txt = st.selectbox("📏 画幅比例", ["16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3", "auto"], key="txt_ratio")
        with col1_2:
            quality_txt = st.selectbox("💎 图片质量", ["auto", "high", "medium", "low"], key="txt_quality")
            
        btn_txt2img = st.button("✨ 立即提交生成 (异步)")

    with tab2:
        st.markdown("#### 🖌️ 上传参考图或在下方画布涂鸦")
        
        uploaded_files = st.file_uploader("可选：上传参考图 (支持多选，第1张作为画布底图)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
        
        canvas_bg = None
        if uploaded_files:
            try:
                canvas_bg = Image.open(io.BytesIO(uploaded_files[0].getvalue()))
                canvas_bg.thumbnail((1024, 1024))
            except:
                pass
                
        if uploaded_files and len(uploaded_files) > 1:
            # 极简预览：只显示图1、图2，隐藏任何报错警告
            cols = st.columns(min(len(uploaded_files)-1, 5))
            for idx, file in enumerate(uploaded_files[1:]):
                with cols[idx % 5]:
                    try:
                        bytes_data = file.getvalue()
                        b64_str = base64.b64encode(bytes_data).decode("utf-8")
                        mime_type = file.type if file.type else "image/jpeg"
                        html_img = f'''
                        <div style="background: #f8f9fa; padding: 4px; border-radius: 6px; text-align: center;">
                            <span style="font-size: 12px; font-weight: bold; color: #666;">图{idx+1}</span><br>
                            <img src="data:{mime_type};base64,{b64_str}" style="height: 50px; border-radius: 4px; object-fit: cover;">
                        </div>
                        '''
                        st.markdown(html_img, unsafe_allow_html=True)
                    except:
                        pass 

        st.caption("在下方区域使用鼠标绘制内容，它将作为主垫图参考：")
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
        
        prompt_img = st.text_area("画面描述 (修改指令或最终画面描述)", height=80, key="img2img_prompt")
        btn_img2img = st.button("✨ 立即提交生成 (异步)")

    # ==========================================
    # 5. 核心 API 交互 (异步不阻塞逻辑)
    # ==========================================
    if btn_txt2img or btn_img2img:
        mode = "txt2img" if btn_txt2img else "img2img"
        current_prompt = prompt_txt if mode == "txt2img" else prompt_img
        
        if not current_prompt:
            st.error("❌ 提示词描述不能为空！")
        else:
            payload = {
                "model": "gpt-image-2",
                "prompt": current_prompt,
                "webHook": "-1",
                "shutProgress": True
            }
            
            if mode == "img2img":
                urls_list = []
                if canvas_result.image_data is not None:
                    canvas_pil = Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA')
                    urls_list.append(pil_to_data_uri(canvas_pil))
                
                if uploaded_files and len(uploaded_files) > 1:
                    for file in uploaded_files[1:]:
                        try:
                            img_extra = Image.open(io.BytesIO(file.getvalue()))
                            urls_list.append(pil_to_data_uri(img_extra))
                        except:
                            pass
                payload["urls"] = urls_list 
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
                    
                    # ✨ 核心：提交后不等待，直接把任务放进右侧队列！
                    add_history({
                        "task_id": task_id,
                        "timestamp": time.time(),
                        "time_str": datetime.now().strftime("%H:%M:%S"),
                        "prompt": current_prompt,
                        "status": "running", # 初始状态：运行中
                        "url": "",
                        "reason": ""
                    })
                    
                    st.success("🎉 任务已提交至云端！左侧已清空，您可以继续写下一个提示词了。请在右侧点击【🔄 刷新】查看进度。")
                    time.sleep(1.5)
                    st.rerun() # 瞬间刷新页面，解锁左侧供用户继续用
                else:
                    st.error(f"⚠️ 提交接口报错：{sub_res.get('msg', sub_res)}")
            except Exception as e:
                st.error(f"❌ 网络或系统异常：{e}")

# ==========================================
# 6. 右侧任务队列与画廊 (折叠面板设计)
# ==========================================
with col_history:
    st.markdown("### 🗂️ 任务大厅")
    st.caption("提示：只能保存近1个小时图片。")
    
    history_list = clean_and_get_history()
    
    # 刷新按钮逻辑：一键查询所有在排队的任务
    if st.button("🔄 刷新全部生成进度", use_container_width=True):
        with st.spinner("正在向云端同步状态..."):
            updated = False
            for item in history_list:
                if item.get('status') == 'running':
                    query_url = "https://grsai.dakka.com.cn/v1/draw/result"
                    headers = {"Authorization": f"Bearer {GRSAI_API_KEY}", "Content-Type": "application/json"}
                    try:
                        q_res = requests.post(query_url, headers=headers, json={"id": item['task_id']}, verify=False).json()
                        if q_res.get("code") == 0:
                            new_status = q_res["data"]["status"]
                            if new_status == "succeeded":
                                item['status'] = 'succeeded'
                                item['url'] = q_res["data"]["results"][0]["url"]
                                updated = True
                            elif new_status == "failed":
                                item['status'] = 'failed'
                                r = q_res["data"].get("failure_reason", "未知")
                                if r in ["output_moderation", "input_moderation"]: r = "内容违规"
                                item['reason'] = r
                                updated = True
                    except:
                        pass
            if updated:
                save_history(history_list)
                st.session_state.history = history_list
        st.rerun()
    
    if not history_list:
        st.info("💡 队列为空，快去左侧提交任务吧！")
    else:
        # 倒序展示：最新的排在最上面
        for item in reversed(history_list):
            
            # 根据状态决定图标
            if item.get('status') == 'succeeded':
                icon = "✅"
            elif item.get('status') == 'failed':
                icon = "❌"
            else:
                icon = "🏃‍♂️"
                
            short_prompt = item['prompt'][:10] + "..." if len(item['prompt']) > 10 else item['prompt']
            label = f"{icon} [{item['time_str']}] {short_prompt}"
            
            # 使用折叠面板展示，点进去才能看图
            with st.expander(label):
                st.write(f"**描述:** {item['prompt']}")
                
                if item.get('status') == 'running':
                    st.info("━🏃‍♂️━━━━━━━━🏁 冲刺中... \n\n👉 请点击上方【🔄 刷新进度】按钮获取最新状态")
                
                elif item.get('status') == 'failed':
                    st.error(f"生成失败原因: {item.get('reason', '未知错误')}")
                
                elif item.get('status') == 'succeeded':
                    # 100% 抛弃 st.image，用 HTML 彻底杜绝 TypeError 报错
                    html_img = f'<img src="{item["url"]}" style="width:100%; border-radius:8px; border:1px solid #ddd; margin-bottom: 10px;">'
                    st.markdown(html_img, unsafe_allow_html=True)
                    
                    # 直接提供带链接的高清下载文字（点击直接在浏览器新标签页打开原图）
                    st.markdown(f"**[📥 点击这里在浏览器中打开并保存高清原图]({item['url']})**")
