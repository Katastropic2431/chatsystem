import asyncio
import websockets
import base64
import hashlib
import json
from json.decoder import JSONDecodeError
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes


# AES Encryption for the message:
def aes_encrypt(message: str, key: bytes, iv: bytes) -> str:
    cipher = AES.new(key, AES.MODE_CFB, iv)
    encrypted_message = cipher.encrypt(message.encode('utf-8'))
    return base64.b64encode(encrypted_message).decode('utf-8')


def aes_decrypt(encrypted_message: str, key: bytes, iv: bytes) -> str:
    # Decode the base64 encoded encrypted message
    encrypted_message_bytes = base64.b64decode(encrypted_message)
    
    # Initialize the cipher with the same key and IV used for encryption
    cipher = AES.new(key, AES.MODE_CFB, iv)
    
    # Decrypt the message
    decrypted_message = cipher.decrypt(encrypted_message_bytes)
    
    # Decode the decrypted message from bytes to string
    return decrypted_message.decode('utf-8')


def rsa_encrypt_aes_key(aes_key: bytes, recipient_public_key: RSA.RsaKey) -> str:
    cipher_rsa = PKCS1_OAEP.new(recipient_public_key)
    encrypted_key = cipher_rsa.encrypt(aes_key)
    return base64.b64encode(encrypted_key).decode('utf-8')


def rsa_decrypt_aes_key(encrypted_aes_key_b64: str, recipient_private_key: RSA.RsaKey) -> bytes:
    # Decode the Base64 encoded encrypted AES key
    encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)
    
    # Initialize the cipher using the RSA private key and PKCS1_OAEP
    cipher_rsa = PKCS1_OAEP.new(recipient_private_key)
    
    # Decrypt the AES key
    aes_key = cipher_rsa.decrypt(encrypted_aes_key)
    
    return aes_key


def get_fingerprint(public_key: RSA.RsaKey) -> str:
    return hashlib.sha256(public_key.export_key()).hexdigest()


class Client:
    def __init__(self, server_uri):
        # Generate or load RSA keys
        self.private_key = RSA.generate(2048)
        self.public_key = self.private_key.publickey()
        self.fingerprint = get_fingerprint(self.public_key)
        self.server_uri = server_uri


    async def send_hello(self, websocket):
        message = {
            "data": {
                "type": "hello",
                "public_key": self.public_key.export_key().decode('utf-8')
            }
        }
        await websocket.send(json.dumps(message))


    async def send_chat_message(
        self,
        websocket, # websocket to the connected server
        destination_servers: list[str],
        recipient_public_keys: list[RSA.RsaKey],
        message_text: str
    ):
        """Chat format
        {
            "data": {
                "type": "chat",
                "destination_servers": [
                    "<Address of each recipient's destination server>",
                ],
                "iv": "<Base64 encoded AES initialisation vector>",
                "symm_keys": [
                    "<Base64 encoded AES key, encrypted with each recipient's public RSA key>",
                ],
                "chat": "<Base64 encoded AES encrypted segment>"
            }
        }

        {
            "chat": {
                "participants": [
                    "<Base64 encoded list of fingerprints of participants, starting with sender>",
                ],
                "message": "<Plaintext message>"
            }
        }
        """
        
        # Generate AES key and IV
        aes_key = get_random_bytes(32)
        iv = get_random_bytes(16)
        
        recipient_fingerprints = [get_fingerprint(key) for key in recipient_public_keys]
        chat_message = {
            "participants": recipient_fingerprints,
            "message": message_text
        }
        chat_message_json = json.dumps(chat_message)
        encrypted_chat = aes_encrypt(chat_message_json, aes_key, iv)
        encrypted_keys = [rsa_encrypt_aes_key(aes_key, pub_key) for pub_key in recipient_public_keys]

        data = {
            "type": "chat",
            "destination_servers": destination_servers,
            "iv": base64.b64encode(iv).decode('utf-8'),
            "symm_keys": encrypted_keys,
            "chat": encrypted_chat
        }

        full_message = {
            "data": data
        }

        await websocket.send(json.dumps(full_message))


    async def request_client_list(self, websocket):
        message = {
            "type": "client_list_request"
        }
        await websocket.send(json.dumps(message))


    async def listen_for_chat_message(self, websocket):
        message = await websocket.recv()
        chat_message = json.loads(message)
        iv = base64.b64decode(chat_message['data']['iv'])
        # print('symm_key:', chat_message['data']['symm_keys'])
        # print('symm_key type:', type(chat_message['data']['symm_keys']))
        for symm_key in chat_message['data']['symm_keys']:            
            aes_key = rsa_decrypt_aes_key(symm_key, self.private_key)
            encrypted_chat = chat_message['data']['chat']
            
            try:
                decrypted_chat = aes_decrypt(encrypted_chat, aes_key, iv)
                decrypted_json = json.loads(decrypted_chat)
                return decrypted_json['message']
            except JSONDecodeError as e:
                # Handle the JSON decoding error
                pass
            except Exception as e:
                # Handle any other exceptions
                print(f"An unexpected error occurred: {e}")
        
        return None


#     async def client_handler(self):
#         async with websockets.connect(self.server_uri) as websocket:
#             await self.send_hello(websocket)
#             await self.request_client_list(websocket)
#             await asyncio.gather(
#                 listen_for_messages(websocket),
#                 request_client_list(websocket),
#                 send_chat_message(websocket, "server_address", "Hello World!")
#             )
