"""Cloud services and hardware modules declared as infrastructure-as-code.

Terraform resource blocks, CloudFormation resources and cert-manager
certificates are read for the keys they create: AWS KMS and ACM, Azure Key
Vault, Google Cloud KMS, and dedicated HSMs. Each cloud key becomes a cloud
service artefact linked to the algorithm it uses.
"""
from __future__ import annotations

import re
from typing import Iterator

from .. import names
from ..catalogue import AlgorithmRef
from ..model import Evidence, Finding, algorithm_finding, algorithm_relation, snippet
from ..walker import FileInfo

DETECTOR = "infrastructure-as-code"
_RESOURCE = re.compile(r'^\s*resource\s+"(?P<type>[\w-]+)"\s+"(?P<name>[\w-]+)"\s*\{')
_ATTR = re.compile(r'^\s*(?P<key>[\w-]+)\s*=\s*"?(?P<value>[^"\n#]*)"?')


def aws_key_spec(spec: str, usage: str | None = None) -> AlgorithmRef | None:
    spec = spec.upper()
    if spec in ("SYMMETRIC_DEFAULT", ""):
        return AlgorithmRef("AES", "256", "GCM")
    if m := re.match(r"RSA_(\d{4})", spec):
        return AlgorithmRef("RSA", m.group(1))
    if m := re.match(r"ECC_NIST_(P\d{3})", spec):
        return AlgorithmRef("ECDH" if usage == "KEY_AGREEMENT" else "ECDSA", f"P-{m.group(1)[1:]}")
    if spec == "ECC_SECG_P256K1":
        return AlgorithmRef("ECDSA", "secp256k1")
    if m := re.match(r"HMAC_(\d{3})", spec):
        return AlgorithmRef("HMAC", hash=names.hash_name(f"sha{m.group(1)}"))
    if m := re.match(r"ML_DSA_(\d{2})", spec):
        return AlgorithmRef("ML-DSA", m.group(1))
    if spec == "SM2":
        return AlgorithmRef("SM2")
    return None


def gcp_algorithm(value: str) -> AlgorithmRef | None:
    v = value.upper()
    if v == "GOOGLE_SYMMETRIC_ENCRYPTION" or v.startswith("AES_256_GCM"):
        return AlgorithmRef("AES", "256", "GCM")
    if m := re.match(r"AES_(128|256)_(GCM|CBC|CTR)", v):
        return AlgorithmRef("AES", m.group(1), m.group(2))
    if m := re.match(r"RSA_(SIGN|DECRYPT)_(PSS|PKCS1|OAEP|RAW_PKCS1)_(\d{4})(?:_SHA(\d+))?", v):
        padding = {"PSS": "PSS", "OAEP": "OAEP", "PKCS1": "PKCS1v15", "RAW_PKCS1": "PKCS1v15"}[m.group(2)]
        return AlgorithmRef("RSA", m.group(3), padding=padding, hash=names.hash_name(f"sha{m.group(4)}") if m.group(4) else None)
    if m := re.match(r"EC_SIGN_(P256|P384|SECP256K1)_SHA(\d+)", v):
        curve = {"P256": "P-256", "P384": "P-384", "SECP256K1": "secp256k1"}[m.group(1)]
        return AlgorithmRef("ECDSA", curve, hash=names.hash_name(f"sha{m.group(2)}"))
    if v == "EC_SIGN_ED25519":
        return AlgorithmRef("EdDSA", "Ed25519")
    if m := re.match(r"HMAC_SHA(\d+)", v):
        return AlgorithmRef("HMAC", hash=names.hash_name(f"sha{m.group(1)}"))
    if m := re.search(r"ML_DSA_(\d{2})", v):
        return AlgorithmRef("ML-DSA", m.group(1))
    if "SLH_DSA" in v:
        return AlgorithmRef("SLH-DSA")
    if m := re.search(r"ML_KEM_(\d{3,4})", v):
        return AlgorithmRef("ML-KEM", m.group(1))
    return None


