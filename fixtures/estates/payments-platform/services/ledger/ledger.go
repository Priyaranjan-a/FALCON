package ledger

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha1"
	"crypto/tls"
)

// SettlementKeys creates the ledger's long-term signing keys.
func SettlementKeys() (*rsa.PrivateKey, *ecdsa.PrivateKey, error) {
	archive, err := rsa.GenerateKey(rand.Reader, 3072)
	if err != nil {
		return nil, nil, err
	}
	session, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	return archive, session, err
}

// ReceiptID keeps compatibility with the mainframe batch format.
func ReceiptID(batch []byte) [20]byte {
	return sha1.Sum(batch)
}

// ServerTLS is shared by every ledger listener.
func ServerTLS() *tls.Config {
	return &tls.Config{
		MinVersion:       tls.VersionTLS12,
		CurvePreferences: []tls.CurveID{tls.X25519MLKEM768, tls.X25519, tls.CurveP256},
		CipherSuites:     []uint16{tls.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256, tls.TLS_RSA_WITH_AES_128_CBC_SHA},
	}
}
