import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
from datetime import datetime
import io

# 1. 設定 Gemini API
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    # 這裡不要放任何真實的金鑰，避免再次被封鎖
    st.error("請在 Streamlit Cloud Secrets 中設定 API Key")

model = genai.GenerativeModel(model_name="models/gemini-2.5-flash")

st.set_page_config(page_title="南亞技術學院 - 專業畢業門檻自動檢核系統", layout="wide")

# 初始化 Session State
if "login" not in st.session_state:
    st.session_state["login"] = False
if "history" not in st.session_state:
    st.session_state["history"] = []

# 使用者名單 (包含不同科系的測試帳號)
USER_DB = {
    "admin": "1234",
    "1111227144": "1234", # 資工系測試
    "nanya_cook": "1234", # 餐飲系測試
    "nanya_design": "1234" # 設計系測試
}

# --- 介面邏輯 ---
if not st.session_state["login"]:
    st.title("🏫 南亞技術學院 - 畢業門檻自動化系統")
    st.info("歡迎使用全校專業證照自動檢核系統")
    user_id = st.text_input("學號 / 帳號")
    password = st.text_input("密碼", type="password")
    if st.button("登入系統"):
        if user_id in USER_DB and USER_DB[user_id] == password:
            st.session_state["login"] = True
            st.session_state["user_id"] = user_id
            st.rerun()
        else:
            st.error("帳號或密碼錯誤")
else:
    # 已登入介面
    st.sidebar.title("南亞校務管理")
    st.sidebar.write(f"目前登入者：{st.session_state['user_id']}")
    if st.sidebar.button("登出系統"):
        st.session_state["login"] = False
        st.rerun()

    st.title("🔍 全校各系專業證照 AI 辨識與檢核")
    st.markdown("""
    **本系統已擴充支援南亞技術學院各系門檻：**
    *   **資工系：** 程式設計、網管相關證照
    *   **餐飲系：** 廚藝丙/乙級、烘焙、食品安全證照
    *   **設計系：** 室內設計、電腦繪圖(ACA/TQC)相關證照
    *   **企管系：** 專案管理、門市服務、會計相關證照
    """)
    
    # 上傳功能
    uploaded_file = st.file_uploader("請上傳您的專業證照照片 (JPG/PNG)", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="待檢核之原始證照", width=500)
        
        if st.button("🚀 啟動全校通用自動化檢核"):
            with st.spinner("AI 正在根據南亞各系畢業門檻進行 Mapping 比對..."):
                # 擴充後的 Prompt：加入多科系判定邏輯
                prompt = """
                你是一個「南亞技術學院」的畢業資格審核員。請分析這張圖片，並嚴格按照格式（姓名,所屬系所,證照名稱,證號,檢核狀態,判定原因）回傳，中間用逗號隔開。
                
                【全校專業門檻判定標準】：
                1. **系所判定**：根據證照內容自動判定屬於「資訊工程系」、「餐飲廚藝系」、「室內設計系」或「企業管理系」。
                2. **印章防偽(關鍵)**：必須有清晰的政府機關或校方紅印、鋼印。無印章或印章可疑者判定為「未達標」。
                3. **達標判定**：
                   - 資工系：程式、網管、電腦硬體相關。
                   - 餐飲系：廚藝、烘焙、餐旅服務相關。
                   - 設計系：繪圖、設計、建築相關。
                   - 企管系：管理、行銷、會計相關。
                   符合上述專業類別且資訊完整、印章清晰，狀態設為「達標 (Passed)」。
                
                回傳格式範例：
                王小明,餐飲廚藝系,中餐烹調丙級,No.7788,達標 (Passed),具備勞動部正式印章且符合本系畢業門檻。
                """
                
                try:
                    response = model.generate_content([prompt, image])
                    res_text = response.text.strip()
                    result_list = [item.strip() for item in res_text.split(',')]
                    
                    new_record = {
                        "檢核時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "姓名": result_list if len(result_list) > 0 else "未知",
                        "判定系所": result_list if len(result_list) > 1 else "其他",
                        "證照名稱": result_list if len(result_list) > 2 else "未知",
                        "證號": result_list if len(result_list) > 3 else "未知",
                        "檢核狀態": result_list if len(result_list) > 4 else "未達標 (Failed)",
                        "AI 審核原因": result_list if len(result_list) > 5 else "格式異常"
                    }
                    
                    st.session_state["history"].append(new_record)
                    
                    # 顯示結果
                    if "Passed" in new_record["檢核狀態"]:
                        st.success(f"✅ 判定為 {new_record['判定系所']}：{new_record['檢核狀態']}")
                    else:
                        st.error(f"❌ 檢核結果：{new_record['檢核狀態']}")
                    
                    st.write(f"**🕵️ AI 專家分析：** {new_record['AI 審核原因']}")
                    st.write("---")
                    
                except Exception as e:
                    st.error(f"自動化檢核失敗：{e}")

    # --- 顯示歷史紀錄與匯出報表 ---
    if st.session_state["history"]:
        st.divider()
        st.subheader("📋 南亞技術學院 - 學生歷年證照檢核清單")
        df = pd.DataFrame(st.session_state["history"])
        st.dataframe(df, use_container_width=True)

        # 匯出報表
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 匯出全校畢業檢核報表 (CSV)",
            data=csv,
            file_name=f"南亞畢業檢核_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
