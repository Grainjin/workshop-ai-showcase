from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parent.parent
CERTS_DIR = ROOT / "backend" / "certs"
PRIVATE_PATH = CERTS_DIR / "jwt-private.pem"
PUBLIC_PATH = CERTS_DIR / "jwt-public.pem"


def generate_rsa_pem_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def main():
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    if PRIVATE_PATH.exists() and PUBLIC_PATH.exists():
        print(f"JWT keys already exist in {CERTS_DIR}")
        return

    private_pem, public_pem = generate_rsa_pem_pair()
    PRIVATE_PATH.write_text(private_pem, encoding="utf-8")
    PUBLIC_PATH.write_text(public_pem, encoding="utf-8")
    PRIVATE_PATH.chmod(0o600)
    print(f"Wrote {PRIVATE_PATH} and {PUBLIC_PATH}")


if __name__ == "__main__":
    main()
