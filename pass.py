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
    st.error("請在 Streamlit Cloud Secrets 中設定 API Key")

# 這裡建議使用穩定版 flash 模型
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

st.set_page_config(page_title="南亞技術學院 - 專業畢業門檻自動檢核系統", layout="wide")

# 初始化 Session State
if "login" not in st.session_state:
    st.session_state["login"] = False
if "history" not in st.session_state:
    st.session_state["history"] = []

# 使用者名單
USER_DB = {
    "admin": "1234",
    "1111227144": "1234",
    "nanya_cook": "1234",
    "nanya_design": "1234"
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
    *   **資工系、餐飲系、設計系、企管系**
    """)

    uploaded_file = st.file_uploader("請上傳您的專業證照照片 (JPG/PNG)", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="待檢核之原始證照", width=500)

        if st.button("🚀 啟動全校通用自動化檢核"):
            with st.spinner("AI 正在根據南亞各系畢業門檻進行比對..."):
                prompt = """
                你是一個「南亞技術學院」的畢業資格審核員。請分析這張圖片，並嚴格按照格式（姓名,所屬系所,證照名稱,證號,檢核狀態,判定原因）回傳，中間用逗號隔開。

                【全校專業門檻判定標準】：
                1. 系所判定：根據內容判定屬於 資工、餐飲、設計 或 企管系。
                2. 印章防偽：必須有清晰印章。
                3. 達標判定：符合專業領域且具備有效印章，狀態設為「達標 (Passed)」。

                回傳格式範例：
                陳興翰,資訊工程系,人工智慧乙級能力檢定,雙福三創第1377號,達標 (Passed),具備正式協會印章。
                """

                try:
                    # 傳送給 AI
                    response = model.generate_content([prompt, image])
                    res_text = response.text.strip()

                    # 處理字串切割 (限制切 5 刀，避免原因中的逗號跑位)
                    result_list = [item.strip() for item in res_text.split(',', 5)]

                    # 補足長度防止出錯
                    while len(result_list) < 6:
                        result_list.append("資料缺失")

                    new_record = {
                        "檢核時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "姓名": result_list[0],
                        "判定系所": result_list[1],
                        "證照名稱": result_list[2],
                        "證號": result_list[3],
                        "檢核狀態": result_list[4],
                        "AI 審核原因": result_list[5]
                    }

                    st.session_state["history"].append(new_record)

                    # 顯示結果
                    status = str(new_record["檢核狀態"])
                    if "達標" in status or "Passed" in status:
                        st.success(f"✅ 判定結果：{status}")
                    else:
                        st.error(f"❌ 判定結果：{status}")

                    st.write(f"**🕵️ AI 專家分析：** {new_record['AI 審核原因']}")
                    st.write("---")

                except Exception as e:
                    st.error(f"自動化檢核失敗：{e}")

    # --- 顯示歷史紀錄與匯出 ---
    if st.session_state["history"]:
        st.divider()
        st.subheader("📋 南亞技術學院 - 學生歷年證照檢核清單")
        df = pd.DataFrame(st.session_state["history"])
        st.dataframe(df, use_container_width=True)

        # 改用更穩定的 Excel 格式匯出，避免 CSV 中文亂碼問題
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='檢核報表')

        st.download_button(
            label="📥 匯出全校畢業檢核報表 (Excel)",
            data=buffer.getvalue(),
            file_name=f"南亞檢核報表_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.ms-excel",
        )
