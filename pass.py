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

# --- 關鍵修正 1：初始化所有需要的 Session State ---
if "login" not in st.session_state:
    st.session_state["login"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = ""
if "user_name" not in st.session_state:
    st.session_state["user_name"] = ""
if "user_dept" not in st.session_state:
    st.session_state["user_dept"] = ""
if "history" not in st.session_state:
    st.session_state["history"] = []

# 使用者資料庫
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
            # --- 關鍵修正 2：登入成功時確實存入所有資訊 ---
            st.session_state["login"] = True
            st.session_state["user_id"] = user_id
            st.session_state["user_name"] = USER_INFO[user_id]["name"]
            st.session_state["user_dept"] = USER_INFO[user_id]["dept"]
            st.rerun()
        else:
            st.error("帳號或密碼錯誤")
else:
    # --- 已登入介面 ---
    st.sidebar.title("南亞校務管理")
    # 使用 markdown 顯示姓名與資訊
    st.sidebar.markdown(f"### 👤 {st.session_state['user_name']}")
    st.sidebar.write(f"**學號：** {st.session_state['user_id']}")
    st.sidebar.write(f"**系所：** {st.session_state['user_dept']}")
    st.sidebar.divider()
    
    if st.sidebar.button("登出系統", use_container_width=True):
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
                prompt = f"""
                你是一個「南亞技術學院」的畢業資格審核員。
                目前的受檢學生姓名為：【{st.session_state['user_name']}】，系所為：【{st.session_state['user_dept']}】。
                
                請分析這張證照圖片，並嚴格按照格式（姓名,判定證照所屬系所,證照名稱,證號,檢核狀態,判定原因）回傳，中間用逗號隔開。
                
                【專業判定與本人驗證標準】：
                1. 姓名比對：證照姓名必須是【{st.session_state['user_name']}】，否則狀態為「未達標 (非本人證照)」。
                2. 系所匹配：證照內容必須屬於【{st.session_state['user_dept']}】專業領域，否則為「未達標 (系所不符)」。
                3. 專業定義：資工(程式、AI、網路)、餐飲(烹調、烘焙)、設計(製圖、繪圖)、企管(會計、專案)。
                4. 達標條件：姓名正確 + 系所正確 + 有印章 = 「達標 (Passed)」。
                
                回傳格式範例：
                {st.session_state['user_name']},{st.session_state['user_dept']},人工智慧檢定,A123,達標 (Passed),符合專業且為本人持證。
                """
                
                try:
                    response = model.generate_content([prompt, image])
                    res_text = response.text.strip()
                    result_list = [item.strip() for item in res_text.split(',', 5)]
                    
                    while len(result_list) < 6:
                        result_list.append("資料缺失")

                    new_record = {
                        "檢核時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "證照顯示姓名": result_list[0],
                        "學生系所": st.session_state["user_dept"],
                        "證照判定系所": result_list[1],
                        "證照名稱": result_list[2],
                        "證號": result_list[3],
                        "檢核狀態": result_list[4],
                        "AI 審核原因": result_list[5]
                    }
                    
                    st.session_state["history"].append(new_record)
                    
                    # --- 顯示結果 (邏輯加強版) ---
                    status = str(new_record["檢核狀態"])
                    reason = str(new_record["AI 審核原因"])
                    
                    # 只有同時滿足「有達標關鍵字」且「沒有未達標關鍵字」才顯示成功
                    is_passed = ("達標" in status or "Passed" in status) and ("未達標" not in status and "Failed" not in status)
                    
                    if is_passed:
                        st.success(f"✅ 檢核通過：{status}")
                    else:
                        st.error(f"❌ 檢核失敗：{status}")
                    
                    st.write(f"**🕵️ AI 專家分析：** {reason}")
                    st.write("---")
                    
                except Exception as e:
                    st.error(f"自動化檢核失敗：{e}")

    # --- 顯示歷史紀錄 ---
    if st.session_state["history"]:
        st.divider()
        st.subheader("📋 證照檢核清單")
        df = pd.DataFrame(st.session_state["history"])
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(label="📥 匯出報表", data=csv, file_name=f"畢業檢核_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