def azure_key(key_type: str, size: str | None, curve: str | None) -> AlgorithmRef | None:
    kt = key_type.upper().replace("-HSM", "")
    if kt == "RSA":
        return AlgorithmRef("RSA", size or "2048")
    if kt == "EC":
        return AlgorithmRef("ECDSA", {"P-256": "P-256", "P-384": "P-384", "P-521": "P-521", "P-256K": "secp256k1"}.get((curve or "P-256").upper(), curve))
    if kt == "OCT":
        return AlgorithmRef("AES", size or "256")
    return None


def _blocks(lines: list[str]) -> Iterator[tuple[str, str, int, dict[str, tuple[str, int]]]]:
    """Terraform resource blocks: (type, name, start line index, attributes -> (value, line index))."""
    i = 0
    while i < len(lines):
        m = _RESOURCE.match(lines[i])
        if not m:
            i += 1
            continue
        depth = lines[i].count("{") - lines[i].count("}")
        attrs: dict[str, tuple[str, int]] = {}
        j = i + 1
        while j < len(lines) and depth > 0:
            depth += lines[j].count("{") - lines[j].count("}")
            a = _ATTR.match(lines[j])
            if a and a.group("key") not in attrs:
                attrs[a.group("key")] = (a.group("value").strip(), j)
            j += 1
        yield m.group("type"), m.group("name"), i, attrs
        i = j


def _cloud(provider: str, service: str, resource: str, label: str, ref: AlgorithmRef | None, evidence: Evidence,
           props: dict, rule: str) -> Finding:
    related = [algorithm_relation("protects-with", ref)] if ref else []
    return Finding(kind="cloud_service", identity={"provider": provider, "service": service, "resource": resource},
                   name=label, evidence=evidence, detector=DETECTOR, rule=rule, confidence=0.95, function="key-management",
                   properties={"provider": provider, "service": service, **props}, related=related)


def _hardware(module: str, vendor: str, evidence: Evidence, rule: str, props: dict | None = None) -> Finding:
    return Finding(kind="hardware", identity={"type": "hsm", "module": module}, name=vendor, evidence=evidence,
                   detector=DETECTOR, rule=rule, confidence=0.95, function="key-protection",
                   properties={"vendor": vendor, "type": "hsm", "interface": "cloud", **(props or {})})


