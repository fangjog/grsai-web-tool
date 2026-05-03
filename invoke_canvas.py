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

# 这里是我们将要加载进画布的数据缓存 (关键)
if 'canvas_load_image_cache' not in st.session_state:
    st.session_state.canvas_load_image_cache = None

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
    st.toast("工作台对话记录已刷新。")

# ==========================================
# 1. 主渲染函数：🎨 专业画布工作台 V5.2.1 (稳定版)
# ==========================================
def render_canvas_workspace(api_key, active_user_key, image_cost):
    st.markdown("""
        <div style="background-color: #0d0e12; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="color:#ffffff; margin:0;">🎨 专业画布工作台 V5.2.1</h3>
            <p style="color:#666; font-size:13px; margin:5px 0;">已全面升级数据桥接框架。点击 [添加到对话] 极速无感传递 Base64 图片，坚如磐石！滚轮缩放，空格拖拽位置。</p>
        </div>
    """, unsafe_allow_html=True)
    
    # 状态初始化
    if 'invoke_tasks_list' not in st.session_state:
        st.session_state.invoke_tasks_list = load_json(INVOKE_PROJECT_FILE, [])
    if 'context_images' not in st.session_state:
        st.session_state.context_images = [] # 用于管理送往对话参考栏的图片Base64列表
    if 'balance_points' not in st.session_state:
        st.session_state.balance_points = 0 # 兜底余额点数

    # 主体布局：左侧画布，右侧对话创作中心 (参考 Jimeng V4风格)
    col_canvas, col_creator = st.columns([8, 2])
    
    with col_canvas:
        # ==========================================
        # 🌟 核心更新：使用双向桥接嵌入本地 HTML (开箱即用)
        # ==========================================
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file_path = os.path.join(current_dir, "canvas_engine.html")
        
        try:
            with open(html_file_path, "r", encoding="utf-8") as f:
                html_code = f.read()
            
            # 使用 components.html 将其直接渲染在页面上，并接收返回值 (关键！)
            # 这个返回值就是前端 window.parent.postMessage({ type: 'streamlit:setComponentValue', value: { ... } }, '*') 传过来的数据
            canvas_response = components.html(html_code, height=780, scrolling=False)
            
            # 🌟 捕捉到前端传回来的新图片数据
            if canvas_response and canvas_response.get("type") == "add_image_to_chat":
                # 将Base64塞入参考列表，不需要再用隐藏的input
                st.session_state.context_images.append(canvas_response.get("content"))
                # 清除状态，防死循环
                # 这里不需要，因为 Streamlit 在 rerun 之后，这个 canvas_response 会自然变成 None
                st.rerun()

        except FileNotFoundError:
            st.error(f"⚠️ 找不到画布引擎文件！确保 `canvas_engine.html` 在 app.py 同目录下。")

    # ==========================================
    # 🌟 右侧对话创作中心
    # ==========================================
    with col_creator:
        st.markdown("### 💬 创作对话中心")
        st.caption(f"剩余可制图次数: {int(st.session_state.balance_points // image_cost)} 张")
        
        c1, c2 = st.columns([1,1])
        with c1: st.button("T 提取文本 reference", disabled=True, use_container_width=True)
        with c2: st.button("🗑️ 刷新对话记录", on_click=clear_workspace_tasks, use_container_width=True)
        
        st.divider()

        # 对话创作区 (参考图4风格)
        with st.container(height=650):
            # 🌟 参考图参考栏 (接收数据后立即显示)
            if st.session_state.context_images:
                st.markdown("📎 参考图栏 (点击AddToDialogue后数据传回此)")
                img_cols = st.columns(min(len(st.session_state.context_images), 3))
                for idx, b64 in enumerate(st.session_state.context_images):
                    with img_cols[idx % 3]:
                        # HTML渲染预览，防报错
                        st.markdown(f'<img src="{b64}" style="width:100%; border-radius:4px; border:1px solid #00c2ff;">', unsafe_allow_html=True)
                        if st.button("🗑️", key=f"del_ctx_{idx}"):
                            st.session_state.context_images.pop(idx)
                            st.rerun()
                st.divider()
            
            # 用户输入框 (Jimeng风格)
            prompt_input = st.text_input("💬 输入画面描述指令...", placeholder="Seedance 2.0 创作描述，左侧选择元素AddToDialogue即可...")
            btn_generate = st.button("✨ 立即生成 (并记账成本)", key="btn_invoke_gen", type="primary")

            # 🌟 处理生成请求 (完美对接上一版管理对账系统)
            if btn_generate:
                if not prompt_input:
                    st.error("❌ 请输入画面描述指令指令！")
                else:
                    # 获取底图和遮罩参考逻辑 (简化演示，只传Base64字符串)
                    urls_list = []
                    if st.session_state.context_images:
                        st.toast("正在高清化对话参考图层...")
                        for b64 in st.session_state.context_images[:3]: # 只传前3张
                            urls_list.append(b64)
                    
                    if not urls_list:
                        st.toast("💡 当前无参考图参考，文生图模式自动解锁。")

                    # 打包 Payload
                    payload = {
                        "model": "gpt-image-2",
                        "prompt": prompt_input,
                        "urls": urls_list,
                        " shutProgress": True # 关闭排队动画
                    }
                    
                    # 出图接口
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
                            st.toast("🎉 任务已排队，生成小人🏃‍♂️已弹出。")
                            st.rerun()
                        else:
                            st.error(f"⚠️ 出图接口报错：{gen_res.get('msg', gen_res)}")
                    except Exception as e:
                        st.error(f"❌ 网络异常：{e}")

            st.divider()
            st.caption("对话历史记录 (Jimeng风格图卡)")
            
            # --- 精致对话卡片历史区 (参考 Jimeng V4风格) ---
            for task in reversed(st.session_state.invoke_tasks_list):
                with st.container():
                    st.markdown(f"**[{task['time_str']}] ✍️You:** {task['prompt'][:25]}...")
                    st.caption(f"参考图: {task['ref_count']}张")
                    
                    # 进度动画小人 (从 V4.4 逻辑对接过来)
                    if task['status'] == "running":
                        if st.button("🏃‍♂️ 追踪动画进度", key=f"btn_track_{task['task_id']}"):
                            # 联动主 app.py 的动画弹窗
                            st.session_state.invoke_tasks_accounted = task # 标记哪个要追踪
                            st.stop()
                    
                    elif task['status'] == "succeeded":
                        html_res = f'<img src="{task["url"]}" style="width:100%; border-radius:8px;">'
                        st.markdown(html_res, unsafe_allow_html=True)
                        st.markdown(f"**[📥 下载高清原图]({task['url']})**")
                        
                        # 🌟 核心需求：生成的图片，点击魔法加载回画布里
                        if st.button("🪄 点击魔法加载回画布工作台", key=f"load_{task['task_id']}"):
                            # 将这个 URL 存入缓存，准备下一次通过 JS 强制加载回前端
                            st.session_state.canvas_load_image_cache = task['url']
                            st.rerun()
                            
                    elif task['status'] == "failed":
                        st.error(f"❌ 失败: 安全审查拦截/系统异常 (失败不扣除额度)")
                        
                    st.divider()
                    
    # 数据链路处理 (核心前端黑科技下半段)
    # 当有生成成功的图片缓存时，通过注入一段注入全局的脚本来控制iframe内部加载图片
    if st.session_state.canvas_load_image_cache:
        url = st.session_state.canvas_load_image_cache
        components.html(f"""
            <script>
                // 强制跨域穿透，找到 iframe 内部并调用加载函数
                // 只有当 streamlit 主页和 iframe 都处于 localhost 下时才有效 (安全策略隔离)
                const iframes = window.parent.document.querySelectorAll('iframe');
                iframes.forEach(iframe => {{
                    try {{
                        if(iframe.contentWindow && iframe.contentWindow.addImageToCanvas) {{
                            iframe.contentWindow.addImageToCanvas("{url}");
                        }}
                    }} catch(e) {{
                        // 这里可能会报跨域错误，是正常的安全限制，不用管
                        console.error("加载生成的图片回画布失败，这是出于浏览器的安全跨域隔离限制。");
                    }}
                }});
            </script>
        """, height=0, width=0)
        # 清除数据，防死循环
        st.session_state.canvas_load_image_cache = None
