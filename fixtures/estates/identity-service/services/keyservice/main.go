package keyservice

import (
	"crypto/mlkem"
	"crypto/sha512"
	"crypto/tls"
)

// NewDecapsulationKey issues the service's post-quantum key-encapsulation key.
func NewDecapsulationKey() (*mlkem.DecapsulationKey1024, error) {
	return mlkem.GenerateKey1024()
}

// Digest uses SHA-384 per CNSA 2.0.
func Digest(data []byte) [48]byte {
	return sha512.Sum384(data)
}

// TLSConfig accepts TLS 1.3 only and prefers the hybrid post-quantum group.
func TLSConfig() *tls.Config {
	return &tls.Config{
		MinVersion:       tls.VersionTLS13,
		CurvePreferences: []tls.CurveID{tls.X25519MLKEM768, tls.SecP384r1MLKEM1024},
	}
}
