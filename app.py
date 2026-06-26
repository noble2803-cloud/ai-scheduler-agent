import streamlit as st
import random
import json
from openai import OpenAI

# 1. 페이지 기본 설정 및 OpenAI 클라이언트 초기화
st.set_page_config(page_title="AI 멘탈케어 스케줄러", layout="wide")

# Streamlit Secrets 또는 사용자 입력에서 API 키 로드
openai_key = st.sidebar.text_input("OpenAI API Key", type="password")

# 재치 있는 스트레스 해소 멘트 리스트
WITTY_TIPS = [
    "☕️ 지금 안 쉬면 이따가 모니터 부술지도 몰라요. 아메리카노 수혈하고 오세요!",
    "🚶‍♂️ 5분만 나가서 바깥 공기 좀 마시고 오죠? 하늘이 무척 예쁩니다 (아마도).",
    "🧘‍♂️ 가벼운 스트레칭 타임! 목이랑 어깨 좀 돌려주세요. 뚝뚝 소리 나면 반성하시고.",
    "🍫 초콜릿이나 당 충전용 간식 타임! 뇌가 살려달라고 소리치고 있어요."
]

# 2. 세션 상태(State) 초기화 (새로고침해도 데이터 유지)
if "mock_schedule" not in st.session_state:
    # 시연용 고정 스케줄 매일 랜덤 생성 (기존 일정 뼈대)
    days = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    mock_activities = ["기존 정기 미팅", "루틴 업무 처리", "이메일 회신 및 서류 정리", "팀 피드백 세션"]
    
    initial_schedule = {}
    for day in days:
        # 매일 1~2개의 고정 일정을 랜덤하게 배치
        num_tasks = random.randint(1, 2)
        initial_schedule[day] = [
            {
                "task_name": random.choice(mock_activities),
                "intensity": random.randint(2, 4),
                "duration": random.randint(1, 2),
                "importance": random.randint(2, 4),
                "is_mock": True
            } for _ in range(num_tasks)
        ]
    st.session_state.mock_schedule = initial_schedule

if "new_tasks" not in st.session_state:
    st.session_state.new_tasks = []

if "ai_explanation" not in st.session_state:
    st.session_state.ai_explanation = "아직 새로운 일정이 추가되지 않았습니다."

# 스트레스 지수 계산기 (Python에서 자체 처리하여 토큰 절약)
def calculate_stress(tasks):
    if not tasks:
        return 0
    total_score = 0
    for t in tasks:
        # 스트레스 점수 공식 = (업무강도 * 1.5) + (중요도 * 1.0) + (소요시간 * 2)
        base = (int(t["intensity"]) * 1.5) + (int(t["importance"]) * 1.0) + (int(t["duration"]) * 2)
        total_score += base
    
    # 100점 만점으로 스케일링 (일정이 너무 많으면 100을 넘을 수 있으므로 제한)
    return min(int(total_score * 3), 100)

# 3. UI 레이아웃 구성
st.title("📅 AI 멘탈케어 스마트 스케줄러")
st.caption("시연용 고정 일정 사이에 새로운 마감 일정을 스마트하게 재배열하고 스트레스 지수를 관리합니다.")

col1, col2 = st.columns([1, 2])

