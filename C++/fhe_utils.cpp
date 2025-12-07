#include "fhe_utils.h"
#include <filesystem>
#include <fstream>
#include <cmath>

using namespace seal;
using namespace std;
namespace fs = std::filesystem;

vector<string> list_index_files(const string &folder_path) {
    vector<string> index_files;
    if (!fs::exists(folder_path)) return index_files;

    for (const auto &entry : fs::directory_iterator(folder_path)) {
        if (entry.is_regular_file() && entry.path().extension() == ".eiv") {
            index_files.push_back(entry.path().string());
        }
    }
    return index_files;
}

seal::Ciphertext load_cipher_from_file(const std::string &path, seal::SEALContext context) {
    Ciphertext ct;
    ifstream in(path, ios::binary);
    if (!in.is_open()) {
        throw runtime_error("File load failed: " + path);
    }
    ct.load(context, in);
    return ct;
}

// [핵심 변경] BFV용 내적 연산
seal::Ciphertext fhe_dot_product(seal::Ciphertext &query, seal::Ciphertext &index, seal::Evaluator &evaluator, const seal::RelinKeys &relin_keys, const seal::GaloisKeys &gal_keys) {
    Ciphertext result;

    // 1. 곱셈 (1 or 0)
    evaluator.multiply(query, index, result);

    // 2. 재선형화 (필수)
    evaluator.relinearize_inplace(result, relin_keys);

    // 3. 슬롯 합산 (Rotate & Add)
    // BFV Batching 모드에서는 슬롯 개수 전체(poly_degree)를 사용하거나 절반을 사용함.
    // 여기서는 안전하게 log2(poly_degree / 2) 만큼 회전
    size_t slot_count = query.poly_modulus_degree() / 2;

    Ciphertext temp;
    for (int i = 0; i < (int)log2(slot_count); i++) {
        evaluator.rotate_rows(result, pow(2, i), gal_keys, temp); // BFV는 rotate_rows 사용 권장
        evaluator.add_inplace(result, temp);
    }

    // 가로축 더한 것을 세로축으로 더함
    evaluator.rotate_columns(result, gal_keys, temp);
    evaluator.add_inplace(result, temp);

    return result;
}