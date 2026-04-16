from OpenSSL import crypto
import os
import datetime

def generate_self_signed_cert(cert_path, key_path):
    print("[*] Generating self-signed certificate for 192.168.1.196 and heathson.ai.local...")
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)

    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "Local"
    cert.get_subject().L = "Local"
    cert.get_subject().O = "OpenCode Local"
    cert.get_subject().OU = "VoiceBridge"
    cert.get_subject().CN = "heathson.ai.local"
    cert.set_serial_number(1001)
    
    now = datetime.datetime.now(datetime.timezone.utc)
    not_before = now.strftime("%Y%m%d%H%M%SZ").encode('utf-8')
    not_after = (now + datetime.timedelta(days=3650)).strftime("%Y%m%d%H%M%SZ").encode('utf-8')
    
    cert.set_notBefore(not_before)
    cert.set_notAfter(not_after)
    
    # SAN (Subject Alternative Names)
    sans = [
        b"DNS:heathson.ai.local",
        b"IP:192.168.1.196",
        b"IP:127.0.0.1",
        b"DNS:localhost"
    ]
    cert.add_extensions([
        crypto.X509Extension(b"subjectAltName", False, b", ".join(sans))
    ])
    
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    with open(cert_path, "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    with open(key_path, "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
    print(f"[*] Certificate saved to {cert_path}")

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    generate_self_signed_cert(
        os.path.join(BASE_DIR, "cert.pem"),
        os.path.join(BASE_DIR, "key.pem")
    )
