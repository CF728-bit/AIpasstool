import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
from datetime import datetime
import io
# --- 關鍵修正 1：引入外部證照資料庫檔案 ---
from certs_db import APPROVED_CERTIFICATES

# 1. 設定 Gemini API (保留您原本的密鑰邏輯，完全不變動)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("請在 Streamlit Cloud Secrets 中設定 API Key")

model = genai.GenerativeModel(model_name="models/gemini-2.5-flash")

st.set_page_config(page_title="南亞技術學院 - 專業畢業門檻自動檢核系統", layout="wide")

# --- 初始化所有需要的 Session State ---
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

# 使用者資料庫 (可依需求自行擴充測試帳號)
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
            st.session_state["user_name"] = USER_INFO[user_id]["name"]
            st.session_state["user_dept"] = USER_INFO[user_id]["dept"]
            st.rerun()
        else:
            st.error("帳號或密碼錯誤")
else:
    # --- 已登入介面 ---
    st.sidebar.title("南亞校務管理")
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
        
        if st.button("檢核"):
            with st.spinner(f"AI 正在比對是否符合 {st.session_state['user_dept']} 專業門檻..."):
                
                # --- 關鍵修正 2：自動提取該登入學生的系所白名單 ---
                current_dept = st.session_state["user_dept"]
                dept_certs = APPROVED_CERTIFICATES.get(current_dept, [])
                
                # 將結構化的白名單轉換為純文字，塞進 Prompt 供 AI 比對
                whitelist_text = "\n".join([f"- {c['名稱']} (級數: {c['級數']}, 發證單位: {c['發證單位']})" for c in dept_certs])
                
                prompt = f"""
                你是一個「南亞技術學院」的畢業資格審核員。
                目前的受檢學生姓名為：【{st.session_state['user_name']}】，系所為：【{current_dept}】。
                
                【該系所學校核可的正式證照白名單】：
                {whitelist_text if dept_certs else "（管理員模式或此系所未設定白名單，請依常理審查）"}
                
                請分析這張證照圖片，並嚴格按照格式（姓名,判定證照所屬系所,證照名稱,證號,檢核狀態,判定原因）回傳，中間用逗號隔開。
                
                【專業判定與本人驗證標準】：
                1. 姓名比對：證照姓名必須完全符合【{st.session_state['user_name']}】，否則狀態為「未達標 (非本人證照)」。
                2. 證照比對：辨識出來的證照名稱，必須在上述提供的【正式證照白名單】內，或者名稱高度相關（如縮寫、同義詞）。若完全無關或非核可證照，狀態為「未達標 (非核可證照)」。
                3. 達標條件：姓名正確 + 證照符合白名單 + 有印章 = 「達標 (Passed)」。
                
                回傳格式範例：
                {st.session_state['user_name']},{current_dept},人工智慧檢定,A123,達標 (Passed),符合專業白名單且為本人持證。
                """
                
                try:
                    response = model.generate_content([prompt, image])
                    res_text = response.text.strip()
                    result_list = [item.strip() for item in res_text.split(',', 5)]
                    
                    while len(result_list) < 6:
                        result_list.append("資料缺失")

                    # --- 關鍵修正 3：後台進行二次確認，自動在清單中抓取官方對齊的「發證單位」與「級數」 ---
                    ai_cert_name = result_list[2]
                    matched_level = "依圖片判定"
                    matched_issuer = "依圖片判定"
                    
                    for cert in dept_certs:
                        if cert["名稱"] in ai_cert_name or ai_cert_name in cert["名稱"]:
                            matched_level = cert["級數"]
                            matched_issuer = cert["發證單位"]
                            break

                    new_record = {
                        "檢核時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "學生姓名": st.session_state["user_name"],
                        "就讀系所": st.session_state["user_dept"],
                        "證照顯示姓名": result_list[0],
                        "證照核定名稱": ai_cert_name,
                        "官方審定級數": matched_level,
                        "官方發證單位": matched_issuer,
                        "證照編號": result_list[3],
                        "檢核狀態": result_list[4],
                        "AI 審核原因": result_list[5]
                    }
                    
                    st.session_state["history"].append(new_record)
                    
                    # --- 顯示結果 (邏輯加強版) ---
                    status = str(new_record["檢核狀態"])
                    reason = str(new_record["AI 審核原因"])
                    
                    is_passed = ("達標" in status or "Passed" in status) and ("未達標" not in status and "Failed" not in status)
                    
                    if is_passed:
                        st.success(f"✅ 檢核通過：{status}")
                    else:
                        st.error(f"❌ 檢核失敗：{status}")
                    
                    st.write(f"**🕵️ AI 專家分析：** {reason}")
                    st.write(f"**📋 系統對齊資料：** 官方發證單位：`{matched_issuer}` | 核定級數：`{matched_level}`")
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
