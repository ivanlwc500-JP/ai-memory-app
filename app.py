import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json

# --- 頁面設定 ---
st.set_page_config(page_title="AI 隨身記憶", page_icon="📝", layout="centered")
st.title("📝 我的 AI 隨身記憶助手")

# --- 1. 讀取機密設定 (Secrets) ---
# 這些變數會從 Streamlit Cloud 的後台設定讀取
api_key = st.secrets.get("GEMINI_API_KEY")
gcp_service_account_str = st.secrets.get("GCP_SERVICE_ACCOUNT")
sheet_url = st.secrets.get("SHEET_URL")

# 檢查設定是否存在
if not api_key or not gcp_service_account_str or not sheet_url:
    st.error("設定檔不完整！請檢查 Streamlit Secrets 是否設定正確。")
    st.stop()

# --- 2. 連接 Gemini ---
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# --- 3. 連接 Google Sheet ---
@st.cache_resource
def connect_to_sheet():
    # 定義範圍
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    # 將 Secrets 裡的字串轉回 JSON
    creds_dict = json.loads(gcp_service_account_str)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # 開啟試算表
    sheet = client.open_by_url(sheet_url).sheet1
    return sheet

try:
    sheet = connect_to_sheet()
except Exception as e:
    st.error(f"連線試算表失敗，請檢查權限或 JSON 內容: {e}")
    st.stop()

# --- 4. 初始化與載入歷史記錄 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
    # 嘗試從試算表載入舊資料
    try:
        records = sheet.get_all_records()
        # 為了避免記錄太多讀取太慢，我們只取最後 20 筆 (可自行調整)
        recent_records = records[-20:] if len(records) > 20 else records
        
        for row in recent_records:
            # 確保欄位名稱跟試算表一致
            role_in_sheet = row.get("角色")
            content_in_sheet = row.get("內容")
            
            if role_in_sheet and content_in_sheet:
                # 轉換角色代碼
                role = "user" if role_in_sheet == "user" else "assistant"
                st.session_state.messages.append({"role": role, "content": content_in_sheet})
    except Exception as e:
        # 如果試算表是空的，可能會報錯，這裡忽略錯誤
        pass

# --- 5. 顯示聊天畫面 ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 6. 處理輸入與儲存 ---
if prompt := st.chat_input("今天想聊什麼？"):
    # A. 顯示並記錄用戶輸入
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # 寫入 Google Sheet (用戶)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        sheet.append_row([timestamp, "user", prompt])
    except:
        st.warning("寫入試算表失敗 (User)")

    # B. AI 思考並回答
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            # 這裡簡單地只把當前問題丟給 AI，若要上下文需傳遞 history
            response = model.generate_content(prompt)
            full_response = response.text
            message_placeholder.markdown(full_response)
        except Exception as e:
            full_response = "抱歉，AI 暫時無法回應。"
            message_placeholder.markdown(full_response)
            
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    
    # 寫入 Google Sheet (AI)
    try:
        sheet.append_row([timestamp, "model", full_response])
    except:
        st.warning("寫入試算表失敗 (AI)")
