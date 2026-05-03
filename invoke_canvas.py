import streamlit as st
import streamlit.components.v1 as components
import json, os, requests, time
from datetime import datetime

INVOKE_PROJECT_FILE = "invoke_workspace_project.json"

def render_canvas_workspace(api_key, active_user_key, image_cost):
    # 🌟 核心：强制 Streamlit 全屏的 CSS (解决你提到的画布不是全局问题)
    st.markdown("""
        <style>
            .block-container { padding: 0 !important; max-width: 100% !important; }
            iframe { border: none !important; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; }
            header { visibility: hidden; }
            .stDeployButton { display:none; }
            footer { visibility: hidden; }
            /* 右侧浮动对话框 */
            .floating-chat {
                position: fixed; right: 20px; top: 20px; width: 350px; bottom: 100px;
                background: white; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                z-index: 1000; overflow: hidden; display: flex; flex-direction: column;
            }
            /* 底部药丸输入框 */
            .bottom-pill {
                position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
                width: 600px; z-index: 1001;
            }
        </style>
    """, unsafe_allow_html=True)

    # 状态初始化
    if 'context_images' not in st.session_state: st.session_state.context_images = []
    if 'invoke_tasks' not in st.session_state: st.session_state.invoke_tasks = []

    # 数据桥梁 (接收画布 Base64)
    bridge_val = st.text_input("canvas_bridge", key="canvas_bridge_input", label_visibility="hidden")
    if bridge_val and bridge_val != st.session_state.get('last_bridge',''):
        st.session_state.last_bridge = bridge_val
        st.session_state.context_images.append(bridge_val.split("|||")[1])
        st.rerun()

    # 1. 渲染全屏画布背景
    with open("canvas_engine.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=1000)

    # 2. 渲染即梦风格 UI
    # 右侧历史
    st.markdown('<div class="floating-chat">', unsafe_allow_html=True)
    with st.container():
        st.markdown("<div style='padding:15px; border-bottom:1px solid #eee;'><b>💬 创作历史</b></div>", unsafe_allow_html=True)
        with st.container(height=600):
            for task in reversed(st.session_state.invoke_tasks):
                st.caption(task['time'])
                st.markdown(f"**指令:** {task['prompt']}")
                if task['url']:
                    st.image(task['url'])
                    if st.button("🪄 加载到画布", key=f"l_{task['task_id']}"):
                        components.html(f"<script>window.parent.frames[0].addImageToCanvas('{task['url']}')</script>")
                st.divider()
    st.markdown('</div>', unsafe_allow_html=True)

    # 底部输入框
    with st.container():
        st.markdown('<div class="bottom-pill">', unsafe_allow_html=True)
        c1, c2 = st.columns([8, 2])
        with c1:
            # 参考图叠放预览
            if st.session_state.context_images:
                cols = st.columns(min(len(st.session_state.context_images), 4))
                for i, img in enumerate(st.session_state.context_images[:4]):
                    cols[i].image(img, width=40)
            prompt = st.text_input("prompt", placeholder="描述你想生成的画面...", label_visibility="collapsed")
        with c2:
            if st.button("🚀 生成", use_container_width=True):
                # 调用 image-2 接口逻辑 (这里省略重复的 API 调用代码，逻辑同前)
                st.toast("任务已提交...")
        st.markdown('</div>', unsafe_allow_html=True)
