import streamlit as st
import random
import json
import google.generativeai as genai

# 1. 페이지 기본 설정 (가로 레이아웃 wide 모드)
st.set_page_config(page_title="AI 멘탈케어 주간 스케줄러", layout="wide")

# 재치 있는 멘트 세트
WITTY_TIPS = [
    "☕️ 지금 안 쉬면 이따가 모니터 부술지도 몰라요. 아메리카노 수혈 필수!",
    "🚶‍♂️ 5분만 나가서 바깥 공기 좀 마시고 오죠? 정수기 앞이라도 걸으세요.",
    "🧘‍♂️ 가벼운 스트레칭 타임! 목이랑 어깨 좀 돌려주세요. 뚝뚝 소리 나면 반성하시고.",
    "🍫 초콜릿이나 당 충전용 간식 타임! 뇌가 살려달라고 소리치고 있어요."
]

MOCK_EXPLANATIONS = [
    "마감 요일이 촉박한 일정을 우선 배치하고, 업무 강도가 높은 날 뒤에는 의도적으로 루틴 업무만 배치하여 멘탈을 보호했습니다. 😎",
    "수요일에 업무 헬게이트가 열릴 뻔했으나, 중요도가 낮은 기존 미팅을 금요일로 밀어버리고 새로운 마감 일정을 최우선으로 배치했습니다. 🚀",
    "스트레스 지수 과부하를 막기 위해 목요일에 몰려있던 로드를 월/화로 분산 배치했습니다. 퇴근은 지켜야 하니까요! ⏱️"
]

DAYS_ORDER = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]

# 2. 세션 상태(State) 초기화
if "mock_schedule" not in st.session_state:
    mock_activities = ["기존 정기 미팅", "루틴 업무 처리", "이메일 회신", "팀 피드백 세션"]
    initial_schedule = {}
    for day in DAYS_ORDER:
        num_tasks = random.randint(1, 2)
        initial_schedule[day] = [
            {
                "task_name": random.choice(mock_activities),
                "intensity": random.randint(2, 4),
                "duration": random.randint(1, 2),
                "importance": random.randint(2, 4),
                "due_day": day,
                "is_mock": True
            } for _ in range(num_tasks)
        ]
    st.session_state.mock_schedule = initial_schedule

if "new_tasks" not in st.session_state:
    st.session_state.new_tasks = []

if "ai_explanation" not in st.session_state:
    st.session_state.ai_explanation = "오른쪽에서 마감 일정을 추가한 뒤 'AI 스마트 스케줄 재배열'을 눌러보세요!"

# 스트레스 지수 자동 계산 함수
def calculate_stress(tasks):
    if not tasks:
        return 0
    total_score = 0
    for t in tasks:
        base = (int(t["intensity"]) * 2.0) + (int(t["importance"]) * 1.0) + (int(t["duration"]) * 1.5)
        total_score += base
    return min(int(total_score * 2.5), 100)

# 3. UI 레이아웃 구성
st.title("📅 AI 멘탈케어 주간 스케줄러 (무료 Gemini 버전)")
st.write("---")

# ⚙️ 사이드바 설정 (여기서 변수 선언 순서를 바로잡았습니다!)
st.sidebar.header("⚙️ 시연 컨트롤 패널")

# [해결 포인트] cheat_mode 변수를 가장 먼저 선언합니다.
cheat_mode = st.sidebar.checkbox("🧙‍♂️ API 없이 시연하기 (치트키 모드)", value=False, 
                                 help="네트워크 장애나 API 제한 발생 시 내부 알고리즘으로 시연하는 모드입니다.")

api_key_to_use = ""

