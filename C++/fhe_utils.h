#pragma once

#include <seal/seal.h>
#include <vector>
#include <string>

std::vector<std::string> list_index_files(const std::string &folder_path);

seal::Ciphertext load_cipher_from_file(const std::string &path, seal::SEALContext context);

// GaloisKeys 인자 추가됨
seal::Ciphertext fhe_dot_product(
        seal::Ciphertext &query,
        seal::Ciphertext &index,
        seal::Evaluator &evaluator,
        const seal::RelinKeys &relin_keys,
        const seal::GaloisKeys &gal_keys
);