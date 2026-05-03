# 文件名: invoke_canvas.py
import streamlit as st
import streamlit.components.v1 as components
import json
import os
import requests
import time
from datetime import datetime

# ==========================================
# 数据存取工具
# ==========================================
INVOKE_PROJECT_FILE = "invoke_workspace_project.json"

def load_json(path, default=[]):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: return default
    return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False)
    except: pass

def clear_workspace_tasks():
    save_json(INVOKE_PROJECT_FILE, [])
    st.session_state.invoke_tasks_list = []
    st.toast("工作台记录已刷新。")

# ==========================================
# 主渲染函数：🎨 专业画布工作台 V5.4 (UI 终极美化版)
# ==========================================
def render_canvas_workspace(api_key, active_user_key, image_cost):
    # 注入即梦风格的卡片 CSS
    st.markdown("""
    <style>
        .jimeng-input-card {
            background-color: #ffffff; border-radius: 16px; padding: 15px 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05); border: 1px solid #eaeaea; margin-bottom: 20px;
        }
        .jimeng-thumb-wrapper { position: relative; height: 60px; margin-bottom: 10px; display: inline-block; width: 100px; }
        .jimeng-thumb-img {
            position: absolute; width: 55px; height: 55px; object-fit: cover;
            border-radius: 8px; border: 2px solid white; box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        .jimeng-thumb-img:nth-child(1) { transform: rotate(-5deg); z-index: 1; left: 0; }
        .jimeng-thumb-img:nth-child(2) { transform: rotate(5deg); z-index: 2; left: 20px; }
        .jimeng-thumb-img:nth-child(3) { transform: rotate(-2deg); z-index: 3; left: 40px; }
    </style>
    """, unsafe_allow_html=True)

    # 状态初始化
    if 'invoke_tasks_list' not in st.session_state:
        st.session_state.invoke_tasks_list = load_json(INVOKE_PROJECT_FILE, [])
    if 'context_images' not in st.session_state:
        st.session_state.context_images = [] 
    if 'canvas_load_image_cache' not in st.session_state:
        st.session_state.canvas_load_image_cache = None
    if 'last_bridge_val' not in st.session_state:
        st.session_state.last_bridge_val = ""

    # 数据桥接
    bridge_val = st.text_input("canvas_bridge", key="canvas_bridge_input", label_visibility="hidden")
    st.markdown('<style>div[data-testid="stTextInput"]:has(input[aria-label="canvas_bridge"]) { display: none; margin: 0; padding: 0; height: 0; }</style>', unsafe_allow_html=True)

    if bridge_val and bridge_val != st.session_state.last_bridge_val:
        st.session_state.last_bridge_val = bridge_val
        try:
            _, b64_data = bridge_val.split("|||", 1)
            st.session_state.context_images.append(b64_data)
            st.rerun()
        except Exception as e: pass

    # 左右布局
    col_canvas, col_creator = st.columns([7, 3]) # 为了让右侧有足够空间展示精美卡片，微调比例
    
    with col_canvas:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file_path = os.path.join(current_dir, "canvas_engine.html")
        try:
            with open(html_file_path, "r", encoding="utf-8") as f:
                html_code = f.read()
            components.html(html_code, height=850, scrolling=False)
        except FileNotFoundError:
            st.error(f"⚠️ 找不到 `canvas_engine.html`。")

    # ==========================================
    # 🌟 核心更新：完美复刻的右侧对话输入区
    # ==========================================
    with col_creator:
        st.markdown("### 💬 Agent 创作中心")
        
        # 将参考图和输入框合体为一个精致的“卡片”
        st.markdown('<div class="jimeng-input-card">', unsafe_allow_html=True)
        
        # 1. 渲染错落叠放的参考缩略图 (完全还原图2效果)
        if st.session_state.context_images:
            html_thumbs = '<div class="jimeng-thumb-wrapper">'
            for idx, b64 in enumerate(st.session_state.context_images[:3]): # 最多展示3张叠放
                html_thumbs += f'<img src="{b64}" class="jimeng-thumb-img">'
            html_thumbs += '</div>'
            
            c_img, c_btn = st.columns([7, 3])
            with c_img:
                st.markdown(html_thumbs, unsafe_allow_html=True)
            with c_btn:
                if st.button("🗑️ 清空参考", key="clear_ctx", use_container_width=True):
                    st.session_state.context_images = []
                    st.rerun()
                    
        # 2. 沉浸式输入框
        prompt_input = st.text_input(
            "描述", 
            placeholder="结合参考，输入文字或 @ 主体，说说今天想做什么。", 
            label_visibility="collapsed"
        )
        
        # 3. 底部操作栏
        col_btn1, col_btn2 = st.columns([6, 4])
        with col_btn1:
            st.markdown("<div style='font-size:12px; color:#666; margin-top:12px;'>✨ 自动 | 🔍 灵感搜索</div>", unsafe_allow_html=True)
        with col_btn2:
            btn_generate = st.button("🚀 立即生成", key="btn_invoke_gen", type="primary", use_container_width=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
        # 卡片结束 ---------------------------------

        # 生成逻辑
        if btn_generate:
            if not prompt_input:
                st.error("❌ 请输入提示词！")
            else:
                urls_list = st.session_state.context_images[:3] if st.session_state.context_images else []
                payload = {"model": "gpt-image-2", "prompt": prompt_input, "urls": urls_list, "shutProgress": True}
                try:
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    st.toast("正在向云端提交生成任务...")
                    gen_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                    
                    if gen_res.get("code") == 0:
                        task_id = gen_res["data"]["id"]
                        item = {
                            "task_id": task_id,
                            "time_str": datetime.now().strftime("%m-%d %H:%M"),
                            "prompt": prompt_input,
                            "ref_count": len(urls_list),
                            "status": "running",
                            "url": ""
                        }
                        st.session_state.invoke_tasks_list.append(item)
                        save_json(INVOKE_PROJECT_FILE, st.session_state.invoke_tasks_list)
                        st.rerun()
                    else:
                        st.error(f"⚠️ 接口报错：{gen_res.get('msg', gen_res)}")
                except Exception as e:
                    st.error(f"❌ 网络异常：{e}")

        # ==========================================
        # 对话历史区 (带滚动条，防止过长)
        # ==========================================
        st.markdown(f"**历史记录** (剩余算力: {int(st.session_state.get('balance_points', 0) // image_cost)}张)")
        
        with st.container(height=500):
            for task in reversed(st.session_state.invoke_tasks_list):
                with st.container():
                    st.markdown(f"**[{task['time_str']}] ✍️:** {task['prompt'][:25]}...")
                    
                    if task['status'] == "running":
                        if st.button("🏃‍♂️ 追踪进度", key=f"btn_track_{task['task_id']}"):
                            st.session_state.invoke_tasks_accounted = task 
                            st.stop()
                    
                    elif task['status'] == "succeeded":
                        st.markdown(f'<img src="{task["url"]}" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
                        if st.button("🪄 加载回画布", key=f"load_{task['task_id']}", use_container_width=True):
                            st.session_state.canvas_load_image_cache = task['url']
                            st.rerun()
                            
                    elif task['status'] == "failed":
                        st.error(f"❌ 失败: 安全审查拦截/异常")
                        
                    st.divider()
                    
    # ==========================================
    # 跨域穿透：自动加载云端图片回前端画布
    # ==========================================
    if st.session_state.canvas_load_image_cache:
        url = st.session_state.canvas_load_image_cache
        components.html(f"""
            <script>
                const iframes = window.parent.document.querySelectorAll('iframe');
                iframes.forEach(iframe => {{
                    try {{
                        if(iframe.contentWindow && iframe.contentWindow.addImageToCanvas) {{
                            iframe.contentWindow.addImageToCanvas("{url}");
                        }}
                    }} catch(e) {{ console.log("Cross-origin constraint"); }}
                }});
            </script>
        """, height=0, width=0)
        st.session_state.canvas_load_image_cache = None
