import streamlit as st
import requests
import time
from PIL import Image
import io
import base64
from datetime import datetime
import json
import os

# ==========================================
# 0. 网页基础配置与全局隐藏 (沉浸式全屏)
# ==========================================
st.set_page_config(page_title="Jimeng Style Workspace", page_icon="🎨", layout="wide", initial_sidebar_state="collapsed")

# 极限自定义 CSS：隐藏默认元素，模拟即梦的排版
st.markdown("""
<style>
    /* 隐藏 Streamlit 默认的顶部边距、菜单和页脚 */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; padding-left: 1rem; padding-right: 1rem; max-width: 100%; }
    header { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* 左侧极简工具栏容器 */
    .left-tools { display: flex; flex-direction: column; gap: 20px; align-items: center; margin-top: 20px; }
    
    /* 灰色无边框画布区 */
    .jimeng-canvas {
        background-color: #f3f4f6;
        border-radius: 8px;
        min-height: 75vh;
        width: 100%;
        position: relative;
        padding: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-wrap: wrap;
        gap: 40px;
        box-shadow: inset 0 0 10px rgba(0,0,0,0.02);
    }

    /* 选中的元素样式 (蓝边框 + 小圆点) */
    .element-wrapper { position: relative; display: inline-block; }
    .is-selected { border: 2px solid #00c2ff; }
    .is-selected::before, .is-selected::after {
        content: ''; position: absolute; width: 8px; height: 8px; background: white; border: 2px solid #00c2ff; border-radius: 50%;
    }
    .is-selected::before { top: -5px; left: -5px; } /* 左上角点 */
    .is-selected::after { bottom: -5px; right: -5px; } /* 右下角点 */

    /* 悬浮工具栏 (纯视觉) */
    .mock-toolbar {
        position: absolute;
        top: -50px; left: 50%; transform: translateX(-50%);
        background: white; border-radius: 8px; padding: 5px 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        display: flex; gap: 15px; font-size: 13px; color: #333; white-space: nowrap; z-index: 10;
        border: 1px solid #eee;
    }
    
    /* 底部输入栏外层调整 */
    .stChatInput { padding-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 数据持久化与状态初始化
# ==========================================
PROJECTS_FILE = "jimeng_projects.json"
def load_projects():
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

if 'projects' not in st.session_state:
    st.session_state.projects = load_projects()
    if not st.session_state.projects:
        st.session_state.projects.append({"id": 1, "title": "未命名项目", "layers": []})
if 'curr_proj_idx' not in st.session_state:
    st.session_state.current_proj_idx = 0
if 'selected_idx' not in st.session_state:
    st.session_state.selected_idx = -1

def save_projects():
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f: json.dump(st.session_state.projects, f, ensure_ascii=False)

curr_proj = st.session_state.projects[st.session_state.current_proj_idx]
if "layers" not in curr_proj: curr_proj["layers"] = []

# ==========================================
# 2. 顶部状态栏 (项目名 & 积分)
# ==========================================
top_c1, top_c2 = st.columns([8, 2])
with top_c1:
    st.markdown(f"### 📂 {curr_proj['title']} ⌵")
with top_c2:
    st.markdown(f"<div style='text-align:right; color:#666;'>可用算力: <strong style='color:#FF4B4B;'>16</strong> 张 &nbsp;&nbsp; 💬 对话</div>", unsafe_allow_html=True)
st.markdown("<hr style='margin: 10px 0; border-color: #eee;'>", unsafe_allow_html=True)

# ==========================================
# 3. 主体区域：左侧工具 + 核心画布
# ==========================================
col_tools, col_canvas = st.columns([1, 15])

# --- 左侧极简工具栏 ---
with col_tools:
    st.markdown("<br><br>", unsafe_allow_html=True)
    up_img = st.file_uploader(" ", type=["png","jpg"], label_visibility="collapsed")
    if up_img:
        b64 = f"data:image/jpeg;base64,{base64.b64encode(up_img.getvalue()).decode()}"
        curr_proj["layers"].append({"type": "image", "content": b64})
        save_projects(); st.rerun()
        
    if st.button("T", help="添加文本"):
        curr_proj["layers"].append({"type": "text", "content": "这个是文本框"})
        save_projects(); st.rerun()
        
    st.button("⌗", help="自动布局")
    st.button("🗑️", help="清空画布")

# --- 核心灰色画布区 ---
with col_canvas:
    st.markdown('<div class="jimeng-canvas">', unsafe_allow_html=True)
    
    if not curr_proj["layers"]:
        st.markdown("<p style='color:#bbb; font-size:18px;'>在底部输入文字，或从左侧上传图片</p>", unsafe_allow_html=True)
    else:
        # 画布元素渲染
        for idx, layer in enumerate(curr_proj["layers"]):
            # 为了交互，我们用按钮模拟点击选中
            is_selected = (idx == st.session_state.selected_idx)
            sel_class = "is-selected" if is_selected else ""
            
            # 开始元素容器
            st.markdown(f'<div class="element-wrapper {sel_class}">', unsafe_allow_html=True)
            
            # 渲染选中状态的悬浮工具栏 (复刻你截图中的内容)
            if is_selected:
                if layer["type"] == "text":
                    st.markdown('''
                    <div class="mock-toolbar">
                        <span>💬 添加到对话</span> <span style="color:#ddd;">|</span> <span>96 ⌵</span> <span>≡</span> <span><b>B</b></span> <span>📥</span>
                    </div>
                    ''', unsafe_allow_html=True)
                else:
                    st.markdown('''
                    <div class="mock-toolbar">
                        <span>💬 添加到对话</span> <span style="color:#ddd;">|</span> <span>🪄 扩图</span> <span>💎 超清</span> <span>✂️ 抠图</span> <span>T 改文字</span>
                    </div>
                    ''', unsafe_allow_html=True)

            # 渲染实际内容
            if layer["type"] == "text":
                # 点击文本本身作为选中触发
                st.markdown(f"<h3 style='margin:0; padding:10px;'>{layer['content']}</h3>", unsafe_allow_html=True)
            else:
                st.markdown(f'<img src="{layer["content"]}" style="max-width:300px; border-radius:4px;">', unsafe_allow_html=True)
                
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 在元素下方放一个极其隐蔽的小按钮用于“选中”和“删除”
            sub_col1, sub_col2 = st.columns([1,1])
            with sub_col1:
                if st.button("👆 选中", key=f"sel_{idx}"):
                    st.session_state.selected_idx = idx
                    st.rerun()
            with sub_col2:
                if is_selected:
                    if st.button("❌ 删", key=f"del_{idx}"):
                        curr_proj["layers"].pop(idx)
                        st.session_state.selected_idx = -1
                        save_projects(); st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 4. 底部中央