# 이제 cheat_mode 변수가 확실히 존재하므로 조건문을 안전하게 실행합니다.
if not cheat_mode:
    custom_key = st.sidebar.text_input("🔄 대체 Gemini API Key 입력 (선택사항)", type="password",
                                       help="Streamlit Secrets 시스템이 비어있거나 작동하지 않을 때 여기에 새 키를 넣으세요.")
    
    if custom_key:
        api_key_to_use = custom_key
        st.sidebar.info("💡 사용자가 새로 입력한 대체 API 키를 사용합니다.")
    else:
        # 깃허브에는 키를 적지 않고, 지난 번에 설정한 Streamlit Secrets 금고에서 안전하게 꺼내옵니다.
        if "GEMINI_API_KEY" in st.secrets:
            api_key_to_use = st.secrets["GEMINI_API_KEY"]
            st.sidebar.success("🔒 Streamlit Secrets 보안 키를 적용 중입니다.")
        else:
            api_key_to_use = ""
            st.sidebar.warning("⚠️ Streamlit 플랫폼의 Secrets 설정에 GEMINI_API_KEY를 등록해 주세요! (혹은 아래 대체 키 입력)")
else:
    st.sidebar.success("🔮 치트키 모드 활성화 (API 호출 없음)")

# 메인 화면 분할 (위: 입력 폼 및 관리, 아래: 가로형 달력)
top_col1, top_col2 = st.columns([1, 1])

with top_col1:
    st.subheader("📥 새 마감 일정 추가")
    with st.form("task_form", clear_on_submit=True):
        task_name = st.text_input("일정 이름", placeholder="예: 상반기 핵심 보고서 제출")
        
        c1, c2 = st.columns(2)
        intensity = c1.slider("업무 강도 (1~5)", 1, 5, 3)
        importance = c2.slider("중요도 (1~5)", 1, 5, 3)
        
        c3, c4 = st.columns(2)
        duration = c3.number_input("소요 시간 (시간)", min_value=1, max_value=8, value=2)
        due_day = c4.selectbox("⚠️ 마감 요일 (Due Date)", DAYS_ORDER, index=4)
        
        submitted = st.form_submit_button("➕ 대기 리스트에 추가")
        if submitted and task_name:
            if len(st.session_state.new_tasks) < 3:
                st.session_state.new_tasks.append({
                    "task_name": task_name,
                    "intensity": intensity,
                    "duration": duration,
                    "importance": importance,
                    "due_day": due_day,
                    "is_mock": False
                })
                st.success(f"'{task_name}' 일정이 등록되었습니다.")
            else:
                st.warning("시연 최적화를 위해 대기 일정은 최대 3개까지만 제한합니다.")

