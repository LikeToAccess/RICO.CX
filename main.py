import datetime
import ipaddress
import os
import ssl
from typing import Optional, Any
from dotenv import load_dotenv

try:
	import gevent.monkey  # type: ignore[import-untyped]
	gevent.monkey.patch_all()
except ImportError:
	pass

from backend.app import create_app, socketio

load_dotenv()


def ensure_self_signed_cert(cert_file: str = "cert.pem", key_file: str = "key.pem") -> Optional[ssl.SSLContext]:
	"""
	Generate a self-signed SSL certificate if it does not already exist and return an SSLContext.
	"""
	if not (os.path.exists(cert_file) and os.path.exists(key_file)):
		try:
			from cryptography import x509
			from cryptography.x509.oid import NameOID
			from cryptography.hazmat.primitives import hashes, serialization
			from cryptography.hazmat.primitives.asymmetric import rsa

			key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
			subject = issuer = x509.Name([
				x509.NameAttribute(NameOID.COMMON_NAME, "rico.cx"),
			])
			cert = x509.CertificateBuilder().subject_name(
				subject
			).issuer_name(
				issuer
			).public_key(
				key.public_key()
			).serial_number(
				x509.random_serial_number()
			).not_valid_before(
				datetime.datetime.now(datetime.timezone.utc)
			).not_valid_after(
				datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650)
			).add_extension(
				x509.SubjectAlternativeName([
					x509.DNSName("localhost"),
					x509.DNSName("rico.cx"),
					x509.IPAddress(ipaddress.ip_address("127.0.0.1"))
				]),
				critical=False,
			).sign(key, hashes.SHA256())

			with open(key_file, "wb") as f:
				f.write(key.private_bytes(
					encoding=serialization.Encoding.PEM,
					format=serialization.PrivateFormat.TraditionalOpenSSL,
					encryption_algorithm=serialization.NoEncryption()
				))

			with open(cert_file, "wb") as f:
				f.write(cert.public_bytes(serialization.Encoding.PEM))
		except Exception as exc:  # pylint: disable=broad-exception-caught
			print(f"Warning: Failed to generate SSL cert: {exc}")
			return None

	ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
	ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)
	return ctx


if __name__ == '__main__':
	port = int(os.environ.get("PORT", 5000))
	debug = os.environ.get("DEBUG_MODE", "False").lower() == "true"
	use_ssl = os.environ.get("USE_SSL", "False").lower() == "true"

	ssl_context: Optional[Any] = None
	if use_ssl:
		ssl_context = ensure_self_signed_cert()

	app = create_app()
	socketio.run(
		app,
		host='0.0.0.0',
		port=port,
		debug=debug,
		ssl_context=ssl_context
	)
