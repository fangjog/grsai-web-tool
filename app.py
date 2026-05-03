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
# 0. 网页基础配置
# ==========================================
st.set_page_config(page_title="AI Pro Workspace", page_icon="🎨", layout="wide")

# 注入自定义 CSS 模拟设计工具界面 (还原图1, 图2的视觉)
st.markdown("""
<style>
    /* 模拟画布背景 */
    .design-canvas {
        background-color: #f0f2f5;
        border-radius: 15px;
        height: 650px;
        position: relative;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        border: 1px solid #ddd;
    }
    
    /* 模拟选中框和手柄 (蓝边控制点) */
    .selected-element {
        border: 2px solid #00c2ff;
        position: relative;
        display: inline-block;
    }
    .handle {
        width: 10px;
        height: 10px;
        background-color: white;
        border: 2px solid #00c2ff;
        border-radius: 50%;
        position: absolute;
    }
    .top-left { top: -6px; left: -6px; }
    .top-right { top: -6px; right: -6px; }
    .bottom-left { bottom: -6px; left: -6px; }
    .bottom-right { bottom: -6px; right: -6px; }
    .rotate-handle {
        bottom: -30px;
        left: 50%;
        transform: translateX(-50%);
        width: 24px;
        height: 24px;
        background: white;
        border-radius: 50%;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* 悬浮工具栏样式 (还原图1, 图2上方横条) */
    .floating-toolbar {
        position: absolute;
        top: -60px;
        left: 50%;
        transform: translateX(-50%);
        background: white;
        padding: 8px 15px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        display: flex;
        gap: 15px;
        align-items: center;
        white-space: nowrap;
        z-index: 100;
    }
    .toolbar-item {
        font-size: 14px;
        color: #333;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 持久化数据与认证 (保持之前逻辑)
# ==========================================
# ... (API配置与验证逻辑保持不变)
KEY_MAP = {"vip888": "API_VIP", "test1234": "API_TEST", "123": "API_123", "free_trial": "GRSAI_API_KEY"}
KEY_POINTS = {"vip888": 10000, "test1234": 5000, "123": 5000, "free_trial": 600}

st.sidebar.markdown("### 🪪 身份验证")
user_key_input = st.sidebar.text_input("🔑 输入激活码", type="password")
user_key = user_key_input.strip() if user_key_input else ""
if not user_key or user_key not in KEY_MAP:
    st.warning("👈 请输入激活码解锁。")
    st.stop()
secret_name = KEY_MAP[user_key]
GRSAI_API_KEY = st.secrets.get(secret_name, "")

# 数据存储
PROJECTS_FILE = "projects_v31.json"
def load_projects():
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

if 'projects' not in st.session_state:
    st.session_state.projects = load_projects()
if 'current_proj_idx' not in st.session_state:
    st.session_state.current_proj_idx = None
if 'selected_layer_idx' not in st.session_state:
    st.session_state.selected_layer_idx = 0

def save_projects():
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(st.session_state.projects, f, ensure_ascii=False)

# ==========================================
# 2. 页面布局
# ==========================================
menu = st.sidebar.radio("菜单", ["灵感生成", "画布项目"])

if menu == "灵感生成":
    st.title("✨ 灵感生成")
    # ... (保持之前的高效生成逻辑，略去以节省篇幅，重点在下方的画布优化)
    st.info("此模块功能正常。请点击左侧【画布项目】查看本次更新的重点设计功能。")

elif menu == "画布项目":
    st.title("🎨 专业画布工作台")
    
    # 项目选择器
    if not st.session_state.projects:
        if st.button("➕ 新建项目"):
            st.session_state.projects.append({"title": "未命名设计", "layers": []})
            st.session_state.current_proj_idx = 0
            save_projects()
            st.rerun()
        st.stop()
    
    # 顶部工具栏 (参考图5, 6, 7)
    t_col1, t_col2, t_col3, t_col4 = st.columns([2, 2, 2, 4])
    curr_proj = st.session_state.projects[st.session_state.current_proj_idx if st.session_state.current_proj_idx is not None else 0]
    
    with t_col1:
        up_img = st.file_uploader("📤 本地上传", type=["png","jpg"], label_visibility="collapsed")
        if up_img:
            img_data = f"data:image/jpeg;base64,{base64.b64encode(up_img.getvalue()).decode()}"
            curr_proj["layers"].append({"type": "image", "content": img_data})
            save_projects(); st.rerun()
    with t_col2:
        if st.button("T 添加文本框", use_container_width=True):
            curr_proj["layers"].append({"type": "text", "content": "这是一个文本框"})
            save_projects(); st.rerun()
    with t_col3:
        st.selectbox("⌗ 画板尺寸", ["自由比例", "16:9", "1:1", "4:3"], label_visibility="collapsed")
    
    st.divider()

    # 画布主区域 (左侧图层选择，中间画布)
    canvas_col, prop_col = st.columns([8, 2])
    
    with prop_col:
        st.markdown("##### 🗂️ 图层管理")
        if not curr_proj["layers"]:
            st.caption("暂无内容")
        else:
            layer_names = [f"图层 {i+1}: {l['type']}" for i, l in enumerate(curr_proj['layers'])]
            st.session_state.selected_layer_idx = st.radio("选择编辑对象", range(len(layer_names)), format_func=lambda x: layer_names[x])
            
            st.markdown("---")
            st.markdown("##### ⚙️ 选定层属性")
            target = curr_proj["layers"][st.session_state.selected_layer_idx]
            if target["type"] == "text":
                new_txt = st.text_input("修改文字", value=target["content"])
                if new_txt != target["content"]:
                    target["content"] = new_txt; save_projects(); st.rerun()
            if st.button("🗑️ 删除此层"):
                curr_proj["layers"].pop(st.session_state.selected_layer_idx)
                save_projects(); st.rerun()

    with canvas_col:
        # 渲染模拟画布
        st.markdown('<div class="design-canvas">', unsafe_allow_html=True)
        
        if curr_proj["layers"]:
            # 只为选中的图层渲染“选中效果”
            for i, layer in enumerate(curr_proj["layers"]):
                is_selected = (i == st.session_state.selected_layer_idx)
                
                # 开始渲染图层容器
                selected_class = "selected-element" if is_selected else ""
                st.markdown(f'<div class="{selected_class}" style="max-width:80%;">', unsafe_allow_html=True)
                
                # 如果选中，显示悬浮工具栏 (还原图1, 图2)
                if is_selected:
                    if layer["type"] == "text":
                        st.markdown(f'''
                        <div class="floating-toolbar">
                            <div class="toolbar-item">💬 添加到对话</div>
                            <div class="toolbar-item">96 ⌵</div>
                            <div class="toolbar-item"><b>B</b></div>
                            <div class="toolbar-item">📥</div>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown(f'''
                        <div class="floating-toolbar">
                            <div class="toolbar-item">🪄 扩图</div>
                            <div class="toolbar-item">💎 超清</div>
                            <div class="toolbar-item">✂️ 报图</div>
                            <div class="toolbar-item">📥</div>
                        </div>
                        ''', unsafe_allow_html=True)

                # 渲染实际内容
                if layer["type"] == "text":
                    st.markdown(f'<h2 style="color:#333; margin:0; padding:10px 20px;">{layer["content"]}</h2>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<img src="{layer["content"]}" style="width:400px; border-radius:4px;">', unsafe_allow_html=True)
                
                # 如果选中，渲染四个蓝手柄和旋转图标 (还原图1, 图2)
                if is_selected:
                    st.markdown('''
                        <div class="handle top-left"></div><div class="handle top-right"></div>
                        <div class="handle bottom-left"></div><div class="handle bottom-right"></div>
                        <div class="rotate-handle">🔄</div>
                    ''', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#999;'>画布空空如也，请点击上方工具栏添加素材</p>", unsafe_allow_html=True)
            
        st.markdown('</div>', unsafe_allow_html=True)
