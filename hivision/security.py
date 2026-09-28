import hmac
import hashlib
import json
import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

def verify_signature(data: dict, app_id: str, timestamp: str, signature: str, secret_key: str) -> bool:
    """
    验证 HMAC 签名
    """
    sorted_keys = sorted(data.keys())
    base_string = "&".join([f"{key}={data[key]}" for key in sorted_keys])
    base_string += f"&app_id={app_id}&timestamp={timestamp}&key={secret_key}"
    
    expected_signature = hmac.new(
        secret_key.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

def decrypt_data(encrypted_data: str, secret_key: str) -> dict:
    """
    AES-ECB 解密 (与 CryptoJS 默认 ECB 模式一致)
    """
    key = secret_key.encode('utf-8')
    # 如果 key 长度不是 16, 24, 或 32 字节，需要处理
    if len(key) not in [16, 24, 32]:
        # 简单截断或填充，实际应根据约定处理
        key = key[:32].ljust(32, b'\0')
        
    cipher = AES.new(key, AES.MODE_ECB)
    decrypted = unpad(cipher.decrypt(base64.b64decode(encrypted_data)), AES.block_size)
    return json.loads(decrypted.decode('utf-8'))
