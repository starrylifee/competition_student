import streamlit as st
import google.generativeai as genai
import requests
import pathlib
import toml
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image, UnidentifiedImageError
import io

# 페이지 설정 - 아이콘과 제목 설정
st.set_page_config(
    page_title="학생용 교육 도구 비전",
    page_icon="🤖",
)

# Streamlit의 배경색 변경
background_color = "#E0FFFF"

# 배경색 변경을 위한 CSS
page_bg_css = f"""
<style>
    .stApp {{
        background-color: {background_color};
    }}
</style>
"""

# Streamlit의 기본 메뉴와 푸터 숨기기
hide_menu_style = """
    <style>
    #MainMenu {visibility: hidden; }
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
st.markdown(page_bg_css, unsafe_allow_html=True)

# secrets.toml 파일 경로
secrets_path = pathlib.Path(__file__).parent.parent / ".streamlit/secrets.toml"

# secrets.toml 파일 읽기
with open(secrets_path, "r") as f:
    secrets = toml.load(f)

# Gemini API 키 설정
gemini_api_key1 = secrets["google"]["gemini_api_key1"]
genai.configure(api_key=gemini_api_key1)

# Notion API 설정
NOTION_API_KEY = secrets["notion"]["api_key"]
DATABASE_ID = secrets["notion"]["database_id_vision"]

# Notion에서 프롬프트, 학생 뷰, 교사 이메일 가져오기
def fetch_prompt_student_view_email_from_notion(activity_code):
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    data = {
        "filter": {
            "property": "activity_code",
            "rich_text": {
                "equals": activity_code
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        results = response.json().get("results")
        if results:
            for result in results:
                properties = result.get("properties", {})
                
                # 'prompt' 속성에서 텍스트 콘텐츠 가져오기
                prompt_property = properties.get("prompt", {})
                prompt_rich_text = prompt_property.get("rich_text", [])
                if not prompt_rich_text:
                    continue
                prompt = prompt_rich_text[0].get("text", {}).get("content", "")
                
                # 'student_view' 속성에서 텍스트 콘텐츠 가져오기
                student_view_property = properties.get("student_view", {})
                student_view_rich_text = student_view_property.get("rich_text", [])
                if not student_view_rich_text:
                    continue
                student_view = student_view_rich_text[0].get("text", {}).get("content", "")
                
                # 'email' 속성에서 plain_text 가져오기 (선택 사항)
                email_property = properties.get("email", {})
                email_rich_text = email_property.get("rich_text", [])
                teacher_email = ""
                if email_rich_text:
                    teacher_email = email_rich_text[0].get("plain_text", "")
    
                # **차단 지침 추가**
                blocking_instructions = (
                    "\n\n"
                    "학생의 입력이 설정된 역할과 관련이 없거나 이상한 내용이 포함되어 있다면, "
                    "그 내용에 대해 응답하지 말고 주어진 역할에 집중해 주세요."
                )
                prompt += blocking_instructions  # 프롬프트에 차단 지침 추가
                
                return prompt, student_view, teacher_email
    return None, None, None

# 이메일 전송 기능
def send_email_to_teacher(student_name, teacher_email, prompt, image_data, ai_response):
    if not teacher_email:
        st.info("⚠️ 교사 이메일이 설정되어 있지 않아 이메일을 전송하지 않습니다.")
        return False  # 이메일 전송 건너뜀
    
    msg = MIMEMultipart()
    msg["From"] = secrets["email"]["address"]
    msg["To"] = teacher_email
    msg["Subject"] = f"{student_name} 학생의 AI 생성 활동 결과"

    body = f"""
    학생 이름: {student_name}

    사용된 프롬프트:
    {prompt}

    AI 생성 결과:
    {ai_response}
    """
    msg.attach(MIMEText(body, "plain"))

    # 이미지 첨부
    img = MIMEText(image_data, "base64", "utf-8")
    img.add_header("Content-Disposition", "attachment", filename="image.png")
    msg.attach(img)

    # 이메일 전송
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(secrets["email"]["address"], secrets["email"]["password"])
            server.send_message(msg)
        return True  # 이메일 전송 성공 시 True 반환
    except Exception as e:
        st.error(f"이메일 전송에 실패했습니다: {e}")
        return False  # 이메일 전송 실패 시 False 반환

# 학생용 UI
st.header('📸 학생용: AI 교육 활동 도구')

st.markdown("""
    **안내:** 이 도구를 사용하여 AI가 생성한 프롬프트에 따라 다양한 교육 활동을 수행할 수 있습니다.
    1. **학생 이름 입력**: 본인의 이름을 입력하세요.
    2. **활동 코드 입력**: 교사가 제공한 활동 코드를 입력하세요.
    3. **프롬프트 가져오기**: 활동 코드에 해당하는 프롬프트를 불러옵니다.
    4. **이미지 업로드**: 교육 활동에 사용할 이미지를 업로드하거나 카메라로 촬영하세요.
    5. **AI 활동 수행**: AI가 제공된 프롬프트와 이미지를 바탕으로 창의적인 교육 활동을 도와줍니다.
