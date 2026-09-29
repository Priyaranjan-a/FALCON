package in.gov.id;

import java.security.KeyPairGenerator;
import java.security.Signature;
import org.bouncycastle.pqc.crypto.mlkem.MLKEMParameters;
import org.bouncycastle.pqc.crypto.mldsa.MLDSAParameters;

/** Identity assertions are signed with ML-DSA-87 and wrapped with ML-KEM-1024. */
public final class QuantumSafeSigner {

    static final Object SIGNING = MLDSAParameters.ml_dsa_87;
    static final Object TRANSPORT = MLKEMParameters.ml_kem_1024;

    public Signature signer() throws Exception {
        return Signature.getInstance("ML-DSA-87");
    }

    public KeyPairGenerator transportKeys() throws Exception {
        return KeyPairGenerator.getInstance("ML-KEM-1024");
    }
}
