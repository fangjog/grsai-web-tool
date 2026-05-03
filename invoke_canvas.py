# 文件名: invoke_canvas.py
import streamlit as st
import streamlit.components.v1 as components
import json
import os
import requests
import time
from PIL import Image
import io
import base64
from datetime import datetime

# ==========================================
# 0. 数据存取工具与配置文件
# ==========================================
TASKS_FILE = "tasks_history.json"
INVOKE_PROJECT_FILE = "invoke_workspace_project.json"

# 获取管理员在主 app.py 中设置的 IMAGE_COST (统一记账成本)
# 由于 st 变量跨文件，我们在渲染函数中动态传递

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
    st.toast("工作台对话记录已刷新。")

# ==========================================
# 1. 主渲染函数：🎨 专业画布工作台 V5.1
# ==========================================
def render_canvas_workspace(api_key, active_user_key, image_cost):
    """
    独立渲染专业画布工作台模块
    (完全静态化前端Fabric引擎 + Python后端的创作中心)
    """
    st.markdown("""
        <div style="background-color: #0d0e12; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="color:#ffffff; margin:0;">🎨 专业画布工作台 V5.1</h3>
            <p style="color:#666; font-size:13px; margin:5px 0;">此区域实现了画布与对话的双向数据高速链路。右键居中画布，空格拖拽位置。</p>
        </div>
    """, unsafe_allow_html=True)
    
    # 确保项目记录文件存在
    if 'invoke_tasks_list' not in st.session_state:
        st.session_state.invoke_tasks_list = load_json(INVOKE_PROJECT_FILE, [])
        
    if 'context_images' not in st.session_state:
        st.session_state.context_images = [] # 用于管理送往对话参考栏的图片Base64列表

    # 数据缓存处理区 (用于在画布HTML和Python之间传递生成的图片URL)
    if 'canvas_load_image_cache' not in st.session_state:
        st.session_state.canvas_load_image_cache = None

    # 定义数据同步组件，收集画布事件数据 (黑科技核心)
    # 这个 html 组件是隐藏的，负责把 Fabric 的点击数据传回 Python
    data_sync = components.html("""
        <script>
            // 监听 Python 的指令 (例如：加载生成的图片回画布)
            window.parent.addEventListener('st:canvas_refresh', (e) => {
                const data = e.detail;
                if (data.type === 'load_generated_image') {
                    // 调用画布的全局函数
                    window.parent.frames[0].addImageToCanvas(data.url);
                }
            });
            
            // 监听画布的数据传回 (例如：点击AddToDialogue，把Base64送过来)
            window.parent.addEventListener('message', (e) => {
                const data = e.data;
                if (data.type === 'add_image_to_chat') {
                    // 标记这个Base64需要存入 st 状态，强制 st 刷新
                    Streamlit.setComponentValue({ type: "image_data", content: data.content });
                }
            });
        </script>
    """, height=0)

    # 主体布局：左侧画布，右侧对话创作中心 (参考 Jimeng V4风格)
    col_canvas, col_creator = st.columns([8, 2])
    
    with col_canvas:
        # ==========================================
        # 🌟 核心需求：嵌入本地 HTML 静态引擎 (無需服务，開箱即用)
        # ==========================================
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file_path = os.path.join(current_dir, "canvas_engine.html")
        
        try:
            with open(html_file_path, "r", encoding="utf-8") as f:
                html_code = f.read()
                
            # 使用 components.html 将其直接渲染在页面上
            # 增加一个隐藏的 CSS 标记，用于 JS 全局查找
            final_html = html_code.replace("AI Pro Canvas Engine", "INVOKE_FRAME")
            components.html(final_html, height=780, scrolling=False)
            
            # 核心链路逻辑：监听 data_sync 传回来的Base64数据，存入st
            if data_sync and data_sync.get("type") == "image_data":
                b64_content = data_sync.get("content")
                st.session_state.context_images.append(b64_content)
                # 清除 data_sync 状态，防死循环
                data_sync["type"] = "none"
                st.rerun()

        except FileNotFoundError:
            st.error(f"⚠️ 找不到画布引擎文件！确保 `canvas_engine.html` 在 app.py 同目录下。")

    # ==========================================
    # 🌟 右侧对话创作中心 (管理参考图 / 出图记录 / 记账)
    # ==========================================
    with col_creator:
        st.markdown("### 💬 创作创作中心")
        st.caption(f"剩余可制图次数: {int(st.session_state.balance_points // image_cost)} 张")
        
        c1, c2 = st.columns([1,1])
        with c1: st.button("T 添加到文本参考", disabled=True, use_container_width=True)
        with c2: st.button("🗑️ 刷新对话", on_click=clear_workspace_tasks, use_container_width=True)
        
        st.divider()

        # 对话创作区 (参考图4风格)
        with st.container(height=650):
            # 🌟 核心功能：参考图列表 (点击AddToDialogue后，数据会瞬间在这出现)
            if st.session_state.context_images:
                st.markdown("📎 对话参考图栏 (点击AddToDialogue后数据传回此)")
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
            prompt_input = st.text_input("💬 输入画面描述，会在右边弹出详细历史...", placeholder="Seedance 2.0 创作描述，左侧选择元素AddToDialogue即可...")
            btn_generate = st.button("✨ 立即生成 (并记账成本)", key="btn_invoke_gen", type="primary")

            # 🌟 处理生成请求 (完美对接上一版管理对账系统)
            if btn_generate:
                if not prompt_input:
                    st.error("❌ 请输入画面描述指令！")
                else:
                    # 获取底图和遮罩参考逻辑 (简化演示，V4架构)
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
                        # 发送请求
                        st.toast("正在向云端提交生成任务...")
                        gen_res = requests.post("https://grsai.dakka.com.cn/v1/draw/completions", headers=headers, json=payload, verify=False).json()
                        
                        if gen_res.get("code") == 0:
                            # 将任务记录存入工作台历史项目文件
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
                            # 保存到文件
                            save_json(INVOKE_PROJECT_FILE, st.session_state.invoke_tasks_list)
                            
                            st.toast("🎉 任务已排队，生成进度小人🏃‍♂️已在队列历史弹出。")
                            st.rerun()
                        else:
                            st.error(f"⚠️ 出图接口报错：{gen_res.get('msg', gen_res)}")
                    except Exception as e:
                        st.error(f"❌ 系统异常：{e}")

            st.divider()
            st.caption("对话历史记录 (失败不扣成本)")
            
            # --- 精致对话卡片历史区 (参考 Jimeng V4风格) ---
            for task in reversed(st.session_state.invoke_tasks_list):
                with st.container():
                    st.markdown(f"**[{task['time_str']}] ✍️You:** {task['prompt'][:25]}...")
                    st.caption(f"参考图: {task['ref_count']}张")
                    
                    # 进度动画小人 (从 V4.4 逻辑对接过来)
                    if task['status'] == "running":
                        if st.button("🏃‍♂️ 追踪动画进度", key=f"btn_track_{task['task_id']}"):
                            # 直接调用主app.py定义的进度动画弹窗逻辑，它会自动处理扣款！
                            st.session_state.invoke_tasks_accounted = task # 标记哪个激活码和项目要扣款
                            st.toast("正在开启生成追踪进度动画...")
                            st.stop()
                            # 处理 st.experimental_dialog("🔍 实时生图进度", task['task_id'], task['prompt'], active_user_key)
                    
                    elif task['status'] == "succeeded":
                        html_res = f'<img src="{task["url"]}" style="width:100%; border-radius:8px;">'
                        st.markdown(html_res, unsafe_allow_html=True)
                        st.markdown(f"**[📥 下载高清原图]({task['url']})**")
                        
                        # 🌟 核心需求：生成的图片，也可点击魔法加载回画布里
                        if st.button("🪄 点击魔法加载回画布工作台", key=f"load_{task['task_id']}"):
                            # 将 URL 数据准备传给 data_sync 组件，强制 JS 加载
                            st.session_state.canvas_load_image_cache = task['url']
                            st.rerun()
                            
                    elif task['status'] == "failed":
                        st.error(f"❌ 失败: 安全审查拦截/系统异常 (失败不扣除额度)")
                        
                    st.divider()
                    
    # ==========================================
    # 数据链路处理 (核心黑科技下半段)
    # ==========================================
    # 当有生成成功的图片缓存时，通过 components 组件触发 JS，加载回 Fabric 画布
    if st.session_state.canvas_load_image_cache:
        url = st.session_state.canvas_load_image_cache
        # 通过 inject JS 的方式触发全局 JS 函数
        st.markdown(f'<hr style="border:none; height:0;"><script>window.stInjectCache = "{url}";</script>', unsafe_allow_html=True)
        # 清除缓存，防死循环
        st.session_state.canvas_load_image_cache = None
