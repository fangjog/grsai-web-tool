# 文件名: invoke_canvas.py
import streamlit as st
import streamlit.components.v1 as components
import json
import os
import requests
import time
from datetime import datetime

# ==========================================
# 0. 数据存取工具
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
# 1. 主渲染函数：🎨 专业画布工作台 V5.3 (稳定修复版)
# ==========================================
def render_canvas_workspace(api_key, active_user_key, image_cost):
    st.markdown("""
        <div style="background-color: #0d0e12; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="color:#ffffff; margin:0;">🎨 专业画布工作台 V5.3</h3>
            <p style="color:#666; font-size:13px; margin:5px 0;">已修复乱码与核心崩溃。现在采用最稳定的隐形数据桥接技术，右键居中，空格拖拽位置。</p>
        </div>
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

    # ==========================================
    # 🌟 核心修复：隐形数据桥接 (彻底解决 APIException)
    # ==========================================
    # 创建一个对用户不可见的输入框，专门用来接收前端发来的 Base64
    bridge_val = st.text_input("canvas_bridge", key="canvas_bridge_input", label_visibility="hidden")
    st.markdown('<style>div[data-testid="stTextInput"]:has(input[aria-label="canvas_bridge"]) { display: none; margin: 0; padding: 0; height: 0; }</style>', unsafe_allow_html=True)

    # 捕捉前端传入的新数据
    if bridge_val and bridge_val != st.session_state.last_bridge_val:
        st.session_state.last_bridge_val = bridge_val
        try:
            # 拆分时间戳和 Base64 数据
            _, b64_data = bridge_val.split("|||", 1)
            st.session_state.context_images.append(b64_data)
            st.rerun()
        except Exception as e:
            pass

    # 布局分离
    col_canvas, col_creator = st.columns([8, 2])
    
    with col_canvas:
        # 嵌入纯净的前端引擎
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file_path = os.path.join(current_dir, "canvas_engine.html")
        try:
            with open(html_file_path, "r", encoding="utf-8") as f:
                html_code = f.read()
            components.html(html_code, height=780, scrolling=False)
        except FileNotFoundError:
            st.error(f"⚠️ 找不到 `canvas_engine.html`。")

    # ==========================================
    # 🌟 右侧对话创作中心
    # ==========================================
    with col_creator:
        st.markdown("### 💬 创作对话中心")
        st.caption(f"剩余可制图次数: {int(st.session_state.get('balance_points', 0) // image_cost)} 张")
        
        c1, c2 = st.columns([1,1])
        with c1: st.button("T 提取文本", disabled=True, use_container_width=True)
        with c2: st.button("🗑️ 刷新记录", on_click=clear_workspace_tasks, use_container_width=True)
        
        st.divider()

        with st.container(height=650):
            # 渲染从画布传过来的参考图
            if st.session_state.context_images:
                st.markdown("📎 **参考图栏** (已从画布提取)")
                img_cols = st.columns(min(len(st.session_state.context_images), 3))
                for idx, b64 in enumerate(st.session_state.context_images):
                    with img_cols[idx % 3]:
                        st.markdown(f'<img src="{b64}" style="width:100%; border-radius:4px; border:1px solid #00c2ff;">', unsafe_allow_html=True)
                        if st.button("🗑️", key=f"del_ctx_{idx}"):
                            st.session_state.context_images.pop(idx)
                            st.rerun()
                st.divider()
            
            prompt_input = st.text_input("💬 输入画面描述...", placeholder="在此输入指令...")
            btn_generate = st.button("✨ 立即生成 (并记账)", key="btn_invoke_gen", type="primary")

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

            st.divider()
            st.caption("对话历史记录")
            
            for task in reversed(st.session_state.invoke_tasks_list):
                with st.container():
                    st.markdown(f"**[{task['time_str']}] ✍️You:** {task['prompt'][:25]}...")
                    st.caption(f"参考图: {task['ref_count']}张")
                    
                    if task['status'] == "running":
                        if st.button("🏃‍♂️ 追踪动画进度", key=f"btn_track_{task['task_id']}"):
                            st.session_state.invoke_tasks_accounted = task 
                            st.stop()
                    
                    elif task['status'] == "succeeded":
                        st.markdown(f'<img src="{task["url"]}" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
                        st.markdown(f"**[📥 下载高清原图]({task['url']})**")
                        if st.button("🪄 加载回画布工作台", key=f"load_{task['task_id']}"):
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