with top_col2:
    st.subheader("📋 대기 중인 마감 일정 (최대 3개)")
    if st.session_state.new_tasks:
        for idx, t in enumerate(st.session_state.new_tasks):
            t_col, b_col = st.columns([5, 1])
            t_col.write(f"**{t['task_name']}** (⏳{t['duration']}h, 🔥강도:{t['intensity']}, 🎯중요:{t['importance']}, 📅**{t['due_day']} 마감**)")
            if b_col.button("❌", key=f"del_{idx}"):
                st.session_state.new_tasks.pop(idx)
                st.rerun()
    else:
        st.write("현재 추가 대기 중인 일정이 없습니다. 왼쪽에서 입력해 주세요.")
    
    st.write("")
    if st.button("🚀 AI 스마트 스케줄 재배열 시작", type="primary", use_container_width=True):
        if not cheat_mode and (api_key_to_use == ""):
            st.error("🚨 사용할 수 있는 API 키가 없습니다! 세팅을 확인하거나 사이드바에서 '치트키 모드'를 켜주세요.")
        elif not st.session_state.new_tasks:
            st.warning("재배열할 새로운 마감 일정을 최소 1개 이상 추가해 주세요.")
        else:
            with st.spinner("Gemini AI가 마감일과 스트레스를 분석하여 스케줄을 짜는 중..."):
                
                # --- [모드 1: 치트키 모드] ---
                if cheat_mode:
                    current_sched = st.session_state.mock_schedule
                    for t in st.session_state.new_tasks:
                        target_day = t["due_day"]
                        current_sched[target_day].append(t)
                    
                    st.session_state.mock_schedule = current_sched
                    st.session_state.ai_explanation = random.choice(MOCK_EXPLANATIONS) + " (※ 현재 치트키 모드로 초고속 로컬 연산되었습니다.)"
                    st.session_state.new_tasks = []
                    st.success("스케줄 재배열 완료!")
                    st.rerun()
                
                # --- [모드 2: 무료 Gemini API 연결 모드] ---
                else:
                    try:
                        genai.configure(api_key=api_key_to_use)
                        
                        prompt = f"""
                        당신은 전문 AI 스케줄러입니다. 기존 주간 일정 사이에 사용자의 신규 '마감 일정'을 재배열해 주세요.
                        
                        [기존 주간 일정]:
                        {json.dumps(st.session_state.mock_schedule, ensure_ascii=False)}
                        
                        [새로 배치할 마감 일정 (due_day 내에 반드시 배치해야 함)]:
                        {json.dumps(st.session_state.new_tasks, ensure_ascii=False)}
                        
                        규칙:
                        1. 신규 일정의 'due_day(마감 요일)'을 확인하고, 반드시 그 마감 요일 당일이나 그 이전 요일에 일정을 배치하세요. (마감일 이후 배치는 절대 금지)
                        2. 반환 형식은 오직 순수한 JSON 오브젝트여야 하며, ```json 같은 마크다운 기호는 절대 포함하지 마세요.
                        3. 구조 예시: {{"schedule": {{"월요일": [...], "화요일": [...]}}, "explanation": "재치 있고 직관적인 스케줄링 이유 설명"}}
                        """
                        
                        model = genai.GenerativeModel(
                            model_name="gemini-1.5-flash",
                            generation_config={"response_mime_type": "application/json"}
                        )
                        
                        response = model.generate_content(prompt)
                        
                        result = json.loads(response.text.strip())
                        st.session_state.mock_schedule = result["schedule"]
                        st.session_state.ai_explanation = result["explanation"]
                        st.session_state.new_tasks = []
                        st.success("Gemini AI 스케줄 재배열 완료!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"🚨 에러가 발생했습니다: {e}\n\n💡 무료 티어 제한 오류일 수 있으니, 시연을 즉시 재개하려면 왼쪽에서 'API 없이 시연하기'를 켜주세요!")

st.write("---")
st.subheader("💡 AI 브리핑 및 주간 리포트")
st.info(f"🤖 **{st.session_state.ai_explanation}**")

# 4. 가로형 달력 구조
st.write("")
st.subheader("🗓️ 이번 주 주간 스케줄 플래너")

cols = st.columns(7)

for idx, day in enumerate(DAYS_ORDER):
    with cols[idx]:
        st.markdown(f"### {day}")
        
        day_tasks = st.session_state.mock_schedule.get(day, [])
        stress_score = calculate_stress(day_tasks)
        
        if stress_score >= 75:
            st.error(f"💥 스트레스: {stress_score}점")
            st.caption(f"🚨 **비상!**\n{random.choice(WITTY_TIPS)}")
        elif stress_score >= 45:
            st.warning(f"⚠️ 스트레스: {stress_score}점")
            st.caption("⚖️ 업무 밀도가 높습니다. 페이스 조절 필요.")
        else:
            st.success(f"🍃 스트레스: {stress_score}점")
            st.caption("☕️ 여유로운 하루! 커피 한 잔의 낭만을 즐기세요.")
            
        st.write("---")
        
        if not day_tasks:
            st.write("*🎉 잡힌 일정이 없습니다! 완전 휴식!*")
        else:
            for task in day_tasks:
                if not task.get("is_mock", False):
                    st.info(f"🌟 **{task['task_name']}**\n\n⏱️ {task['duration']}시간 / 🔥 강도: {task['intensity']}\n\n🎯 중요: {task['importance']}")
                else:
                    st.markdown(
                        f"""
                        <div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px; color: #31333F;'>
                            <small>🔒 기존 일정</small><br>
                            <strong>{task['task_name']}</strong><br>
                            <small>⏱️ {task['duration']}h | 🔥 강도: {task['intensity']}</small>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
