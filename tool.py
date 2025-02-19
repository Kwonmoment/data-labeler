import streamlit as st
import json
import pandas as pd
from pathlib import Path
import math
from datetime import datetime
import os
import glob
import io
from PIL import Image

# 데이터 저장 디렉토리 설정
DATA_DIR = "data"
LABEL_FILE = "labels.json"
ASSIGNMENTS_FILE = "assignments.json"
POLICY_IMAGE = "policy_image.png"
os.makedirs(DATA_DIR, exist_ok=True)

# 데이터 저장 및 로드 함수들
def save_data(data, filename):
    """데이터를 JSON 파일로 저장"""
    with open(os.path.join(DATA_DIR, filename), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_data(filename):
    """JSON 파일에서 데이터 로드"""
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_image(image_file, filename):
    """이미지 파일 저장"""
    image_path = os.path.join(DATA_DIR, filename)
    with open(image_path, "wb") as f:
        f.write(image_file.getbuffer())
    return image_path

def get_policy_image():
    """정책 이미지 로드"""
    image_path = os.path.join(DATA_DIR, POLICY_IMAGE)
    if os.path.exists(image_path):
        return Image.open(image_path)
    return None

# 세션 상태 초기화 및 데이터 로드
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.all_data = []
    st.session_state.user_assignments = load_data(ASSIGNMENTS_FILE) or {}
    st.session_state.labels = load_data(LABEL_FILE) or {}
    st.session_state.policy_image = get_policy_image()
    
    # 기존 데이터 파일들 로드
    for file in glob.glob(os.path.join(DATA_DIR, "data_*.json")):
        with open(file, 'r', encoding='utf-8') as f:
            st.session_state.all_data.extend(json.load(f))

def clear_all_data():
    """모든 데이터와 파일 초기화"""
    # 정책 이미지는 유지
    policy_path = os.path.join(DATA_DIR, POLICY_IMAGE)
    has_policy = os.path.exists(policy_path)
    policy_image = None
    
    if has_policy:
        policy_image = Image.open(policy_path)
    
    # data 디렉토리 내의 모든 파일 삭제
    for file in glob.glob(os.path.join(DATA_DIR, "*")):
        if not (has_policy and file == policy_path):
            os.remove(file)
    
    # 정책 이미지 저장
    if has_policy:
        policy_image.save(policy_path)
    
    # 세션 상태 초기화
    st.session_state.all_data = []
    st.session_state.user_assignments = {}
    st.session_state.labels = {}
    
    return True

def assign_data(total_samples, num_users):
    """데이터를 사용자 수에 따라 균등하게 분배"""
    samples_per_user = total_samples // num_users
    assignments = {}
    
    for i in range(num_users):
        start_idx = i * samples_per_user
        end_idx = start_idx + samples_per_user if i < num_users - 1 else total_samples
        assignments[f"user_{i+1}"] = list(range(start_idx, end_idx))
    
    return assignments

def calculate_progress(user, assigned_indices):
    """사용자별 진행률 계산"""
    completed = 0
    for idx in assigned_indices:
        label_data = st.session_state.labels.get(str(idx), {})
        label_value = label_data.get('label')
        if label_value not in ['선택되지 않음', None]:  # 라벨이 선택된 경우만 카운트
            completed += 1
    return completed

def save_labels_to_excel():
    """라벨링 결과를 엑셀 파일로 저장"""
    results = []
    for idx, item in enumerate(st.session_state.all_data):
        label_data = st.session_state.labels.get(str(idx), {})
        results.append({
            'instruction': item['instruction'],
            'output': item['output'],
            'label': label_data.get('label', ''),
            'labeled_by': label_data.get('user', ''),
            'timestamp': label_data.get('timestamp', '')
        })
    
    df = pd.DataFrame(results)
    # 엑셀 파일 생성
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    return output.getvalue()

def host_interface():
    """호스트 인터페이스"""
    st.header("호스트 인터페이스")
    
    # 정책 이미지 업로드
    with st.expander("라벨링 정책 관리", expanded=False):
        policy_img = st.file_uploader("라벨링 정책 이미지 업로드", type=['png', 'jpg', 'jpeg'])
        if policy_img is not None and st.button("정책 이미지 저장"):
            image_path = save_image(policy_img, POLICY_IMAGE)
            st.session_state.policy_image = Image.open(image_path)
            st.success("정책 이미지가 저장되었습니다!")
        
        # 현재 정책 이미지 표시
        if st.session_state.policy_image is not None:
            st.image(st.session_state.policy_image, caption="현재 라벨링 정책", use_column_width=True)
    
    # 데이터 초기화 섹션
    with st.expander("데이터 관리", expanded=False):
        st.warning("주의: 초기화하면 모든 데이터와 라벨링 결과가 삭제됩니다! (정책 이미지는 유지됩니다)")
        if st.button("모든 데이터 초기화"):
            if clear_all_data():
                st.success("모든 데이터가 성공적으로 초기화되었습니다!")
                st.rerun()  # UI 새로고침
    
    # 데이터 업로드
    uploaded_files = st.file_uploader(
        "JSON 파일들을 업로드하세요", 
        type=['json'], 
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("데이터 업로드"):
            new_data = []
            for file in uploaded_files:
                content = json.loads(file.read())
                new_data.extend(content)
            
            # 새 데이터 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_data(new_data, f"data_{timestamp}.json")
            st.session_state.all_data.extend(new_data)
            st.success(f"{len(new_data)}개의 새로운 데이터가 추가되었습니다!")
    
    # 데이터 현황 표시
    if st.session_state.all_data:
        st.info(f"현재 총 {len(st.session_state.all_data)}개의 데이터가 있습니다.")
    
    # 라벨러 수 설정 및 데이터 분배
    if st.session_state.all_data:
        num_users = st.number_input("라벨링 작업자 수를 입력하세요", min_value=1, value=1)
        if st.button("데이터 분배"):
            st.session_state.user_assignments = assign_data(
                len(st.session_state.all_data), 
                num_users
            )
            save_data(st.session_state.user_assignments, ASSIGNMENTS_FILE)
            st.success("데이터가 성공적으로 분배되었습니다!")
    
    # 진행 상황 확인
    if st.session_state.labels:
        st.header("진행 상황")
        for user, assigned_indices in st.session_state.user_assignments.items():
            completed = calculate_progress(user, assigned_indices)
            progress = completed / len(assigned_indices)
            st.write(f"{user}: {completed}/{len(assigned_indices)} ({progress:.1%})")
        
        # 결과 다운로드
        if st.button("결과 다운로드"):
            excel_data = save_labels_to_excel()
            st.download_button(
                label="엑셀 파일 다운로드",
                data=excel_data,
                file_name=f"labeling_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def show_info_popup(user, assigned_indices):
    """정보 팝업 표시"""
    st.sidebar.header("진행 정보")
    
    # 진행률 표시
    completed = calculate_progress(user, assigned_indices)
    progress = completed / len(assigned_indices) if len(assigned_indices) > 0 else 0
    st.sidebar.progress(progress)
    st.sidebar.write(f"진행률: {completed}/{len(assigned_indices)} ({progress:.1%})")

    # 데이터 선택 정책 표시
    st.sidebar.header("데이터 선택 기준: 국토 정보 포함")
    st.sidebar.markdown("1. 국토 이용 · 개발 · 보전과 관련된 <u>정책</u>에 대한 정보", unsafe_allow_html=True)
    st.sidebar.markdown("1. 국토 이용 · 개발 · 보전과 관련된 <u>행정 절차</u>에 대한 정보", unsafe_allow_html=True)
    st.sidebar.markdown("1. 국토 이용 · 개발 · 보전과 관련된 <u>전문 용어</u>에 대한 정보", unsafe_allow_html=True)
    
    # 정책 이미지 표시
    if st.session_state.policy_image is not None:
        st.sidebar.image(st.session_state.policy_image, caption="라벨링 정책", use_column_width=True)
    else:
        st.sidebar.warning("라벨링 정책 이미지가 없습니다.")

def labeler_interface():
    """라벨러 인터페이스"""
    st.header("국토 정보가 포함된 데이터 선택")
    
    if not st.session_state.all_data:
        st.warning("아직 업로드된 데이터가 없습니다.")
        return
    
    if not st.session_state.user_assignments:
        st.warning("아직 데이터가 분배되지 않았습니다.")
        return
    
    # 사용자 선택
    user = st.selectbox(
        "사용자 선택", 
        options=list(st.session_state.user_assignments.keys())
    )
    
    if user:
        assigned_indices = st.session_state.user_assignments[user]
        
        # 플로팅 버튼 (사이드바 토글)
        if 'show_sidebar' not in st.session_state:
            st.session_state.show_sidebar = False
            
        # 플로팅 버튼 CSS
        st.markdown("""
        <style>
        .floating-btn {
            position: fixed;
            right: 20px;
            bottom: 20px;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background-color: #4CAF50;
            color: white;
            text-align: center;
            line-height: 50px;
            font-size: 24px;
            cursor: pointer;
            z-index: 999;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.3);
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 플로팅 버튼 JavaScript
        st.markdown(f"""
        <div class="floating-btn" onclick="this.style.display='none'; document.getElementById('sidebar').style.display='block';">ℹ️</div>
        <script>
            const btn = document.querySelector('.floating-btn');
            btn.addEventListener('click', function() {{
                const sidebarEvent = new CustomEvent('streamlit:toggleSidebar');
                window.dispatchEvent(sidebarEvent);
            }});
        </script>
        """, unsafe_allow_html=True)
        
        # 사이드바에 정보 표시
        show_info_popup(user, assigned_indices)
        
        # 라벨링 인터페이스
        for idx in assigned_indices:
            if idx < len(st.session_state.all_data):
                item = st.session_state.all_data[idx]
                with st.expander(f"샘플 {idx + 1}", expanded=False):
                    st.write("**질문:**", item['instruction'])
                    st.write("**답변:**", item['output'])
                    
                    # 기존 라벨 가져오기
                    existing_label = st.session_state.labels.get(str(idx), {}).get('label', '선택되지 않음')
                    
                    # 라벨 선택 (선택되지 않음, 정책, 행정 절차, 전문용어, X)
                    label_options = ['선택되지 않음', '정책', '행정 절차', '전문용어', 'X']
                    current_index = label_options.index(existing_label) if existing_label in label_options else 0
                    
                    label = st.selectbox(
                        "라벨:",
                        options=label_options,
                        index=current_index,
                        key=f"label_{idx}"
                    )
                    
                    if label != existing_label:
                        if label == '선택되지 않음':
                            # 라벨이 선택되지 않음으로 변경된 경우, 해당 레코드 삭제
                            if str(idx) in st.session_state.labels:
                                del st.session_state.labels[str(idx)]
                        else:
                            # 라벨링된 경우
                            st.session_state.labels[str(idx)] = {
                                'label': label,
                                'user': user,
                                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                        save_data(st.session_state.labels, LABEL_FILE)
                        st.success("라벨이 저장되었습니다!")

def main():
    st.title("데이터 라벨링 플랫폼")
    
    # 인터페이스 선택
    interface = st.sidebar.radio("인터페이스 선택", ["호스트", "라벨러"])
    
    if interface == "호스트":
        host_interface()
    else:
        labeler_interface()

if __name__ == "__main__":
    main()