def scan(file: FileInfo, text: str) -> Iterator[Finding]:
    lines = text.splitlines()
    rel = file.rel

    def ev(index: int) -> Evidence:
        return Evidence(rel, index + 1, None, snippet(lines, index))

    if file.name.endswith((".tf", ".hcl")):
        for rtype, rname, start, attrs in _blocks(lines):
            address = f"{rtype}.{rname}"
            value = lambda k: attrs.get(k, ("", start))[0]  # noqa: E731
            line = lambda k: attrs.get(k, ("", start))[1]  # noqa: E731
            if rtype == "aws_kms_key":
                key = "key_spec" if "key_spec" in attrs else "customer_master_key_spec"
                spec = value(key) or "SYMMETRIC_DEFAULT"
                usage = value("key_usage") or "ENCRYPT_DECRYPT"
                ref = aws_key_spec(spec, usage)
                yield _cloud("aws", "kms", address, f"AWS KMS key · {rname}", ref, ev(line(key)),
                             {"key_spec": spec, "key_usage": usage, "rotation": value("enable_key_rotation") == "true",
                              "multi_region": value("multi_region") == "true"}, "tf.aws-kms")
            elif rtype == "aws_acm_certificate":
                spec = value("key_algorithm") or "RSA_2048"
                ref = aws_key_spec(spec.replace("EC_prime256v1", "ECC_NIST_P256").replace("EC_secp384r1", "ECC_NIST_P384").replace("EC_secp521r1", "ECC_NIST_P521"))
                yield _cloud("aws", "acm", address, f"AWS Certificate Manager · {rname}", ref, ev(line("key_algorithm")),
                             {"key_algorithm": spec, "domain": value("domain_name") or None}, "tf.aws-acm")
            elif rtype == "aws_cloudhsm_v2_cluster":
                yield _hardware("aws-cloudhsm", "AWS CloudHSM", ev(start), "tf.aws-cloudhsm", {"hsm_type": value("hsm_type") or None})
            elif rtype == "azurerm_key_vault_key":
                key_type = value("key_type") or "RSA"
                ref = azure_key(key_type, value("key_size") or None, value("curve") or None)
                yield _cloud("azure", "key-vault", address, f"Azure Key Vault key · {rname}", ref, ev(line("key_type")),
                             {"key_type": key_type, "protection": "HSM" if key_type.upper().endswith("-HSM") else "software"}, "tf.azure-keyvault")
            elif rtype == "azurerm_key_vault_managed_hardware_security_module":
                yield _hardware("azure-managed-hsm", "Azure Managed HSM", ev(start), "tf.azure-managed-hsm")
            elif rtype == "google_kms_crypto_key":
                algorithm = value("algorithm") or "GOOGLE_SYMMETRIC_ENCRYPTION"
                ref = gcp_algorithm(algorithm)
                protection = value("protection_level") or "SOFTWARE"
                yield _cloud("gcp", "cloud-kms", address, f"Google Cloud KMS key · {rname}", ref, ev(line("algorithm")),
                             {"algorithm": algorithm, "purpose": value("purpose") or "ENCRYPT_DECRYPT", "protection": protection}, "tf.gcp-kms")
                if protection == "HSM":
                    yield _hardware("gcp-cloud-hsm", "Google Cloud HSM", ev(line("protection_level")), "tf.gcp-cloud-hsm")

    if "AWS::KMS::Key" in text or "AWS::CertificateManager::Certificate" in text:
        for index, line in enumerate(lines):
            if "AWS::KMS::Key" in line:
                window = lines[index: index + 25]
                spec_line = next(((i, l) for i, l in enumerate(window) if re.search(r"KeySpec", l)), None)
                usage = next((re.search(r"KeyUsage\W+(\w+)", l).group(1) for l in window if re.search(r"KeyUsage\W+(\w+)", l)), None)
                spec = re.search(r"KeySpec\W+(\w+)", spec_line[1]).group(1) if spec_line else "SYMMETRIC_DEFAULT"
                logical = next((re.match(r"^\s*\"?([\w-]+)\"?\s*:", lines[j]).group(1) for j in range(index - 1, max(index - 4, -1), -1)
                                if re.match(r"^\s*\"?([\w-]+)\"?\s*:\s*\{?\s*$", lines[j])), "KmsKey")
                yield _cloud("aws", "kms", f"AWS::KMS::Key.{logical}", f"AWS KMS key · {logical}", aws_key_spec(spec, usage),
                             ev(index + (spec_line[0] if spec_line else 0)), {"key_spec": spec, "key_usage": usage}, "cfn.aws-kms")

    if "cert-manager.io" in text and re.search(r"kind:\s*Certificate\b", text):
        algorithm = re.search(r"privateKey:\s*\n(?:\s+.*\n)*?\s+algorithm:\s*(\w+)", text)
        size = re.search(r"privateKey:\s*\n(?:\s+.*\n)*?\s+size:\s*(\d+)", text)
        name = (algorithm.group(1) if algorithm else "RSA").upper()
        ref = {"RSA": AlgorithmRef("RSA", size.group(1) if size else "2048"),
               "ECDSA": AlgorithmRef("ECDSA", {"256": "P-256", "384": "P-384", "521": "P-521"}.get(size.group(1) if size else "256")),
               "ED25519": AlgorithmRef("EdDSA", "Ed25519")}.get(name)
        index = text[: algorithm.start()].count("\n") + 1 if algorithm else next((i for i, l in enumerate(lines) if "kind: Certificate" in l), 0)
        if ref:
            yield algorithm_finding(ref, ev(index), detector=DETECTOR, rule="k8s.cert-manager", confidence=0.9,
                                    function="certificate-issuance", library="cert-manager",
                                    extra={"note": "Key algorithm for certificates issued by cert-manager"})