# 왼쪽 사이드: 입력 및 등록된 일정 관리
with col1:
    st.header("📥 새 마감 일정 입력")
    with st.form("task_form", clear_on_submit=True):
        task_name = st.text_input("일정 이름", placeholder="예: 프로젝트 최종 보고서 작성")
        intensity = st.slider("업무 강도 (1~5)", 1, 5, 3)
        duration = st.number_input("소요 시간 (시간 단위)", min_value=1, max_value=8, value=2)
        importance = st.slider("중요도 (1~5)", 1, 5, 3)
        
        submitted = st.form_submit_state = st.form_submit_button("추가하기")
        if submitted and task_name:
            if len(st.session_state.new_tasks) < 3:
                st.session_state.new_tasks.append({
                    "task_name": task_name,
                    "intensity": intensity,
                    "duration": duration,
                    "importance": importance,
                    "is_mock": False
                })
                st.success(f"'{task_name}' 일정이 임시 리스트에 추가되었습니다!")
            else:
                st.warning("시연을 위해 일정은 최대 3개까지만 넣을 수 있습니다.")

    # 추가된 일정 리스트 및 삭제 기능
    st.subheader("📋 추가 대기 중인 마감 일정 (최대 3개)")
    if st.session_state.new_tasks:
        for idx, t in enumerate(st.session_state.new_tasks):
            t_col, b_col = st.columns([4, 1])
            t_col.write(f"**{t['task_name']}** (강도:{t['intensity']}, {t['duration']}시간, 중요도:{t['importance']})")
            if b_col.button("❌", key=f"del_{idx}"):
                st.session_state.new_tasks.pop(idx)
                st.rerun()
    else:
        st.write("추가된 일정이 없습니다.")

    # AI 재배열 트리거 버튼
    if st.button("🚀 AI 스마트 스케줄 재배열 시작", type="primary"):
        if not openai_key:
            st.error("왼쪽 사이드바에 OpenAI API Key를 입력해주세요!")
        elif not st.session_state.new_tasks:
            st.warning("재배열할 새로운 마감 일정을 최소 1개 이상 추가해주세요.")
        else:
            with st.spinner("AI가 일정을 분석하고 최적의 스케줄을 짜는 중입니다..."):
                try:
                    client = OpenAI(api_key=openai_key)
                    
                    # LLM에게 보낼 프롬프트 작성 (토큰 절약을 위해 JSON 포맷 지정)
                    prompt = f"""
                    당신은 전문 스케줄러 에이전트입니다.
                    기존의 일주일 고정 스케줄 정보와 사용자가 새롭게 추가하고 싶어하는 마감 일정 리스트를 드립니다.
                    업무 강도, 중요도, 소요 시간을 고려하여 기존 일정 사이사이에 새 일정을 '요일별'로 최적 분배하여 재배열해주세요.
                    
                    [기존 고정 스케줄]:
                    {json.dumps(st.session_state.mock_schedule, ensure_ascii=False)}
                    
                    [새로 추가할 마감 일정]:
                    {json.dumps(st.session_state.new_tasks, ensure_ascii=False)}
                    
                    규칙:
                    1. 반환 형식은 반드시 순수한 JSON 오브젝트여야 합니다. Markdown 포맷(```json 등)을 포함하지 마세요.
                    2. 구조는 {{"schedule": {{"월요일": [...], "화요일": [...]}}, "explanation": "왜 이렇게 짰는지에 대한 재치있고 명쾌한 설명"}} 형태여야 합니다.
                    3. 입력받은 모든 마감 일정은 버리지 말고 스케줄 내에 골고루 포함시켜야 합니다.
                    """
                    
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7
                    )
                    
                    # 결과 파싱 및 세션 적용
                    result = json.loads(response.choices[0].message.content.strip())
                    st.session_state.mock_schedule = result["schedule"]
                    st.session_state.ai_explanation = result["explanation"]
                    # 시연 종료 후 리스트 비우기 (선택 사항)
                    st.session_state.new_tasks = []
                    st.success("스케줄 재배열이 완료되었습니다!")
                    st.rerun()
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}\nAPI 키를 다시 확인하거나 JSON 파싱 에러일 수 있습니다.")

# 오른쪽 사이드: 1주일 스케줄 출력 및 스트레스 지수
with col2:
    st.header("📅 이번 주 스마트 스케줄 분석")
    
    # AI 배치 이유 브리핑 리딩
    st.info(f"🤖 **AI의 스케줄링 리포트:**\n\n{st.session_state.ai_explanation}")
    st.write("---")
    
    # 요일별 스케줄 카드 뷰
    days_order = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    
    # 화면을 깔끔하게 분할하기 위해 7일 일정을 확장러(Expander) 혹은 카드 형태로 배치
    for day in days_order:
        if day in st.session_state.mock_schedule:
            day_tasks = st.session_state.mock_schedule[day]
            stress_score = calculate_stress(day_tasks)
            
            # 스트레스 점수에 따른 메시지 및 색상 정의
            if stress_score >= 70:
                stress_status = f"🔴 위험 ({stress_score}점) - {random.choice(WITTY_TIPS)}"
            elif stress_score >= 40:
                stress_status = f"🟡 보통 ({stress_score}점) - 무난한 하루입니다. 페이스를 유지하세요."
            else:
                stress_status = f"🟢 여유 ({stress_score}점) - ☕️ 오늘은 꽤 널널하네요! 중간중간 멍 때려도 무죄."
            
            # 요일별 박스 개설
            with st.expander(f"📆 {day} (예상 스트레스 지수: {stress_status})", expanded=True):
                if not day_tasks:
                    st.write("🎉 잡힌 일정이 없습니다! 완전 휴식!")
                else:
                    # 테이블 형태로 예쁘게 출력
                    for idx, task in enumerate(day_tasks):
                        is_new_marker = "🌟 [새 마감 일정]" if not task.get("is_mock", False) else "🔒 [기존]"
                        st.write(f"- {is_new_marker} **{task['task_name']}** | ⏳ {task['duration']}시간 | 🔥 강도: {task['intensity']} | 🎯 중요도: {task['importance']}")