import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
from datetime import datetime
import io
from certs_db import APPROVED_CERTIFICATES

# 1. 設定 Gemini API (保留原密鑰邏輯，不做任何變動)
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("請在 Streamlit Cloud Secrets 中設定 API Key")

model = genai.GenerativeModel(model_name="models/gemini-2.5-flash")

st.set_page_config(page_title="南亞技術學院 - 專業畢業門檻自動檢核系統", layout="wide")

# 初始化 Session State
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

# --- 💡 點數計算輔助函式 ---
def calculate_cert_points(level, issuer):
    """根據證照級數與發證單位，自動計算門檻點數"""
    lvl = str(level)
    isr = str(issuer)
    
    # 判斷是否為政府機構或國際證照
    is_gov_or_intl = any(keyword in isr.lower() for keyword in [
        "勞動部", "考試院", "環保署", "經濟部", "交通部", "教育部", "觀光署", "民航局", "農業部", "客家委員會", "原住民族委員會",
        "microsoft", "cisco", "autodesk", "adobe", "certiport", "trimble", "linux", "red hat", "sun microsystems", "ec-council", "check point"
    ])
    
    # 1. 甲級 / 進階 判定
    if "甲" in lvl or "進階" in lvl or "n2" in lvl.lower() or "master" in lvl.lower() or "大師" in lvl:
        return 12 if is_gov_or_intl else 9
        
    # 2. 乙級 / 普考 / 單一級 判定
    elif "乙" in lvl or "單一" in lvl or "普考" in lvl or "中高級" in lvl or "n3" in lvl.lower():
        return 8 if is_gov_or_intl else 5
        
    # 3. 丙級 / 初級 / 實用級 / 核心能力 判定
    else:
        return 4 if is_gov_or_intl else 2

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
    
    # --- 💡 側邊欄動態顯示當前點數與畢業進度 ---
    valid_records = [r for r in st.session_state["history"] if "✅" in r["檢核狀態"]]
    total_points = sum(r["所得點數"] for r in valid_records)
    
    st.sidebar.subheader("🎯 畢業門檻點數累計")
    st.sidebar.metric(label="當前總點數", value=f"{total_points} / 12 點")
    
    # 進度條顯示 (最高到 100%)
    progress_val = min(total_points / 12, 1.0)
    st.sidebar.progress(progress_val)
    
    if total_points >= 12:
        st.sidebar.success("🎉 已達畢業門檻標準！")
    else:
        st.sidebar.warning(f"⏳ 尚缺 {12 - total_points} 點達標畢業門檻")
        
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
                
                current_dept = st.session_state["user_dept"]
                dept_certs = APPROVED_CERTIFICATES.get(current_dept, [])
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

                    ai_cert_name = result_list
                    status_text = result_list
                    
                    # 預設資料庫對齊欄位
                    matched_level = "依圖片判定"
                    matched_issuer = "依圖片判定"
                    cert_points = 0
                    
                    # 檢查 AI 判定是否成功達標
                    is_passed = ("達標" in status_text or "Passed" in status_text) and ("未達標" not in status_text and "Failed" not in status_text)
                    
                    # 如果通過，從 Python 資料庫查找詳細級數與單位以精準計算點數
                    if is_passed:
                        for cert in dept_certs:
                            if cert["名稱"] in ai_cert_name or ai_cert_name in cert["名稱"]:
                                matched_level = cert["級數"]
                                matched_issuer = cert["發證單位"]
                                break
                        # 計算點數
                        cert_points = calculate_cert_points(matched_level, matched_issuer)
                        final_status = "✅ 檢核通過"
                    else:
                        final_status = f"❌ 檢核失敗 ({status_text})"

                    new_record = {
                        "檢核時間": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "學生姓名": st.session_state["user_name"],
                        "就讀系所": st.session_state["user_dept"],
                        "證照顯示姓名": result_list,
                        "證照核定名稱": ai_cert_name,
                        "官方審定級數": matched_level,
                        "官方發證單位": matched_issuer,
                        "所得點數": cert_points,
                        "證照編號": result_list,
                        "檢核狀態": final_status,
                        "AI 審核原因": result_list
                    }
                    
                    st.session_state["history"].append(new_record)
                    
                    # 畫面即時反饋
                    if is_passed:
                        st.success(f"✅ 檢核通過！本張證照核定點數：{cert_points} 點。")
                    else:
                        st.error(f"❌ 檢核未通過：{status_text}")
                    
                    st.write(f"**🕵️ AI 專家分析：** {new_record['AI 審核原因']}")
                    st.write(f"**📋 系統對齊資料：** 發證單位：`{matched_issuer}` | 核定級數：`{matched_level}` | 核發點數：`{cert_points}` 點")
                    st.write("---")
                    
                    # 強制刷新頁面，讓側邊欄的點數計數器即時更新
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"自動化檢核失敗：{e}")

    # --- 顯示歷史紀錄 ---
    if st.session_state["history"]:
        st.divider()
        st.subheader("📋 證照檢核清單與累計報表")
        df = pd.DataFrame(st.session_state["history"])
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(label="📥 匯出個人畢業檢核報表", data=csv, file_name=f"南亞畢業檢核_{st.session_state['user_id']}_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
