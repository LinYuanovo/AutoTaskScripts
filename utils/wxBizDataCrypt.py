import base64
import json
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

class WXBizDataCryptUtil:
    """
    微信小程序加解密工具
    """
    def __init__(self, sessionKey):
        self.sessionKey = sessionKey

    def encrypt(self, data, iv=None):
        """
        data: dict或str，若为dict自动转为json字符串
        iv: base64字符串，若为None自动生成
        返回: (加密数据base64, iv base64)
        """
        if isinstance(data, dict):
            data = json.dumps(data, separators=(',', ':'))
        if iv is None:
            iv_bytes = get_random_bytes(16)
            iv = base64.b64encode(iv_bytes).decode('utf-8')
        else:
            iv_bytes = base64.b64decode(iv)
        sessionKey = base64.b64decode(self.sessionKey)
        cipher = AES.new(sessionKey, AES.MODE_CBC, iv_bytes)
        padded = self._pad(data.encode('utf-8'))
        encrypted = cipher.encrypt(padded)
        encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')
        return encrypted_b64, iv

    def decrypt(self, encryptedData, iv):
        """
        encryptedData: base64字符串
        iv: base64字符串
        返回: dict或str
        """
        sessionKey = base64.b64decode(self.sessionKey)
        encryptedData = base64.b64decode(encryptedData)
        iv = base64.b64decode(iv)
        cipher = AES.new(sessionKey, AES.MODE_CBC, iv)
        decrypted = self._unpad(cipher.decrypt(encryptedData))
        try:
            return json.loads(decrypted)
        except Exception:
            return decrypted.decode('utf-8')

    def _pad(self, s):
        pad_len = 16 - len(s) % 16
        return s + bytes([pad_len] * pad_len)

    def _unpad(self, s):
        return s[:-s[-1]]
