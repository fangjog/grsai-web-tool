# 文件名: invoke_canvas.py
import streamlit as st
import streamlit.components.v1 as components
import json, os, requests, time
from datetime import datetime

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

def render_canvas_workspace(api_key, active_user_key, image_cost):
    # 🌟 极简全屏 CSS 
    st.markdown("""
    <style>
        .block-container { padding: 0 !important; max-width: 100% !important; }
        [data-testid="stVerticalBlock"] > div:has(div.stFrame) { padding: 0 !important; }
        
        .canvas-bg { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; z-index: 0; }
        
        .bottom-input-bar {
            position: fixed; bottom: 90px; left: 50%; transform: translateX(-50%);
            background: white; border-radius: 30px; padding: 10px 25px;
            box-shadow: 0 4px 30px rgba(0,0,0,0.15); z-index: 100;
            width: 600px; border: 1px solid #eee; display: flex; align-items: center;
        }

        .top-right-bar {
            position: fixed; top: 20px; right: 20px; z-index: 100;
            display: flex; gap: 15px; align-items: center;
        }

        .thumb-stack { position: relative; width: 60px; height: 45px; display: inline-block; margin-right: 15px; }
        .thumb-img {
            position: absolute; width: 40px; height: 40px; object-fit: cover;
            border-radius: 6px; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
    </style>
    """, unsafe_allow_html=True)

    if 'invoke_tasks_list' not in st.session_state: st.session_state.invoke_tasks_list = load_json(INVOKE_PROJECT_FILE, [])
    if 'context_images' not in st.session_state: st.session_state.context_images = [] 
    if 'show_sidebar' not in st.session_state: st.session_state.show_sidebar = False
    if 'last_bridge_val' not in st.session_state: st.session_state.last_bridge_val = ""

    # ==========================================
    # 数据桥接
    # ==========================================
    bridge_val = st.text_input("canvas_bridge", key="canvas_bridge_input", label_visibility="hidden")
    st.markdown('<style>div[data-testid="stTextInput"]:has(input[aria-label="canvas_bridge"]) { display: none; height:0; }</style>', unsafe_allow_html=True)
    
    if bridge_val and bridge_val != st.session_state.last_bridge_val:
        st.session_state.last_bridge_val = bridge_val
        _, b64 = bridge_val.split("|||", 1)
        st.session_state.context_images.append(b64)
        st.rerun()

    # ==========================================
    # 渲染 Tldraw 画布层
    # ==========================================
    st.markdown('<div class="canvas-bg">', unsafe_allow_html=True)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_file_path = os.path.join(current_dir, "canvas_engine.html")
    with open(html_file_path, "r", encoding="utf-8") as f:
        components.html(f.read(), height=1000)
    st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # UI：右上角与底部输入药丸
    # ==========================================
    st.markdown('<div class="top-right-bar">', unsafe_allow_html=True)
    col_tr1, col_tr2 = st.columns([1,1])
    with col_tr1: st.markdown(f"<span style='color:#666; font-weight:bold;'>剩余算力: {int(st.session_state.get('balance_points',0)//image_cost)}</span>", unsafe_allow_html=True)
    with col_tr2: 
        if st.button("💬 创作记录"): 
            st.session_state.show_sidebar = not st.session_state.show_sidebar
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="bottom-input-bar">', unsafe_allow_html=True)
    bi_c1, bi_c2, bi_c3 = st.columns([1.5, 7, 1.5])
    with bi_c1:
        if st.session_state.context_images:
            html_thumbs = '<div class="thumb-stack" onclick="window.parent.location.reload()">'
            for idx, b64 in enumerate(st.session_state.context_images[:3]):
                html_thumbs += f'<img src="{b64}" class="thumb-img" style="left:{idx*12}px; z-index:{10-idx};">'
            html_thumbs += '</div>'
            st.markdown(html_thumbs, unsafe_allow_html=True)
        else:
            st.markdown("<span style='font-size:24px; color:#ccc;'>✨</span>", unsafe_allow_html=True)
    with bi_c2:
        prompt_input = st.text_input("prompt", placeholder="结合画布参考图，描述你的构思...", label_visibility="collapsed")
    with bi_c3:
        if st.button("🚀生成", key="gen_btn"):
            if prompt_input:
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                payload = {"model": "gpt-image-2", "prompt": prompt_input, "urls": st.session_state.context_images[:3], "shutProgress": True}
                res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                if res.get("code") == 0:
                    item = {"task_id": res["data"]["id"], "time_str": datetime.now().strftime("%H:%M"), "prompt": prompt_input, "status": "running", "url": ""}
                    st.session_state.invoke_tasks_list.append(item)
                    save_json(INVOKE_PROJECT_FILE, st.session_state.invoke_tasks_list)
                    st.toast("🎨 创作开始！请点击右上角【创作记录】追踪进度。")
                else: st.error("接口错误")
            else: st.warning("请输入指令描述")
    st.markdown('</div>', unsafe_allow_html=True)

    # ==========================================
    # 对话历史侧边栏
    # ==========================================
    if st.session_state.show_sidebar:
        with st.sidebar:
            st.markdown("### 💬 创作历史记录")
            if st.button("清空记录"): save_json(INVOKE_PROJECT_FILE, []); st.session_state.invoke_tasks_list=[]; st.rerun()
            st.divider()
            for task in reversed(st.session_state.invoke_tasks_list):
                with st.container():
                    st.caption(f"🕒 {task['time_str']}")
                    st.markdown(f"**指令:** {task['prompt']}")
                    if task['status'] == "running":
                        if st.button("🏃 追踪进度", key=f"t_{task['task_id']}"):
                            st.session_state.invoke_tasks_accounted = task
                            st.rerun()
                    elif task['status'] == "succeeded":
                        st.image(task['url'])
                        if st.button("🪄 魔法加载到画板", key=f"l_{task['task_id']}"):
                            components.html(f"<script>window.parent.frames[0].addImageToCanvas('{task['url']}')</script>")
                    st.divider()

    # 魔法回流触发
    if st.session_state.get('canvas_load_image_cache'):
        url = st.session_state.canvas_load_image_cache
        components.html(f"<script>window.parent.frames[0].addImageToCanvas('{url}')</script>")
        st.session_state.canvas_load_image_cache = None
