import asyncio
import websockets
import base64
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
import json

class Client:
    def __init__(self, server_uri):
        # Generate RSA key pair
        self.private_key = RSA.generate(2048)
        self.public_key = self.private_key.publickey()
        self.aes_key = None
        self.iv = None
        self.server_uri = server_uri

    def rsa_encrypt(self, data, recipient_public_key):
        cipher_rsa = PKCS1_OAEP.new(recipient_public_key)
        encrypted_data = cipher_rsa.encrypt(data)
        return base64.b64encode(encrypted_data).decode('utf-8')

    def rsa_decrypt(self, encrypted_data):
        cipher_rsa = PKCS1_OAEP.new(self.private_key)
        decrypted_data = cipher_rsa.decrypt(base64.b64decode(encrypted_data))
        return decrypted_data

    def aes_encrypt(self, message):
        # Ensure IV is generated before encryption
        self.iv = get_random_bytes(12)  # GCM mode typically uses a 12-byte IV
        cipher = AES.new(self.aes_key, AES.MODE_GCM, self.iv)
        ciphertext, tag = cipher.encrypt_and_digest(message.encode('utf-8'))
        return base64.b64encode(ciphertext).decode('utf-8')


    def aes_decrypt(self, ciphertext):
        cipher = AES.new(self.aes_key, AES.MODE_GCM, self.iv)
        plaintext = cipher.decrypt(base64.b64decode(ciphertext))
        return plaintext.decode('utf-8')

    async def send_message(self, websocket, message):
        encrypted_message = self.aes_encrypt(message)
        data = {
            'type': 'message',
            'message': encrypted_message,
            'iv': base64.b64encode(self.iv).decode('utf-8')
        }
        await websocket.send(json.dumps(data))

    async def receive_message(self, websocket):
        async for message in websocket:
            message_data = json.loads(message)
            if message_data['type'] == 'message':
                decrypted_message = self.aes_decrypt(message_data['message'])
                print(f"Decrypted message: {decrypted_message}")

    async def client_handler(self):
        async with websockets.connect(self.server_uri) as websocket:
            # Send public key to server (or other clients)
            await websocket.send(json.dumps({
                'type': 'public_key',
                'public_key': self.public_key.export_key().decode('utf-8')
            }))

            # Handle messaging
            await asyncio.gather(
                self.receive_message(websocket),
                self.user_input(websocket)
            )

    async def user_input(self, websocket):
        while True:
            message = input("Enter message: ")
            self.iv = get_random_bytes(12)
            await self.send_message(websocket, message)

if __name__ == '__main__':
    server_uri = "ws://localhost:6789"
    client = Client(server_uri)
    asyncio.run(client.client_handler())
