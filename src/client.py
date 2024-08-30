import asyncio
import websockets
import json
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
import base64


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


class Client:
    def __init__(self, server_uri):
        # Generate or load RSA keys
        self.private_key = RSA.generate(2048)
        self.public_key = self.private_key.publickey().export_key().decode()
        self.server_uri = server_uri


    def create_chat_message(
        self, 
        recipients_fingerprints, 
        message
    ):
        chat = {
            "participants": recipients_fingerprints,
            "message": message
        }
        return chat


    async def send_hello(self, websocket):
        message = {
            "data": {
                "type": "hello",
                "public_key": self.public_key
            }
        }
        await websocket.send(json.dumps(message))
        # print('Sent hello message with public key.')


    async def send_chat_message(
        self,
        websocket, # websocket to the connected server
        destination_servers,
        recipient_fingerprints,
        message_text
    ):
        # Generate AES key and IV
        aes_key = get_random_bytes(32)
        iv = get_random_bytes(16)
        
        chat_message = self.create_chat_message(
            recipient_fingerprints, 
            message_text
        )
        chat_message_json = json.dumps(chat_message)
        encrypted_chat = aes_encrypt(chat_message_json, aes_key, iv)

        # public_keys = [recipient_public_key1, recipient_public_key2]

        # encrypted_keys = [rsa_encrypt_aes_key(aes_key, pub_key) for pub_key in public_keys]

        data = {
            "type": "chat",
            "destination_servers": destination_servers,
            "iv": base64.b64encode(iv).decode('utf-8'), # needs to be encrypted with recipient's public key
            "symm_keys": base64.b64encode(aes_key).decode('utf-8'), # needs to be encrypted with recipient's public key
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
        aes_key = base64.b64decode(chat_message['data']['symm_keys'])
        
        encrypted_chat = chat_message['data']['chat']
        decrypted_chat = aes_decrypt(encrypted_chat, aes_key, iv)
        decrypted_json = json.loads(decrypted_chat)
        return decrypted_json['message']


#     async def client_handler(self):
#         async with websockets.connect(self.server_uri) as websocket:
#             await self.send_hello(websocket)
#             await self.request_client_list(websocket)
#             await asyncio.gather(
#                 listen_for_messages(websocket),
#                 request_client_list(websocket),
#                 send_chat_message(websocket, "server_address", "Hello World!")
#             )

# if __name__ == "__main__":
#     asyncio.run(client_handler())
