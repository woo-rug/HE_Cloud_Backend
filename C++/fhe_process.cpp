#include "fhe_process.h"
#include "fhe_utils.h"
#include "base64.h"

#include <seal/seal.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>

using json = nlohmann::json;
using namespace seal;
using namespace std;
namespace fs = std::filesystem;

void process_index_folder(const string &query_path, const string &index_folder, seal::SEALContext context, seal::Evaluator &evaluator, seal::RelinKeys relin_keys, seal::GaloisKeys gal_keys) {
    // 쿼리 로드
    Ciphertext query;
    try {
        query = load_cipher_from_file(query_path, context);
    } catch (...) {
        json err; err["error"] = "Failed to load query file";
        cout << err.dump() << endl;
        return;
    }

    // 폴더에서 파일 목록 가져오기
    vector<string> index_list = list_index_files(index_folder);

    for (string &index_path : index_list) {
        try {
            // 인덱스 벡터 로드
            Ciphertext index = load_cipher_from_file(index_path, context);

            // 동형 내적 연산 수행 (GaloisKeys 전달)
            Ciphertext result = fhe_dot_product(query, index, evaluator, relin_keys, gal_keys);

            // 결과 직렬화
            stringstream ss;
            result.save(ss);
            string raw = ss.str();

            // Base64 인코딩 (reinterpret_cast 필요)
            string encoded_result = base64_encode(reinterpret_cast<const unsigned char*>(raw.c_str()), raw.length());

            // 파일명에서 index_id 추출
            string filename = fs::path(index_path).filename().string(); // '123.eiv'
            string index_id_str = filename.substr(0, filename.find('.')); // '123'
            int index_id = stoi(index_id_str);

            // 결과를 JSON 형태로 출력
            json result_json;
            result_json["index_id"] = index_id;
            result_json["enc_score"] = encoded_result;

            // Python 백엔드가 readline()으로 읽으므로 줄바꿈 필수
            cout << result_json.dump() << endl;

        } catch (const exception& e) {
            // 개별 파일 에러 시 전체 중단하지 않고 로그 출력 후 계속
            json err;
            err["error"] = string("Error processing ") + index_path + ": " + e.what();
            cerr << err.dump() << endl;
        }
    }
}