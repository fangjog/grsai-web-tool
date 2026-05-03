# 文件名: invoke_canvas.py
import streamlit as st
import streamlit.components.v1 as components

def render_canvas_workspace(api_key):
    """
    独立渲染专业画布工作台模块
    """
    st.title("🎨 专业画布工作台 (InvokeAI 架构版)")
    
    st.markdown("""
        <div style="background-color: #eef1f6; padding: 15px; border-radius: 8px; border-left: 5px solid #00c2ff; margin-bottom: 20px;">
            <h4>🚀 架构升级说明</h4>
            <p>下方已成功嵌入独立的前端画布引擎。请确保您的本地或服务器已在 <code>http://localhost:3000</code> 启动了该前端服务。</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("##### 🛠️ 独立画布交互区")
    
    # ==========================================
    # 🌟 核心：嵌入 InvokeAI 前端画布
    # ==========================================
    # 参数说明：
    # url: 你的 InvokeAI 或 React 前端运行的地址
    # height: iframe 的高度（根据你的屏幕调节，800 比较适合全屏画板）
    # scrolling: 是否允许 iframe 内部滚动
    try:
        components.iframe(
            src="http://localhost:3000", 
            height=850, 
            scrolling=True
        )
    except Exception as e:
        st.error(f"加载前端服务失败，请检查服务状态。错误: {e}")
