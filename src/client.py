import asyncio
import websockets
import base64
import hashlib
import json
import sys
import inquirer
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from json.decoder import JSONDecodeError
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes


# AES Encryption for the message:
def aes_encrypt(message: str, key: bytes, iv: bytes) -> str:
    cipher = AES.new(key, AES.MODE_CFB, iv)
    encrypted_message = cipher.encrypt(message.encode("utf-8"))
    return base64.b64encode(encrypted_message).decode("utf-8")


def aes_decrypt(encrypted_message: str, key: bytes, iv: bytes) -> str:
    # Decode the base64 encoded encrypted message
    encrypted_message_bytes = base64.b64decode(encrypted_message)
    
    # Initialize the cipher with the same key and IV used for encryption
    cipher = AES.new(key, AES.MODE_CFB, iv)
    
    # Decrypt the message
    decrypted_message = cipher.decrypt(encrypted_message_bytes)
    
    # Decode the decrypted message from bytes to string
    return decrypted_message.decode("utf-8")


def rsa_encrypt_aes_key(aes_key: bytes, recipient_public_key: RSA.RsaKey) -> str:
    cipher_rsa = PKCS1_OAEP.new(recipient_public_key)
    encrypted_key = cipher_rsa.encrypt(aes_key)
    return base64.b64encode(encrypted_key).decode("utf-8")


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
        self.client_info = {} # mapping each client's public key to its server


    async def send_hello(self, websocket):
        message = {
            "data": {
                "type": "hello",
                "public_key": self.public_key.export_key().decode("utf-8")
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
                    "<Address of each recipient"s destination server>",
                ],
                "iv": "<Base64 encoded AES initialisation vector>",
                "symm_keys": [
                    "<Base64 encoded AES key, encrypted with each recipient"s public RSA key>",
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
        
        # Base64 encoded list of fingerprints of participants, starting with sender
        recipient_fingerprints = [self.fingerprint] + [get_fingerprint(key) for key in recipient_public_keys]
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
            "iv": base64.b64encode(iv).decode("utf-8"),
            "symm_keys": encrypted_keys,
            "chat": encrypted_chat
        }

        full_message = {
            "type": "signed_data",
            "data": data
        }

        await websocket.send(json.dumps(full_message))


    async def request_client_list(self, websocket):
        message = {
            "type": "client_list_request"
        }
        await websocket.send(json.dumps(message))


    def extract_chat_message(self, chat_message):
        iv = base64.b64decode(chat_message["data"]["iv"])
        encrypted_chat = chat_message["data"]["chat"]

        for symm_key in chat_message["data"]["symm_keys"]:            
            try:
                aes_key = rsa_decrypt_aes_key(symm_key, self.private_key)
            except ValueError:
                # The aes key is not correct
                continue
            
            try:
                decrypted_chat = aes_decrypt(encrypted_chat, aes_key, iv)
                decrypted_json = json.loads(decrypted_chat)
                message = decrypted_json["message"]
                sender = decrypted_json["participants"][0]
                return message, sender
            except JSONDecodeError as e:
                print("Unknown message format")
            except Exception as e:
                # Handle any other exceptions
                print(f"An unexpected error occurred: {e}")
        
        return None, None


    def cache_client_info(self, client_list):
        for server in client_list["servers"]:
            for client in server["clients"]:
                self.client_info[client] = server["address"]

    
    async def listen_for_messages(self, websocket):
        try:
            while True:
                message = await websocket.recv()
                message_json = json.loads(message)

                if message_json["type"] == "client_list":
                    self.cache_client_info(message_json)   
                    print(json.dumps(message_json, indent=2))
                elif message_json["type"] == "signed_data":
                    text, sender = self.extract_chat_message(message_json)
                    if text is not None:
                        print(f"Sender: {sender}")
                        print(f"Text: {text}")

        except websockets.ConnectionClosed:
            print(f"Connection closed.")
        except JSONDecodeError as e:
            print("Received unknown message format.")

   
    def ask_user(self, prompt):
        return inquirer.prompt(prompt) 
    

    # Asynchronous wrapper for inquirer
    async def ask_user_async(self, loop, prompt):
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, self.ask_user, prompt)
            return result

    
    async def read_inputs(self, websocket):
        loop = asyncio.get_event_loop()
        action_prompt = [
            inquirer.List("action",
                message="Please select an action",
                choices=["Request client list", "Send message", "Quit"],
            ),
        ]
        
        try:
            while True:
                # Make user input asychronous to avoid blocking the whole process
                action_answer = await self.ask_user_async(loop, action_prompt)
                
                if action_answer["action"] == "Request client list":
                    await self.request_client_list(websocket)
                elif action_answer["action"] == "Send message":
                    if len(self.client_info) == 0:
                        print("Currently no information about other clients. Please request client list first.")
                    
                    choices = [key for key in self.client_info]
                    message_prompt = [
                        inquirer.Checkbox("public_keys",
                            message="Please select recipients' public keys (press \"space\" to select)",
                            choices=choices,
                        ),
                        inquirer.Text("message", message="Please input text message"),
                    ]
                    message_answers = await self.ask_user_async(loop, message_prompt)

                    # Prepare for sending a message
                    public_keys = [RSA.import_key(key_pem) for key_pem in message_answers["public_keys"]]
                    destination_servers = [
                        self.client_info[key] for key in message_answers["public_keys"]
                    ]
                    await self.send_chat_message(
                        websocket,
                        destination_servers,
                        public_keys,
                        message_answers["message"]
                    )
                elif action_answer["action"] == "Quit":
                    print("Closing connection...")
                    await websocket.close()
                    break

                # Wait for some time so that the user can see the response
                await asyncio.sleep(1)

        except websockets.ConnectionClosed:
            print(f"Connection closed.")


    async def client_handler(self):
        async with websockets.connect(self.server_uri) as websocket:
            await self.send_hello(websocket)
            await asyncio.gather(
                self.listen_for_messages(websocket),
                self.read_inputs(websocket)
            )


if __name__ == '__main__':
    prompt = [
        inquirer.Text("address", message="Server address", default="127.0.0.1"),
        inquirer.Text("port", message="Server port", default="8000")
    ]
    config = inquirer.prompt(prompt)
    server_uri = f"ws://{config['address']}:{config['port']}"
    client = Client(server_uri)
    asyncio.run(client.client_handler())