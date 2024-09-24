import streamlit as st
from openai import OpenAI
import requests
import pathlib
import toml
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 세션 상태 초기화
if 'prompt' not in st.session_state:
    st.session_state.prompt = ""
if 'teacher_email' not in st.session_state:
    st.session_state.teacher_email = ""
if 'image_url' not in st.session_state:
    st.session_state.image_url = ""
if 'adjectives' not in st.session_state:
    st.session_state.adjectives = []

# 페이지 설정 - 아이콘과 제목 설정
st.set_page_config(
    page_title="학생용 교육 도구 이미지",
    page_icon="🤖",
)

# Streamlit의 배경색 변경
background_color = "#FFEBEE"

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

# OpenAI API 클라이언트 초기화
client = OpenAI(api_key=secrets["api"]["keys"][0])  # 첫 번째 API 키 사용

# Notion API 설정
NOTION_API_KEY = secrets["notion"]["api_key"]
NOTION_DATABASE_ID = secrets["notion"]["database_id_image"]

# 이메일 전송 기능
def send_email_to_teacher(student_name, teacher_email, prompt, adjectives, image_url):
    if not teacher_email:
        return False  # 이메일 전송 건너뜀

    msg = MIMEMultipart()
    msg["From"] = secrets["email"]["address"]
    msg["To"] = teacher_email
    msg["Subject"] = f"{student_name} 학생의 이미지 생성 결과"

    body = f"""
    학생 이름: {student_name}
    주제: {prompt}
    형용사: {adjectives}

    생성된 이미지 URL:
    {image_url}
    """
    msg.attach(MIMEText(body, "plain"))

    # 이메일 전송
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(secrets["email"]["address"], secrets["email"]["password"])
            server.send_message(msg)
        return True  # 이메일 전송 성공 시 True 반환
    except Exception as e:
        st.error(f"이메일 전송에 실패했습니다: {e}")
        return False  # 이메일 전송 실패 시 False 반환

# Notion에서 프롬프트와 형용사(adjective) 가져오기
def get_prompt_and_adjectives(activity_code):
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
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
                # 프롬프트 가져오기
                prompt_property = result["properties"].get("prompt", {})
                prompt_rich_text = prompt_property.get("rich_text", [])
                prompt = prompt_rich_text[0].get("text", {}).get("content", "") if prompt_rich_text else ""

                # 교사 이메일 가져오기
                email_property = result["properties"].get("email", {})
                email_rich_text = email_property.get("rich_text", [])
                teacher_email = email_rich_text[0].get("plain_text", "") if email_rich_text else ""

                # 형용사 가져오기 (JSON 문자열 파싱)
                adjectives_property = result["properties"].get("adjectives", {})
                adjectives = []
                if adjectives_property.get("rich_text"):
                    adjectives_str = adjectives_property["rich_text"][0]["text"]["content"]
                    try:
                        adjectives = json.loads(adjectives_str)  # JSON 문자열을 리스트로 변환
                    except json.JSONDecodeError:
                        st.error("⚠️ 형용사를 파싱하는 중 오류가 발생했습니다.")

                # 세션 상태에 프롬프트와 형용사 저장
                st.session_state.prompt = prompt
                st.session_state.teacher_email = teacher_email
                st.session_state.adjectives = adjectives

                return prompt, teacher_email, adjectives
    return None, None, []

# 학생용 UI
st.header('🎨 학생용: 이미지 생성 도구')

# 사용 설명 추가
st.markdown("""
    **안내:** 이 도구를 사용하여 교사가 제공한 프롬프트에 따라 이미지를 생성할 수 있습니다.
    1. **학생 이름 입력**: 본인의 이름을 입력하세요.
    2. **코드 입력**: 수업과 관련된 활동 코드를 입력하세요.
    3. **프롬프트 가져오기**: 코드를 입력한 후 **프롬프트 가져오기** 버튼을 클릭하면, 교사가 설정한 프롬프트를 불러옵니다.
    4. **형용사 선택**: 이미지의 스타일이나 느낌을 나타내는 형용사를 선택하세요.
    5. **이미지 생성**: 교사 프롬프트와 선택한 형용사를 바탕으로 이미지를 생성합니다.
    6. **결과 확인**: 생성된 이미지를 확인하고 필요시 다운로드하세요.
""")

# 학생 이름 입력 필드
student_name = st.text_input("🔑 학생 이름 입력", value="", max_chars=50)
if not student_name:
    st.warning("학생 이름을 입력하세요.")

# 활동 코드 입력 필드
activity_code = st.text_input("🔑 코드 입력")

if st.button("📄 프롬프트 가져오기", key="get_prompt"):
    if activity_code:
        with st.spinner("🔍 프롬프트를 불러오는 중..."):
            prompt, teacher_email, adjectives = get_prompt_and_adjectives(activity_code)

            if prompt:
                st.session_state.prompt = prompt
                st.session_state.teacher_email = teacher_email  # 빈 문자열일 수 있음
                st.session_state.adjectives = adjectives
                st.success("✅ 프롬프트를 성공적으로 불러왔습니다.")
            else:
                st.error("⚠️ 해당 코드에 대한 프롬프트를 찾을 수 없습니다.")
    else:
        st.error("⚠️ 코드를 입력하세요.")

# 프롬프트와 형용사 선택
if st.session_state.prompt:
    st.write("**프롬프트:** " + st.session_state.prompt)

    selected_adjective = None  # selected_adjective 변수 초기화

    if st.session_state.adjectives:
        st.subheader("**형용사 선택**")
        selected_adjective = st.selectbox(
            "🎨 형용사를 선택하세요:",
            options=st.session_state.adjectives
        )
    else:
        st.error("⚠️ 형용사를 불러올 수 없습니다.")

    if selected_adjective:
        if st.button("🖼️ 이미지 생성", key="generate_image"):
            with st.spinner("🖼️ 이미지를 생성하는 중..."):
                combined_prompt = f"{st.session_state.prompt} {selected_adjective}"
                try:
                    response = client.images.generate(
                        model="dall-e-3",
                        prompt=combined_prompt,
                        size="1024x1024",
                        quality="standard",
                        n=1,
                    )
                    image_url = response.data[0].url
                    st.session_state.image_url = image_url
                    st.image(image_url, caption="생성된 이미지", use_column_width=True)

                    # 이미지 데이터를 바이너리로 가져오기
                    image_response = requests.get(image_url)
                    if image_response.status_code == 200:
                        image_data = image_response.content
                        st.success("✅ 이미지가 성공적으로 생성되었습니다!")
                        st.download_button(
                            label="💾 이미지 다운로드",
                            data=image_data,
                            file_name="generated_image.png",
                            mime="image/png"
                        )
                        # 이메일로 결과 전송
                        if send_email_to_teacher(student_name, st.session_state.teacher_email, st.session_state.prompt, selected_adjective, image_url):
                            if st.session_state.teacher_email:
                                st.success("📧 교사에게 이메일로 결과가 전송되었습니다.")
                    else:
                        st.error("이미지를 가져오는 중 오류가 발생했습니다.")

                except Exception as e:
                    st.error(f"이미지 생성에 실패했습니다: {e}")
else:
    st.info("프롬프트를 가져와 주세요.")
