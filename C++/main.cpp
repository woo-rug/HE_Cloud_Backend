#include <iostream>
#include <string>
#include <chrono>
#include <filesystem>
#include <fstream>
#include "fhe_process.h"
#include <seal/seal.h>

using namespace std;
using namespace seal;

// 인자 파싱용 구조체
struct Args {
    string query_path, vector_folder, keys_path;
    size_t poly_degree = 8192; // BFV는 4096으로도 충분 (속도 향상)
};

Args parse_arguments(int argc, char* argv[]) {
    Args args;
    for (int i = 1; i < argc; i++) {
        string arg = argv[i];
        if (arg == "--query" && i + 1 < argc) args.query_path = argv[++i];
        else if (arg == "--vector-folder" && i + 1 < argc) args.vector_folder = argv[++i];
        else if (arg == "--keys-path" && i + 1 < argc) args.keys_path = argv[++i];
        else if (arg == "--poly-degree" && i + 1 < argc) args.poly_degree = stoi(argv[++i]);
    }
    return args;
}

int main(int argc, char* argv[]) {
    try {
        Args args = parse_arguments(argc, argv);
        if (args.query_path.empty() || args.vector_folder.empty() || args.keys_path.empty()) {
            cerr << "Usage: ./fhe_search_engine --query <path> --vector-folder <path> --keys-path <path>" << endl;
            return 1;
        }

        // [핵심 변경] 1. BFV Context 설정
        EncryptionParameters params(scheme_type::bfv);
        params.set_poly_modulus_degree(args.poly_degree);
        params.set_coeff_modulus(CoeffModulus::BFVDefault(args.poly_degree));
        // Plain Modulus: 결과값(최대 4096)을 담을 수 있게 20비트 정도 설정
        params.set_plain_modulus(PlainModulus::Batching(args.poly_degree, 20));

        SEALContext context(params);
        if (!context.parameters_set()) throw runtime_error("Invalid SEAL parameters");

        Evaluator evaluator(context);

        // 2. 키 로딩
        RelinKeys relin_keys;
        GaloisKeys gal_keys;

        ifstream relin_fs(args.keys_path + "/relin_keys.k", ios::binary);
        relin_keys.load(context, relin_fs);

        ifstream gal_fs(args.keys_path + "/gal_keys.k", ios::binary);
        gal_keys.load(context, gal_fs);

        auto start_time = chrono::high_resolution_clock::now();
        // 3. 실행
        process_index_folder(args.query_path, args.vector_folder, context, evaluator, relin_keys, gal_keys);

        auto end_time = chrono::high_resolution_clock::now();
        chrono::duration<double> elasped = end_time - start_time;
        cerr << "[BENCHMARK TIME]" << elasped.count() << endl;

    } catch (const exception &e) {
        cerr << "Error: " << e.what() << endl;
        return 1;
    }
    return 0;
}