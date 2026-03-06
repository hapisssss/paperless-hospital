from Crypto.Cipher import AES
from base64 import urlsafe_b64encode, urlsafe_b64decode
from dotenv import load_dotenv
import base64
import json
import string
import os

# Load environment variables from .env file
load_dotenv()

# Ambil AES key dari environment variable atau nilai default jika tidak ada
AES_KEY = os.getenv('AES_KEY', 'G3GYuVRBwQHzPuP6UvzEaQ==')

def encryptUrl(param: str, key: str = AES_KEY) -> str:
    # Ensure the parameter length is a multiple of 16 bytes
    try:
        while len(param) % 16 != 0:
            param += ' '

        # Create AES cipher object with ECB mode
        cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)

        # Encrypt the parameter
        encrypted_param = cipher.encrypt(param.encode('utf-8'))

        # Encode the encrypted data to base64 for URL-safe representation
        encoded_param = urlsafe_b64encode(encrypted_param).decode('utf-8')

        return encoded_param
    except(ValueError, KeyError) as e:
        print(f"Encryption error: {e}")
        return None

def decryptUrl(encrypted_param: str, key: str = AES_KEY) -> str:
    try:
        # Decode the encrypted parameter from base64
        encrypted_param_bytes = urlsafe_b64decode(encrypted_param)

        # Create AES cipher object with ECB mode
        cipher = AES.new(key.encode('utf-8'), AES.MODE_ECB)

        # Decrypt the parameter
        decrypted_param = cipher.decrypt(encrypted_param_bytes).decode('utf-8')

        return decrypted_param
    except(ValueError, KeyError) as e:
        print(f"Encryption error: {e}")
        return None

# # Example usage:

# # Encrypt parameter
# parameter = "123"
# encrypted_parameter = encrypt(parameter)
# print("Encrypted parameter:", encrypted_parameter)

# # Decrypt parameter
# decrypted_parameter = decrypt(encrypted_parameter)
# print("Decrypted parameter:", decrypted_parameter)


# Generate a simple substitution cipher map
def generate_cipher_map(shift):
    original = string.ascii_letters + string.digits
    shifted = original[shift:] + original[:shift]
    return str.maketrans(original, shifted), str.maketrans(shifted, original)

# Encrypt function
def encryptKey(text, shift=5):
    cipher_map, _ = generate_cipher_map(shift)
    return text.translate(cipher_map)

# Decrypt function
def decryptKey(ciphertext, shift=5):
    _, decipher_map = generate_cipher_map(shift)
    return ciphertext.translate(decipher_map)

def decode_header(encoded_str: str):
    try:
        decoded_bytes = base64.b64decode(encoded_str) 
        decoded_str = decoded_bytes.decode() 
        return json.loads(decoded_str) 
    except Exception:
        return {}