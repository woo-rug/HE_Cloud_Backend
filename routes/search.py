import asyncio
from typing import List
from fastapi import APIRouter, HTTPException, Depends, WebSocket, UploadFile, Form, File

from db import SessionLocal
from models import IndexVector, User, Dictionary
from dependencies.auth import get_current_user
import os, aiofiles, json, uuid, sys

router = APIRouter()
# [주의] Docker 환경 변수나 설정에 맞춰 경로 확인 필요
UPLOAD_FOLDER = "uploads"
# 만약 Docker 내부 절대 경로라면 '/app/uploads', 로컬 테스트면 'uploads'

@router.post("/upload/queries")
async def upload_queries(
        dict_versions: str = Form(...),
        queries: List[UploadFile] = File(...),
        user: User = Depends(get_current_user)
):
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    try:
        dict_versions_list = json.loads(dict_versions)
    except:
        raise HTTPException(status_code=400, detail="사전 버전이 JSON 리스트 형태가 아닙니다.")

    # 개수 확인 (안전장치)
    if len(dict_versions_list) != len(queries):
        raise HTTPException(status_code=400, detail="쿼리 파일 수와 사전 버전 수가 일치하지 않습니다.")

    # 쿼리 저장 폴더
    user_query_dir = os.path.join(UPLOAD_FOLDER, "query", f"user_{user.id}")
    os.makedirs(user_query_dir, exist_ok=True)

    result_ids = []

    for query in queries:
        qid = str(uuid.uuid4())

        save_path = os.path.join(user_query_dir, f"{qid}.eiv")
        async with aiofiles.open(save_path, mode="wb") as f:
            query_vector = await query.read()
            await f.write(query_vector)

        result_ids.append(qid)

    pairs = []
    for qid, version in zip(result_ids, dict_versions_list):
        pairs.append({"query_id": qid, "dict_version": version})

    return {"queries": pairs}


@router.websocket("/search")
async def search_stream(websocket: WebSocket):
    await websocket.accept()

    # 사용자 토큰 받기
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4000, reason="토큰이 없습니다.")
        return

    try:
        user = get_current_user(token)
    except Exception:
        await websocket.close(code=4001, reason="토큰이 유효하지 않습니다.")
        return

    if not user:
        await websocket.close(code=4001, reason="회원 인증 실패")
        return

    # JSON 수신
    try:
        body = await websocket.receive_json()

        if isinstance(body, list):
            items = body
        elif isinstance(body, dict):
            items = body.get("items", [])
        else:
            items = []

    except Exception as e:
        print(f"WebSocket JSON Error: {e}")
        await websocket.close(code=4002, reason="JSON 파싱 오류")
        return

    db = SessionLocal()

    # 쿼리 작업 목록 구성
    query_jobs = []

    for entity in items:  # body 대신 items 순회
        dict_version = entity["dict_version"]
        qid = entity["query_id"]

        dict_row = db.query(Dictionary).filter(Dictionary.owner_id == user.id,
                                               Dictionary.version == dict_version).first()
        if not dict_row:
            await websocket.send_json({"error": f"사전 버전 {dict_version}을 찾을 수 없습니다."})
            continue

        keys_path = os.path.join(UPLOAD_FOLDER, "keys", f"user_{user.id}")

        # 쿼리 파일 경로
        query_path = os.path.join(UPLOAD_FOLDER, "query", f"user_{user.id}", f"{qid}.eiv")

        # 인덱스 벡터 폴더 경로
        vector_folder = os.path.join(UPLOAD_FOLDER, "index", f"user_{user.id}", f"dict_{dict_version}")

        # 파일 존재 여부 체크
        if not os.path.exists(query_path):
            await websocket.send_json({"error": f"쿼리 파일 없음: {qid}"})
            continue

        query_jobs.append({
            "query_path": query_path,
            "vector_folder": vector_folder,
            "dict_version": dict_version,
            "poly_degree": dict_row.poly_degree,
            "keys_path": keys_path
        })

    print(query_jobs)

    # C++ 연산 실행
    # Docker : /app/bin/fhe_search_engine , 로컬 : ./bin/fhe_search_engine
    FHE_SEARCH_BIN = "/app/bin/fhe_search_engine"
    if not os.path.exists(FHE_SEARCH_BIN):
        # 로컬 테스트용 경로 (예시)
        FHE_SEARCH_BIN = "./bin/fhe_search_engine"

        # 검색 작업(Job) 하나씩 순회
        for job in query_jobs:
            cmd = [
                FHE_SEARCH_BIN,
                "--query", job["query_path"],
                "--vector-folder", job["vector_folder"],
                "--poly-degree", str(job["poly_degree"]),
                "--keys-path", job["keys_path"]
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    limit=1024 * 1024 * 100
                )
            except Exception as e:
                await websocket.send_json({"error": f"C++ 실행 실패: {str(e)}"})
                continue

            # [트래픽 측정용 변수 유지]
            total_traffic_size = 0

            # stdout 읽기 루프 (결과 처리)
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                decoded_line = line.decode().strip()
                if not decoded_line: continue

                try:
                    cpp_result = json.loads(decoded_line)
                    index_id = cpp_result.get("index_id")
                    enc_score = cpp_result.get("enc_score")

                    if index_id is None: continue

                    # DB 매핑
                    index_row = db.query(IndexVector).filter(
                        IndexVector.owner_id == user.id,
                        IndexVector.id == index_id
                    ).first()

                    if index_row:
                        result = {
                            "file_id": index_row.doc_id,
                            "score": enc_score,
                        }

                        # [요청하신 대로 트래픽 로직은 그대로 유지]
                        json_str = json.dumps(result)
                        real_traffic_size = len(json_str.encode('utf-8'))
                        print(
                            f"[BENCHMARK_TRAFFIC] Size: {real_traffic_size} Bytes ({real_traffic_size / 1024:.2f} KB)")

                        await websocket.send_json(result)

                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"Processing Error: {e}")

            stderr_data = await process.stderr.read()
            await process.wait()  # 프로세스 종료 대기

            # 여기서 바로 출력해야 매 검색마다 뜹니다.
            if stderr_data:
                print(f"======== [C++ TIME LOG] ========")
                print(f"{stderr_data.decode().strip()}")
                print("================================")

    await websocket.send_json({"status": "end"})
    await websocket.close()