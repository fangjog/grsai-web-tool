# 文件名: invoke_canvas.py
import streamlit as st
import streamlit.components.v1 as components
import os

def render_canvas_workspace(api_key):
    """
    独立渲染专业画布工作台模块
    (完全静态化，无需启动额外的 Node.js 服务器)
    """
    st.title("🎨 专业画布工作台")
    
    st.markdown("""
        <div style="background-color: #eef1f6; padding: 15px; border-radius: 8px; border-left: 5px solid #00c2ff; margin-bottom: 20px;">
            <h4>🚀 开箱即用架构</h4>
            <p>此画板由底层 <code>Fabric.js</code> 驱动，代码已完全内置于您的 Git 仓库。<b>无需配置环境，无需启动外部端口</b>，任意用户 clone 后即可体验丝滑的元素拖拽、层级管理与缩放。</p>
        </div>
    """, unsafe_allow_html=True)

    # ==========================================
    # 🌟 核心：读取本地 HTML 并直接嵌入
    # ==========================================
    # 获取当前 Python 文件所在的目录，并找到 HTML 文件
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_file_path = os.path.join(current_dir, "canvas_engine.html")
    
    try:
        # 读取 HTML 文件内容
        with open(html_file_path, "r", encoding="utf-8") as f:
            html_code = f.read()
            
        # 使用 components.html 将其直接渲染在页面上！
        components.html(html_code, height=750, scrolling=False)
        
    except FileNotFoundError:
        st.error(f"⚠️ 找不到画布文件！请确保 `canvas_engine.html` 与 `app.py` 在同一个目录下。")
