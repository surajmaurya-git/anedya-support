import hashlib
import time

token_id=""
token=""

# Function to generate Anedya signature
def generate_anedya_signature(token: str, timestamp: int, request_body=None):
    if request_body is None:
        body_hash = hashlib.sha256(b"").digest()
    else:
        body_hash = hashlib.sha256(request_body.encode()).digest()

    timestamp_bytes = timestamp.to_bytes(8, "big", signed=False)
    sig_version_bytes = b"v1"
    token_bytes = token.encode()

    combined = body_hash + timestamp_bytes + sig_version_bytes + token_bytes
    return hashlib.sha256(combined).hexdigest()

timestamp = int(time.time())
token=input("Token : ")
print("Time  :", timestamp)
print("Signature :", generate_anedya_signature(token, timestamp=timestamp))