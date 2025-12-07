#pragma once
#include <string>
#include <seal/seal.h>

using namespace std;

void process_index_folder(
    const string &query_path,
    const string &index_folder,
    seal::SEALContext context,
    seal::Evaluator &evaluator,
    seal::RelinKeys relin_keys,
    seal::GaloisKeys gal_keys // 추가됨
);