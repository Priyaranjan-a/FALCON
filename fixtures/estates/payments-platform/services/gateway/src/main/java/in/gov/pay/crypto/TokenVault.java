package in.gov.pay.crypto;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.security.Signature;
import javax.crypto.Cipher;
import javax.crypto.SecretKeyFactory;
import javax.net.ssl.SSLContext;

/** Card token vault used by the payments gateway. */
public final class TokenVault {

    private final SecureRandom random = new SecureRandom();

    public byte[] encryptToken(byte[] key, byte[] pan) throws Exception {
        // Legacy mode kept for compatibility with the 2014 settlement file format.
        Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
        cipher.init(Cipher.ENCRYPT_MODE, new javax.crypto.spec.SecretKeySpec(key, "AES"));
        return cipher.doFinal(pan);
    }

    public byte[] wrapForBank(byte[] data) throws Exception {
        Cipher cipher = Cipher.getInstance("RSA/ECB/OAEPWithSHA-256AndMGF1Padding");
        return cipher.doFinal(data);
    }

    public KeyPair signingKeys() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048, random);
        return generator.generateKeyPair();
    }

    public byte[] signSettlement(KeyPair keys, byte[] batch) throws Exception {
        Signature signature = Signature.getInstance("SHA1withRSA");
        signature.initSign(keys.getPrivate());
        signature.update(batch);
        return signature.sign();
    }

    public byte[] fingerprint(byte[] merchantId) throws Exception {
        return MessageDigest.getInstance("MD5").digest(merchantId);
    }

    public SecretKeyFactory pinKeys() throws Exception {
        return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA1");
    }

    public SSLContext bankLink() throws Exception {
        return SSLContext.getInstance("TLSv1.2");
    }
}
