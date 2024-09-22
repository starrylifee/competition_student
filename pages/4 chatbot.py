import openai
from openai import OpenAI
import streamlit as st
import random
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 페이지 설정 - 아이콘과 제목 설정
st.set_page_config(
    page_title="학생용 교육 도구 챗봇",  # 브라우저 탭에 표시될 제목
    page_icon="🤖",  # 브라우저 탭에 표시될 아이콘 (이모지 또는 이미지 파일 경로)
)

# Streamlit의 배경색 변경
background_color = "#F0FFF0"

# Streamlit의 기본 메뉴와 푸터 숨기기
hide_menu_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
<script>
document.addEventListener("DOMContentLoaded", function() {
    var mainMenu = document.getElementById('MainMenu');
    if (mainMenu) {
        mainMenu.style.display = 'none';
    }
    var footer = document.getElementsByTagName('footer')[0];
    if (footer) {
        footer.style.display = 'none';
    }
    var header = document.getElementsByTagName('header')[0];
    if (header) {
        header.style.display = 'none';
    }
});
</script>
"""

# Streamlit에서 HTML 및 CSS 적용
st.markdown(hide_menu_style, unsafe_allow_html=True)

# OpenAI API 클라이언트 초기화
api_keys = st.secrets["api"]["keys"]
api_keys = [key for key in api_keys if key]  # None 값 제거

if api_keys:
    selected_api_key = random.choice(api_keys)
    openai.api_key = selected_api_key  # OpenAI API 키 설정
    client = OpenAI(api_key=selected_api_key)  # 클라이언트 초기화
else:
    st.error("사용 가능한 OpenAI API 키가 없습니다.")
    st.stop()

# 노션 API 설정
NOTION_API_URL = "https://api.notion.com/v1/databases/{database_id}/query"
NOTION_API_KEY = st.secrets["notion"]["api_key"]
DATABASE_ID_CHATBOT = st.secrets["notion"]["database_id_chatbot"]

headers = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def fetch_instruction_from_notion(activity_code):
    try:
        instruction_api_url = NOTION_API_URL.format(database_id=DATABASE_ID_CHATBOT)
        instruction_query_payload = {
            "filter": {
                "property": "activity_code",
                "rich_text": {
                    "equals": activity_code
                }
            }
        }
        response = requests.post(instruction_api_url, headers=headers, json=instruction_query_payload)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        data = response.json()
        
        if "results" in data and len(data["results"]) > 0:
            # 'prompt', 'email', 'student_view' 속성이 존재하는지 확인
            properties = data["results"][0]["properties"]
            if "prompt" in properties and properties["prompt"]["rich_text"]:
                instruction = properties["prompt"]["rich_text"][0]["text"]["content"]
            else:
                instruction = ""
            
            if "email" in properties and properties["email"]["rich_text"]:
                teacher_email = properties["email"]["rich_text"][0]["text"]["content"]
            else:
                teacher_email = ""
            
            if "student_view" in properties and properties["student_view"]["rich_text"]:
                student_view = properties["student_view"]["rich_text"][0]["text"]["content"]
            else:
                student_view = ""  # 기본 제목
            
            return instruction, teacher_email, student_view
        else:
            st.sidebar.error("해당 Activity 코드를 노션에서 찾을 수 없습니다.")
            return None, None, None
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"노션 API 호출 중 오류가 발생했습니다: {e}")
        return None, None, None
    except Exception as e:
        st.sidebar.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
        return None, None, None

def send_email(chat_history, student_name, teacher_email):
    if not teacher_email:
        st.warning("교사 이메일이 설정되어 있지 않습니다.")
        return False  # 이메일 전송 실패

    # 이메일 메시지 구성
    msg = MIMEMultipart()
    msg["From"] = st.secrets["email"]["address"]
    msg["To"] = teacher_email
    msg["Subject"] = f"{student_name} 학생의 챗봇 대화 기록"

    # 대화 내용 포맷팅
    body = f"학생 이름: {student_name}\n\n대화 기록:\n\n"
    for msg_entry in chat_history:
        role = "학생" if msg_entry["role"] == "user" else "챗봇"
        body += f"{role}: {msg_entry['content']}\n"

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(st.secrets["email"]["address"], st.secrets["email"]["password"])
            server.send_message(msg)
        return True  # 이메일 전송 성공
    except Exception as e:
        st.error(f"이메일 전송에 실패했습니다: {e}")
        return False  # 이메일 전송 실패

def main():
    # 사이드바에 활동 코드 입력 필드 및 학생 이름 입력 필드 추가
    st.sidebar.header("활동 코드 및 학생 이름 입력")
    activity_code = st.sidebar.text_input("활동 코드 입력", value="", max_chars=50)
    student_name = st.sidebar.text_input("🔑 학생 이름 입력", value="", max_chars=50)
    
    # 두 필드가 모두 입력되었는지 확인
    if activity_code and student_name:
        fetch_prompt_btn = st.sidebar.button("프롬프트 가져오기")
        st.sidebar.info("모든 필드를 입력한 후 '프롬프트 가져오기' 버튼을 클릭하세요.")
    else:
        fetch_prompt_btn = False
        st.sidebar.info("활동 코드와 학생 이름을 모두 입력해야 합니다.")
    
    # 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.initialized = False
        st.session_state.teacher_email = ""
        st.session_state.student_view = ""
        st.session_state.last_email_count = 0  # 이메일 전송을 추적하기 위한 변수
    
    if fetch_prompt_btn:
        if not activity_code or not student_name:
            st.sidebar.error("활동 코드와 학생 이름을 모두 입력해주세요.")
        else:
            instruction, teacher_email, student_view = fetch_instruction_from_notion(activity_code)
            if instruction:
                st.session_state.messages = [
                    {"role": "system", "content": instruction}
                ]
                st.session_state.teacher_email = teacher_email
                st.session_state.student_view = student_view
                st.session_state.initialized = True
                st.sidebar.success("프롬프트가 성공적으로 불러와졌습니다.")
            else:
                st.sidebar.error("프롬프트를 불러오지 못했습니다.")
    
    # Display chat interface
    st.title(st.session_state.student_view)

    if st.session_state.initialized:
        if prompt := st.chat_input("메시지를 입력하세요"):
            # 사용자 메시지 추가
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            # 사용자 메시지 개수 확인
            user_message_count = sum(1 for msg in st.session_state.messages if msg["role"] == "user")

            with st.spinner("응답을 기다리는 중..."):
                try:
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=st.session_state.messages
                    )

                    msg = response.choices[0].message.content.strip()

                    # AI 메시지 추가
                    st.session_state.messages.append({"role": "assistant", "content": msg})
                    st.chat_message("assistant").write(msg)
                except Exception as e:
                    st.error(f"AI 응답 생성에 실패했습니다: {e}")

            # 이메일 자동 전송 조건 확인: 사용자 메시지 개수가 5의 배수이고 이전에 전송되지 않았을 때
            if user_message_count % 5 == 0 and user_message_count != st.session_state.last_email_count:
                success = send_email(st.session_state.messages, student_name, st.session_state.teacher_email)
                if success:
                    st.success("대화 내역이 성공적으로 이메일로 전송되었습니다.")
                    st.session_state.last_email_count = user_message_count
                else:
                    st.error("대화 내역 이메일 전송에 실패했습니다.")

if __name__ == "__main__":
    main()
