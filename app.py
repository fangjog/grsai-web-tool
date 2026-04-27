import streamlit as st
import requests
import time
from PIL import Image
import io

# 你的 Grsai API Key (在服务端写死，绝不泄露给客户)
GRSAI_API_KEY = "sk-7b4232dd897f426f9e7b3145073a59b8" 

# 简单的卡密验证系统 (正式商用可以对接发卡平台API)
VALID_KEYS = ["vip888", "test1234"]

st.set_page_config(page_title="image-2生图", page_icon="🎨")
st.title("🚀 iamge-2生图")

# 1. 登录验证模块
user_key = st.text_input("🔑 请输入激活码/卡密", type="password")

if user_key not in VALID_KEYS:
    st.warning("请输入有效的激活码以使用系统。")
    st.stop() # 卡密不对，直接停止渲染后续页面

st.success("✅ 验证通过，欢迎使用！")

# 2. 交互界面设计
st.markdown("---")
prompt = st.text_area("📝 请输入画面描述 (支持中文直出)", height=150)
aspect_ratio = st.selectbox("📏 选择画幅比例", ["16:9", "9:16", "1:1", "3:4", "4:3"])

# 3. 核心生图逻辑
if st.button("✨ 立即生成 (消耗1次额度)"):
    if not prompt:
        st.error("描述不能为空！")
    else:
        # 进度提示
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        # --- 步骤 A：提交任务 ---
        status_text.info("📡 正在向服务器提交任务...")
        submit_url = "https://grsai.dakka.com.cn/v1/draw/completions"
        headers = {
            "Authorization": f"Bearer {GRSAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-image-2",
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "webHook": "-1",
            "shutProgress": True
        }
        
        try:
            sub_res = requests.post(submit_url, headers=headers, json=payload, verify=False).json()
            if sub_res.get("code") == 0:
                task_id = sub_res["data"]["id"]
                progress_bar.progress(20)
                
                # --- 步骤 B：轮询查询 ---
                query_url = "https://grsai.dakka.com.cn/v1/draw/result"
                for i in range(30): # 最多等一分半钟
                    status_text.warning(f"⏳ 任务排队中，请稍候... (第 {i+1} 次查询)")
                    q_res = requests.post(query_url, headers=headers, json={"id": task_id}, verify=False).json()
                    
                    if q_res.get("code") == 0 and q_res["data"]["status"] == "succeeded":
                        img_url = q_res["data"]["results"][0]["url"]
                        status_text.success("✅ 图片生成完毕！正在下载...")
                        progress_bar.progress(100)
                        
                        # 展示图片
                        img_data = requests.get(img_url, verify=False).content
                        image = Image.open(io.BytesIO(img_data))
                        st.image(image, caption="为您生成的画面")
                        
                        # 提供下载按钮
                        st.download_button(label="💾 下载高清原图", data=img_data, file_name=f"{task_id}.jpg", mime="image/jpeg")
                        break
                        
                    elif q_res.get("code") == 0 and q_res["data"]["status"] == "failed":
                        status_text.error("❌ 生成失败，可能包含违规词汇。")
                        break
                        
                    time.sleep(3)
                    progress_bar.progress(min(20 + i*2, 90)) # 假进度条动画
            else:
                status_text.error(f"提交失败：{sub_res}")
        except Exception as e:
            status_text.error(f"网络错误：{e}")
streamlit
requests
pillow
