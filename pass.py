import streamlit as st
import google.generativeai as genai
from PIL import Image
import pandas as pd
from datetime import datetime
import io

# 1. 設定 Gemini API
genai.configure(api_key="AIzaSyBdJw5uHOxcAbLjHrBXcI7wrD1nOt8nMeM")
model = genai.GenerativeModel(model_name="models/gemini-2.5-flash")

st.set_page_config(page_title="專業證照檢核系統", layout="wide")

# 初始化 Session State
if "login" not in st.session_state:
    st.session_state["login"] = False
if "history" not in st.session_state:
    st.session_state["history"] = []

# 使用者名單
USER_DB = {
    "admin": "1234",
    "1111227144": "1234",
    "test": "test"
}

# --- 介面邏輯 ---
if not st.session_state["login"]:
    st.title("🪪 證照管理系統 - 登入")
    user_id = st.text_input("帳號")
    password = st.text_input("密碼", type="password")
    if st.button("登入"):
        if user_id in USER_DB and USER_DB[user_id] == password:
            st.session_state["login"] = True
            st.rerun()
        else:
            st.error("帳號或密碼錯誤")
else:
    # 已登入介面
    st.sidebar.title("控制面板")
    if st.sidebar.button("登出系統"):
        st.session_state["login"] = False
        st.rerun()

    st.title("🔍 專業證照 AI 辨識與防偽檢核")
    
    # 上傳功能
    uploaded_file = st.file_uploader("請上傳證照照片 (JPG/PNG)", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="待處理證照", width=500)
        
        if st.button("開始辨識"):
            with st.spinner("AI 正在進行深度鑑識中..."):
                # 升級後的 Prompt：強調印章與防偽
                prompt = """
                你是一個專業的證照數位鑑識專家。請嚴格分析這張圖片，並以格式（姓名,證照名稱,證照號碼,有效日期,合格狀態,判定原因）回傳，中間用逗號隔開。
                
                【合格判定標準（極嚴格）】：
                1. **印章檢查(核心)**：必須有清晰的發照單位「紅印」、「鋼印」或「公章」。
                   - 若無印章，或印章文字與發照單位不符，判定為「不合格」。
                   - 檢查印章邊緣，若看起來像數位貼上的（無自然透出或重疊感），判定為「不合格」。
                2. **數位篡改偵測**：檢查文字及印章周邊是否有異常色塊、字體不一、或是修圖抹除痕跡。
                3. **物理特徵**：真實拍攝的證照應有微小陰影、紙張紋理。若為過於完美的純白數位檔，需加註懷疑。
                4. **資訊完整性**：必須包含姓名、證照名稱、證號。
                
                回傳格式範例：
                陳小明,乙級技術士證,No.123,2025/12/31,合格,印章清晰且未發現修圖痕跡。
                """
                
                try:
                    response = model.generate_content([prompt, image])
                    res_text = response.text.strip()
                    
                    # 處理 AI 回傳的字串
                    result_list = [item.strip() for item in res_text.split(',')]
                    
                    # 建立紀錄
                    new_record = {
                        "辨識時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "姓名": result_list[0] if len(result_list) > 0 else "未知",
                        "證照名稱": result_list[1] if len(result_list) > 1 else "未知",
                        "證號": result_list[2] if len(result_list) > 2 else "未知",
                        "有效期": result_list[3] if len(result_list) > 3 else "未知",
                        "合格狀態": result_list[4] if len(result_list) > 4 else "不合格",
                        "判定原因": result_list[5] if len(result_list) > 5 else "AI 格式回傳異常"
                    }
                    
                    # 存入歷史紀錄
                    st.session_state["history"].append(new_record)
                    
                    # 顯示結果
                    if new_record["合格狀態"] == "合格":
                        st.success(f"✅ 判定結果：{new_record['合格狀態']}")
                    else:
                        st.error(f"❌ 判定結果：{new_record['合格狀態']}")
                        
                    st.write(f"**🕵️ 專家分析原因：** {new_record['判定原因']}")
                    st.write("---")
                    
                except Exception as e:
                    st.error(f"辨識失敗：{e}")

    # --- 顯示歷史紀錄與下載 ---
    if st.session_state["history"]:
        st.divider()
        st.subheader("📋 辨識歷史紀錄 (含防偽判斷)")
        df = pd.DataFrame(st.session_state["history"])
        st.dataframe(df, use_container_width=True)

        # CSV 匯出 (UTF-8-SIG 確保 Excel 不亂碼)
        csv = df.to_csv(index=False).encode('utf-8-sig')

        st.download_button(
            label="📥 匯出完整報表 (CSV)",
            data=csv,
            file_name=f"證照鑑定紀錄_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
