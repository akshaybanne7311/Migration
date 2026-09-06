import datetime
import io
import tarfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from tests.conftest import FIXTURES_DIR


def _make_self_signed_pem(cn: str) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def _build_ucs_with_cert(cert_pem: bytes) -> bytes:
    conf_text = (FIXTURES_DIR / "synthetic_bigip.conf").read_text()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in (
            ("config/bigip.conf", conf_text.encode()),
            ("config/ssl/ssl.crt/mycert.crt", cert_pem),
        ):
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def test_download_returns_the_original_pem_bytes(client):
    pem = _make_self_signed_pem("download-me.example.com")
    ucs_bytes = _build_ucs_with_cert(pem)

    resp = client.post(
        "/api/v1/sessions",
        files={"file": ("with-cert.ucs", io.BytesIO(ucs_bytes), "application/octet-stream")},
    )
    assert resp.status_code == 200, resp.text
    session_id = resp.json()["id"]
    assert resp.json()["status"] == "ready"

    objs = client.get(f"/api/v1/sessions/{session_id}/system-objects").json()["items"]
    certs = [o for o in objs if o["object_type"] == "x509 certificate"]
    assert len(certs) == 1
    import json as _json

    fingerprint = _json.loads(certs[0]["entries_json"])["fingerprint_sha256"]

    download = client.get(f"/api/v1/sessions/{session_id}/certificates/{fingerprint}/download")
    assert download.status_code == 200
    assert download.content == pem
    assert download.headers["content-type"] == "application/x-pem-file"
    assert "download-me.example.com" in download.headers["content-disposition"]


def test_download_unknown_fingerprint_is_404(ready_session_id, client):
    resp = client.get(f"/api/v1/sessions/{ready_session_id}/certificates/deadbeef/download")
    assert resp.status_code == 404