""")

# 학생 이름 입력 필드 추가
student_name = st.text_input("🔑 학생 이름 입력", value="", max_chars=50)
if not student_name:
    st.warning("학생 이름을 입력하세요.")

# 활동 코드 입력 필드
activity_code = st.text_input("🔑 활동 코드 입력")

if st.button("📄 프롬프트 가져오기", key="get_prompt"):
    if activity_code:
        with st.spinner("🔍 프롬프트를 불러오는 중..."):
            prompt, student_view, teacher_email = fetch_prompt_student_view_email_from_notion(activity_code)
            if prompt and student_view:
                st.session_state.prompt = prompt
                st.session_state.student_view = student_view
                st.session_state.teacher_email = teacher_email  # None 또는 빈 문자열일 수 있음
                st.success("✅ 프롬프트를 성공적으로 불러왔습니다.")
            else:
                st.error("⚠️ 활동 코드를 다시 확인하세요.")  # 코드 불러오기 실패 시 오류 메시지
    else:
        st.error("⚠️ 활동 코드를 입력하세요.")

if "prompt" in st.session_state and st.session_state.prompt and "student_view" in st.session_state and st.session_state.student_view:
    st.write("**프롬프트:** " + st.session_state.student_view)

    # 이미지 업로드 또는 카메라 촬영
    st.write("📸 이미지를 업로드하거나 카메라로 촬영하여 프롬프트를 처리하세요.")
    image = st.file_uploader("이미지 업로드", type=["jpg", "jpeg", "png"])

    if image:
        st.image(image, caption='선택된 이미지', use_column_width=True)

        try:
            with st.spinner('🧠 AI가 이미지를 분석하여 창의적인 교육 활동을 도와줍니다...'):
                # 이미지 바이트 문자열로 변환
                img_bytes = image.read()

                # bytes 타입의 이미지 데이터를 PIL.Image.Image 객체로 변환
                img = Image.open(io.BytesIO(img_bytes))

                model = genai.GenerativeModel('gemini-1.5-flash')

                # Generate content
                response = model.generate_content([
                    st.session_state.prompt, img
                ])

                # Resolve the response
                response.resolve()

                ai_response_text = response.text
                st.markdown(ai_response_text)

                # 결과와 이미지를 교사에게 이메일로 전송
                if send_email_to_teacher(student_name, st.session_state.teacher_email, st.session_state.prompt, img_bytes, ai_response_text):
                    if st.session_state.teacher_email:
                        st.success("📧 교사에게 이메일로 결과가 전송되었습니다.")
        except UnidentifiedImageError:
            st.error("❌ 업로드된 파일이 유효한 이미지 파일이 아닙니다. 다른 파일을 업로드해 주세요.")
else:
    st.info("프롬프트를 가져오세요.")
