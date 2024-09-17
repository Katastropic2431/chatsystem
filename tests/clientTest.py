import asyncio
import websockets
import base64
import json
import inquirer
import hashlib
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes

# Helper functions for signing, encryption, and verification
def sign_data(private_key, data, counter):
    message = json.dumps(data, sort_keys=True) + str(counter)
    hashed_message = SHA256.new(message.encode('utf-8'))
    signature = pkcs1_15.new(private_key).sign(hashed_message)
    return base64.b64encode(signature).decode('utf-8')

def get_fingerprint(public_key):
    return hashlib.sha256(public_key.export_key()).hexdigest()

def aes_encrypt(message, key, iv):
    cipher = AES.new(key, AES.MODE_CFB, iv)
    encrypted_message = cipher.encrypt(message.encode("utf-8"))
    return base64.b64encode(encrypted_message).decode("utf-8")

class Client:
    def __init__(self, server_uri, username):
        self.counter = 0
        self.username = username
        self.private_key = RSA.generate(2048)
        self.public_key = self.private_key.publickey()
        self.fingerprint = get_fingerprint(self.public_key)
        self.server_uri = server_uri
        self.client_info = {}

    def create_signed_message(self, data):
        self.counter += 1
        signature = sign_data(self.private_key, data, self.counter)
        return {
            "type": "signed_data",
            "data": data,
            "counter": self.counter,
            "signature": signature
        }

    async def send_hello(self, websocket):
        data = {
            "type": "hello",
            "public_key": self.public_key.export_key().decode('utf-8')
        }
        signed_message = self.create_signed_message(data)
        await websocket.send(json.dumps(signed_message))

    async def request_client_list(self, websocket):
        message = self.create_signed_message({"type": "client_list_request"})
        await websocket.send(json.dumps(message))

    async def listen_for_messages(self, websocket):
        while True:
            try:
                message = await websocket.recv()
                message_json = json.loads(message)
                if message_json["type"] == "client_list":
                    self.cache_client_info(message_json)
                    print(json.dumps(message_json, indent=2))
            except websockets.ConnectionClosed:
                print("Connection closed.")
                break

    def cache_client_info(self, client_list):
        self.client_info = {}
        for server in client_list["servers"]:
            for client in server["clients"]:
                self.client_info[client] = server["address"]
        print(f"Updated client info: {self.client_info}")

    async def read_inputs(self, websocket):
        action_prompt = [
            inquirer.List("action", message="Please select an action", choices=["Request client list", "Send message", "Quit"]),
        ]
        while True:
            action_answer = inquirer.prompt(action_prompt)
            if action_answer["action"] == "Request client list":
                await self.request_client_list(websocket)
            elif action_answer["action"] == "Send message":
                if not self.client_info:
                    print("No cached client list. Request the client list first.")
                    continue
                choices = [f"{fingerprint} - {self.client_info[fingerprint]}" for fingerprint in self.client_info]
                message_prompt = [
                    inquirer.List("recipient", message="Select recipient", choices=choices),
                    inquirer.Text("message", message="Enter your message"),
                ]
                message_answers = inquirer.prompt(message_prompt)
                recipient_fingerprint = message_answers["recipient"].split(" - ")[0]
                destination_server = self.client_info[recipient_fingerprint]
                await self.send_chat_message(websocket, destination_server, message_answers["message"])
            elif action_answer["action"] == "Quit":
                await websocket.close()
                break

    async def send_chat_message(self, websocket, destination_server, message_text):
        data = {
            "type": "public_chat",
            "sender": self.fingerprint,
            "message": message_text
        }
        signed_message = self.create_signed_message(data)
        await websocket.send(json.dumps(signed_message))

    async def client_handler(self):
        async with websockets.connect(self.server_uri) as websocket:
            await self.send_hello(websocket)
            await asyncio.gather(
                self.listen_for_messages(websocket),
                self.read_inputs(websocket)
            )

if __name__ == "__main__":
    prompt = [
        inquirer.Text("username", message="Username"),
        inquirer.Text("address", message="Server address", default="127.0.0.1"),
        inquirer.Text("port", message="Server port", default="8000"),
    ]
    config = inquirer.prompt(prompt)
    server_uri = f"ws://{config['address']}:{config['port']}"
    client = Client(server_uri, config["username"])
    asyncio.run(client.client_handler())
