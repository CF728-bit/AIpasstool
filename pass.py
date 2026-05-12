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

model = genai.GenerativeModel(model_name="models/gemini-2.5-flash")

st.set_page_config(page_title="南亞技術學院 - 專業畢業門檻自動檢核系統", layout="wide")

# 初始化 Session State
if "login" not in st.session_state:
    st.session_state["login"] = False
if "history" not in st.session_state:
    st.session_state["history"] = []

# 使用者名單與所屬系所對照
USER_INFO = {
    "admin": {"pw": "1234", "dept": "管理員", "name": "系統管理員"},
    "1111227144": {"pw": "1234", "dept": "資訊工程系", "name": "陳興翰"},
    "1111227113": {"pw": "1234", "dept": "資訊工程系", "name": "林佑德"},
    "nanya_design": {"pw": "1234", "dept": "室內設計系", "name": "李大華"}
}

# --- 介面邏輯 ---
if not st.session_state["login"]:
    st.title("🏫 南亞技術學院 - 畢業門檻自動化系統")
    st.info("歡迎使用全校專業證照自動檢核系統")
    user_id = st.text_input("學號 / 帳號")
    password = st.text_input("密碼", type="password")
    if st.button("登入系統"):
        if user_id in USER_INFO and USER_INFO[user_id]["pw"] == password:
            st.session_state["login"] = True
            st.session_state["user_id"] = user_id
            st.session_state["user_dept"] = USER_INFO[user_id]["dept"]
            st.rerun()
        else:
            st.error("帳號或密碼錯誤")
else:
    # 已登入介面
    st.sidebar.title("南亞校務管理")
    st.sidebar.write(f"目前登入者：{st.session_state['user_id']}")
    st.sidebar.write(f"所屬系所：{st.session_state['user_dept']}")
    if st.sidebar.button("登出系統"):
        st.session_state["login"] = False
        st.rerun()

    st.title("🔍 全校各系專業證照 AI 辨識與檢核")
    st.markdown(f"**當前審核模式：【{st.session_state['user_dept']}】畢業門檻比對**")
    
    uploaded_file = st.file_uploader("請上傳您的專業證照照片 (JPG/PNG)", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="待檢核之原始證照", width=500)
        
        if st.button("🚀 啟動專業對口自動化檢核"):
            with st.spinner(f"AI 正在比對是否符合 {st.session_state['user_dept']} 專業門檻..."):
                
                # 動態建構 Prompt，根據登入者系所要求 AI 嚴格把關
                prompt = f"""
                你是一個「南亞技術學院」的畢業資格審核員。
                目前的受檢學生所屬系所為：【{st.session_state['user_dept']}】。
                
                請分析這張證照圖片，並嚴格按照格式（姓名,判定證照所屬系所,證照名稱,證號,檢核狀態,判定原因）回傳，中間用逗號隔開。
                
                【專業對口判定標準】：
                1. **系所匹配 (最重要)**：
                   - 如果證照內容「不屬於」【{st.session_state['user_dept']}】的專業領域，檢核狀態必須設為「未達標 (系所不符)」。
                   - 範例：資工系學生拿「中餐丙級」證照，應判定為「未達標」。
                2. **專業領域定義**：
                   - 資訊工程系：程式設計、網路管理、人工智慧、資訊安全、硬體裝修、TQC/MOS等。
                   - 餐飲廚藝系：中西餐烹調、烘焙、食品安全、調酒、餐飲服務等。
                   - 室內設計系：建築製圖、CAD繪圖、室內裝修、視覺傳達等。
                   - 企業管理系：門市服務、會計、專案管理、行銷企劃等。
                3. **印章檢核**：必須具備正式機構印章。
                4. **達標狀態**：必須「同時符合」系所專業且「具備有效印章」，才設為「達標 (Passed)」。
                
                回傳格式範例：
                陳興翰,資訊工程系,人工智慧乙級能力檢定,雙福三創第1377號,達標 (Passed),證照符合資工系專業領域且印章完整。
                """
                
                try:
                    response = model.generate_content([prompt, image])
                    res_text = response.text.strip()
                    
                    result_list = [item.strip() for item in res_text.split(',', 5)]
                    
                    while len(result_list) < 6:
                        result_list.append("資料缺失")

                    new_record = {
                        "檢核時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "學生姓名": result_list[0],
                        "學生系所": st.session_state["user_dept"],
                        "證照判定系所": result_list[1],
                        "證照名稱": result_list[2],
                        "證號": result_list[3],
                        "檢核狀態": result_list[4],
                        "AI 審核原因": result_list[5]
                    }
                    
                    st.session_state["history"].append(new_record)
                    
                    # 顯示結果
                    status = str(new_record["檢核狀態"])
                    if "達標" in status or "Passed" in status:
                        st.success(f"✅ 檢核通過：{status}")
                    else:
                        st.error(f"❌ 檢核失敗：{status}")
                    
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

        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 匯出全校畢業檢核報表 (CSV)",
            data=csv,
            file_name=f"南亞畢業檢核_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
