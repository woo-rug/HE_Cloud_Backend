# HE-Cloud: 동형암호 기반 프라이버시 보존형 클라우드 검색 시스템

## 1. 프로젝트 소개
이 프로젝트는 모바일/데스크톱 환경에서 동형암호를 이용하여 서버가 내용을 알 수 없는 상태로 파일을 저장하고 검색하는 시스템입니다.
- **Frontend:** Flutter (Dart)
- **Backend:** Python FastAPI
- **Core Engine:** C++ (Microsoft SEAL)

## 2. 사전 요구 사항 (Prerequisites)
이 프로젝트를 실행하기 위해서는 다음 도구들이 설치되어 있어야 합니다.
- Python 3.10 이상
- MySQL Server
- C++ 컴파일러 (GCC 또는 Clang), CMake
- Flutter SDK

## 3. 설치 및 실행 방법 (Installation)

### Step 1. 데이터베이스 설정
1. MySQL에 `he_cloud` 데이터베이스를 생성합니다.
2. `HE_Cloud_Backend` 폴더에 `.env` 파일을 생성하고, `.env.example`을 참고하여 본인의 DB 정보(비밀번호 등)를 입력합니다.

### Step 2. Backend (Server) 실행
```bash
cd HE_Cloud_Backend
pip install -r requirements.txt
uvicorn main:app --reload