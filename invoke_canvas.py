# 文件名: invoke_canvas.py
import streamlit as st
import streamlit.components.v1 as components
import json, os, requests, time
from datetime import datetime

def render_canvas_workspace(api_key, active_user_key, image_cost):
    # 🌟 核心：全屏沉浸式 CSS (彻底解决“画布不是全局”的问题)
    st.markdown("""
        <style>
            /* 强制全屏，隐藏所有侧边栏和内边距 */
            .block-container { padding: 0 !important; max-width: 100% !important; }
            iframe { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; border: none; z-index: 0; }
            header, footer { visibility: hidden; }
            .stDeployButton { display: none; }
            
            /* 即梦风格：右侧悬浮对话历史 */
            .jimeng-sidebar {
                position: fixed; right: 20px; top: 20px; width: 360px; height: calc(100vh - 120px);
                background: rgba(255, 255, 255, 0.95); backdrop-filter: blur(10px);
                border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                z-index: 1000; overflow: hidden; display: flex; flex-direction: column;
                border: 1px solid rgba(0,0,0,0.05);
            }
        </style>
    """, unsafe_allow_html=True)

    # 状态与数据桥接
    if 'context_images' not in st.session_state: st.session_state.context_images = []
    if 'invoke_tasks' not in st.session_state: st.session_state.invoke_tasks = []

    # 隐形数据桥梁 (接收画布选中的图片)
    bridge_val = st.text_input("canvas_bridge", key="canvas_bridge_input", label_visibility="hidden")
    if bridge_val and bridge_val != st.session_state.get('last_bridge',''):
        st.session_state.last_bridge = bridge_val
        st.session_state.context_images.append(bridge_val.split("|||")[1])
        st.rerun()

    # 1. 渲染全屏 Tldraw 画布 (基于 CDN，免安装)
    with open("canvas_engine.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=2000) # 高度给够，iframe会自动铺满

    # 2. 渲染右侧悬浮历史面板 (图3效果)
    st.markdown('<div class="jimeng-sidebar">', unsafe_allow_html=True)
    st.markdown("<div style='padding:20px; font-weight:bold; border-bottom:1px solid #eee;'>🕒 创作记录</div>", unsafe_allow_html=True)
    with st.container():
        history_box = st.container(height=600)
        for task in reversed(st.session_state.invoke_tasks):
            with history_box:
                st.caption(f"指令: {task['prompt'][:20]}...")
                if task['url']:
                    st.image(task['url'])
                    if st.button("🪄 魔法回流", key=f"back_{task['task_id']}"):
                        # 指令回流逻辑
                        st.toast("正在加载回画布...")
                st.divider()
    st.markdown('</div>', unsafe_allow_html=True)
