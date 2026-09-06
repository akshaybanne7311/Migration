import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.ingest.certificates import parse_certificates


def _make_self_signed_pem(cn: str, days_valid: int, not_before_offset_days: int = 0) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now + datetime.timedelta(days=not_before_offset_days))
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def test_parses_real_expiry_and_flags_expired_vs_valid():
    valid_pem = _make_self_signed_pem("still-valid.example.com", days_valid=365)
    expired_pem = _make_self_signed_pem("expired.example.com", days_valid=-30, not_before_offset_days=-400)

    results = parse_certificates({"config/ssl/ssl.crt/valid.crt": valid_pem, "config/ssl/ssl.crt/expired.crt": expired_pem})

    by_cn = {c.subject_cn: c for c in results}
    assert by_cn["still-valid.example.com"].is_expired is False
    assert by_cn["still-valid.example.com"].days_until_expiry > 300
    assert by_cn["expired.example.com"].is_expired is True
    assert by_cn["expired.example.com"].days_until_expiry < 0
    assert by_cn["still-valid.example.com"].is_self_signed is True


def test_same_certificate_at_multiple_paths_is_deduplicated():
    pem = _make_self_signed_pem("dup.example.com", days_valid=100)
    results = parse_certificates(
        {
            "config/ssl/ssl.crt/dup.crt": pem,
            "config/filestore/files_d/Common_d/certificate_d/:Common:dup.crt_1_1": pem,
        }
    )
    assert len(results) == 1
    assert set(results[0].source_paths) == {
        "config/ssl/ssl.crt/dup.crt",
        "config/filestore/files_d/Common_d/certificate_d/:Common:dup.crt_1_1",
    }


def test_malformed_pem_is_skipped_not_raised():
    results = parse_certificates({"config/ssl/ssl.crt/broken.crt": b"-----BEGIN CERTIFICATE-----\nnot real\n"})
    assert results == []
