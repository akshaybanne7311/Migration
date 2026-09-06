"""Parse real X.509 certificate files pulled from a UCS/QKView archive.

`cm cert` stanzas in bigip.conf only carry cache-path/checksum/revision --
no expiration date, since that's a property of the actual certificate
bytes, which live elsewhere in the archive as real PEM files. The same
certificate is typically present at multiple archive paths (client-facing
copy under config/ssl/ssl.crt/, plus one or more filestore revisions under
certificate_d/ / trust_certificate_d/) -- deduplicated here by SHA-256
fingerprint of the DER bytes so a device with one cert doesn't get
reported as three.
"""
import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID
from pydantic import BaseModel

from app.models.domain import SystemObject


class CertificateInfo(BaseModel):
    fingerprint_sha256: str
    subject_cn: Optional[str] = None
    subject: str
    issuer_cn: Optional[str] = None
    issuer: str
    serial_number: str
    not_before: str
    not_after: str
    days_until_expiry: int
    is_expired: bool
    is_self_signed: bool
    source_paths: List[str]


def _common_name(name: x509.Name) -> Optional[str]:
    attrs = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    return attrs[0].value if attrs else None


def parse_certificates(files: Dict[str, bytes]) -> List[CertificateInfo]:
    by_fingerprint: Dict[str, CertificateInfo] = {}
    now = datetime.now(timezone.utc)

    for path, pem_bytes in files.items():
        try:
            cert = x509.load_pem_x509_certificate(pem_bytes, default_backend())
        except ValueError:
            # Not a valid/parseable certificate (bundle-of-multiple-PEMs,
            # corrupted export, etc.) -- skip rather than guess.
            continue

        fingerprint = hashlib.sha256(cert.public_bytes(encoding=Encoding.DER)).hexdigest()

        if fingerprint in by_fingerprint:
            by_fingerprint[fingerprint].source_paths.append(path)
            continue

        not_after = cert.not_valid_after_utc
        days_until_expiry = (not_after - now).days
        by_fingerprint[fingerprint] = CertificateInfo(
            fingerprint_sha256=fingerprint,
            subject_cn=_common_name(cert.subject),
            subject=cert.subject.rfc4514_string(),
            issuer_cn=_common_name(cert.issuer),
            issuer=cert.issuer.rfc4514_string(),
            serial_number=str(cert.serial_number),
            not_before=cert.not_valid_before_utc.isoformat(),
            not_after=not_after.isoformat(),
            days_until_expiry=days_until_expiry,
            is_expired=days_until_expiry < 0,
            is_self_signed=cert.subject == cert.issuer,
            source_paths=[path],
        )

    return sorted(by_fingerprint.values(), key=lambda c: c.days_until_expiry)


def certificate_to_system_object(cert: CertificateInfo) -> SystemObject:
    """Reuses the existing generic system_objects table/API instead of a
    dedicated one -- certs are few (single digits to low tens per device),
    so there's no volume reason to special-case storage the way command
    history needed its own table."""
    name = cert.subject_cn or cert.fingerprint_sha256[:16]
    return SystemObject(
        object_type="x509 certificate",
        name=name,
        entries_json=json.dumps(cert.model_dump()),
    )
