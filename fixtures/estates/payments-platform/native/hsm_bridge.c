/* Bridge between the settlement engine and the payment HSM. */
#include <openssl/evp.h>
#include <openssl/rsa.h>
#include <openssl/ssl.h>
#include <oqs/oqs.h>
#include "cryptoki.h"

static const char *PKCS11_MODULE = "/opt/safenet/lunaclient/lib/libCryptoki2_64.so";

int bridge_init(void) {
    CK_RV rv = C_Initialize(NULL);
    return rv == CKR_OK ? 0 : -1;
}

RSA *legacy_key(void) {
    RSA *rsa = RSA_new();
    BIGNUM *e = BN_new();
    BN_set_word(e, RSA_F4);
    RSA_generate_key_ex(rsa, 2048, e, NULL);
    return rsa;
}

int encrypt_pin_block(unsigned char *out, const unsigned char *in, int len, const unsigned char *key) {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_des_ede3_cbc(), NULL, key, NULL);
    return EVP_EncryptUpdate(ctx, out, &len, in, len);
}

void digest(const unsigned char *data, size_t n, unsigned char *md) {
    EVP_Digest(data, n, md, NULL, EVP_sha1(), NULL);
}

SSL_CTX *link_context(void) {
    SSL_CTX *ctx = SSL_CTX_new(TLS_method());
    SSL_CTX_set_min_proto_version(ctx, TLS1_2_VERSION);
    SSL_CTX_set1_groups_list(ctx, "X25519MLKEM768:X25519");
    return ctx;
}

OQS_KEM *pq_channel(void) {
    return OQS_KEM_new(OQS_KEM_alg_ml_kem_768);
}
