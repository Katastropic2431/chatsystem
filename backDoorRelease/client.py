import asyncio
import websockets
import base64
import hashlib
import requests # for making HTTP requests
import json
import os
import inquirer
from pathlib import Path  # add this import to handle file paths
from concurrent.futures import ThreadPoolExecutor
from json.decoder import JSONDecodeError
from Crypto.PublicKey import RSA
from Crypto.Signature import pss
from Crypto.Hash import SHA256
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes

# AES Encryption for the message:
def aes_encrypt(message: str, key: bytes, iv: bytes) -> str:
    cipher = AES.new(key, AES.MODE_GCM, iv)
    encrypted_message = cipher.encrypt(message.encode("utf-8"))
    return base64.b64encode(encrypted_message).decode("utf-8")


def aes_decrypt(encrypted_message: str, key: bytes, iv: bytes) -> str:
    # Decode the base64 encoded encrypted message
    encrypted_message_bytes = base64.b64decode(encrypted_message)
    
    # Initialize the cipher with the same key and IV used for encryption
    cipher = AES.new(key, AES.MODE_GCM, iv)
    
    # Decrypt the message
    decrypted_message = cipher.decrypt(encrypted_message_bytes)
    
    # Decode the decrypted message from bytes to string
    return decrypted_message.decode("utf-8")


def rsa_encrypt_aes_key(aes_key: bytes, recipient_public_key: RSA.RsaKey) -> str:
    cipher_rsa = PKCS1_OAEP.new(key=recipient_public_key, hashAlgo=SHA256.new())
    encrypted_key = cipher_rsa.encrypt(aes_key)
    return base64.b64encode(encrypted_key).decode("utf-8")


def rsa_decrypt_aes_key(encrypted_aes_key_b64: str, recipient_private_key: RSA.RsaKey) -> bytes:
    # Decode the Base64 encoded encrypted AES key
    encrypted_aes_key = base64.b64decode(encrypted_aes_key_b64)
    
    # Initialize the cipher using the RSA private key and PKCS1_OAEP
    cipher_rsa = PKCS1_OAEP.new(recipient_private_key, hashAlgo=SHA256.new())
    
    # Decrypt the AES key
    aes_key = cipher_rsa.decrypt(encrypted_aes_key)
    
    return aes_key

# Sign a message using PSS with SHA-256
def sign_message(data: dict, counter: int, private_key) -> str:
    data = json.dumps(data) + str(counter)
    h = SHA256.new(data.encode('utf-8'))
    signer = pss.new(private_key, salt_bytes=32)
    signature = signer.sign(h)
    return base64.b64encode(signature).decode('utf-8')

def return_random_bytes(byte_length) -> bytes:
    try:
        return get_random_bytes(byte_length)
    except Exception:
        # Use backup method to generate random bytes
        bytes = int(byte_length)
        return bytes.to_bytes((bytes.bit_length() + 7) // 8, byteorder='big').ljust(32, b'\0')


# Verify a signature using PSS with SHA-256
def verify_signature(data: str, counter: int, signature: str, public_key) -> bool:
    data = json.dumps(data) + str(counter)
    h = SHA256.new(data.encode('utf-8'))
    verifier = pss.new(public_key, salt_bytes=32)
    try:
        verifier.verify(h, base64.b64decode(signature))
        return True
    except (ValueError, TypeError):
        return False

def get_fingerprint(public_key: RSA.RsaKey) -> str:
    return hashlib.sha256(public_key.export_key()).hexdigest()


class Client:
    def __init__(self, config):
        # Generate or load RSA keys
        self.server_uri = f"ws://{config['address']}:{config['port']}"
        self.private_key = RSA.generate(bits=2048, e=65537)
        self.public_key = self.private_key.publickey()
        self.fingerprint = get_fingerprint(self.public_key)
        self.flask_server = config['flask_server']
        self.address = config['address']
        self.client_info = {} # mapping each client's public key to its server
        self.fingerprint_to_public_key = {} # mapping each client's fingerprint to its public key
        self.fingerprint_to_public_key[self.fingerprint] = self.public_key.export_key().decode("utf-8") # Add the client's own public key
        self.fingerprint_to_counter = {}
        self.counter = 0


    async def send_hello(self, websocket):
        data = {
            "type": "hello",
            "public_key": self.public_key.export_key().decode("utf-8")
        }
        signiture = sign_message(data, self.counter, self.private_key)
        message = {
            "type": "signed_data",
            "data": data,
            "counter": self.counter,
            "signature": signiture
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
        self.counter += 1
        # Generate AES key and IV
        aes_key = return_random_bytes("32")
        iv = return_random_bytes(16)
        
        # Base64 encoded list of fingerprints of participants, starting with sender
        recipient_fingerprints = [self.fingerprint] + [get_fingerprint(key) for key in recipient_public_keys]
        # base 64 encode the fingerprints
        recipient_fingerprints = [base64.b64encode(fingerprint.encode('utf-8')).decode('utf-8') for fingerprint in recipient_fingerprints]
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

        signiture = sign_message(data, self.counter, self.private_key)

        full_message = {
            "type": "signed_data",
            "data": data,
            "counter": self.counter,
            "signature": signiture
        }

        await websocket.send(json.dumps(full_message))

    async def send_public_message(self, websocket, message_text):
        self.counter += 1
        data = {
            "type": "public_chat",
            "sender": base64.b64encode(self.fingerprint.encode('utf-8')).decode('utf-8'),
            "message": message_text
        }
        signiture = sign_message(data, self.counter, self.private_key)
        full_message = {
            "type": "signed_data",
            "data": data,
            "counter": self.counter,
            "signature": signiture
        }
        await websocket.send(json.dumps(full_message))

    async def request_client_list(self, websocket):
        message = {
            "type": "client_list_request"
        }
        await websocket.send(json.dumps(message))

    def check_for_relay_attack(self, sender, counter) -> bool:
        if sender not in self.fingerprint_to_counter:
            # add the sender to the list of known clients
            self.fingerprint_to_counter[sender] = counter
            return False
        elif counter <= self.fingerprint_to_counter[sender]:
            print("Relay attack detected")
            return True
        self.fingerprint_to_counter[sender] = counter
        return False

    def extract_chat_message(self, chat_message) -> tuple:
        """Function that extracts a direct chat message"""
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
                # decode the sender fingerprint
                sender = base64.b64decode(sender).decode("utf-8")
                # Check for relay attack
                if self.check_for_relay_attack(sender, chat_message["counter"]):
                    return None, None
                # Verify the signature of the chat message
                if sender not in self.fingerprint_to_public_key:
                    print("Unknown sender cannot verify signature please ensure you have the most recent client list")
                    return None, None
                if not verify_signature(chat_message["data"], chat_message["counter"], chat_message["signature"], RSA.import_key(self.fingerprint_to_public_key[sender])):
                    print("Signature verification failed")
                    return None, None
                return message, sender
            except JSONDecodeError as e:
                print("Unknown message format")
            except Exception as e:
                # Handle any other exceptions
                print(f"An unexpected error occurred: {e}")
        
        return None, None

    def extract_public_chat(self, public_chat) -> tuple:
        """Function that extracts a public chat message"""
        try:
            message = public_chat["data"]["message"]
            sender = public_chat["data"]["sender"]
            # decode the sender fingerprint
            sender = base64.b64decode(sender).decode("utf-8")
            # Check for relay attack
            if self.check_for_relay_attack(sender, public_chat["counter"]):
                return None, None
            return message, sender
        except JSONDecodeError as e:
            print("Unknown message format")
        except Exception as e:
            # Handle any other exceptions
            print(f"An unexpected error occurred: {e}")


    def cache_client_info(self, client_list):
        self.finger_print_to_public_key = {}
        for server in client_list["servers"]:
            for client in server["clients"]:
                self.client_info[client] = server["address"]
                self.fingerprint_to_public_key[get_fingerprint(RSA.import_key(client))] = client
    
    async def listen_for_messages(self, websocket):
        try:
            while True:
                message = await websocket.recv()
                message_json = json.loads(message)

                if message_json["type"] == "client_list":
                    self.cache_client_info(message_json)   
                    print(json.dumps(message_json, indent=2))
                elif message_json["type"] == "signed_data":
                    if message_json["data"]["type"] == "chat":
                        text, sender = self.extract_chat_message(message_json)
                    elif message_json["data"]["type"] == "public_chat":
                        text, sender = self.extract_public_chat(message_json)
                    else:
                        print("Unknown message type")
                        continue
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

    async def upload_file(self, websocket):
        """Uploads a file to the Flask server and shares the download link."""
        loop = asyncio.get_event_loop()

        file_prompt = [
            inquirer.Text("file_path", message="Enter the full path of the file to upload")
        ]
        file_answer = await self.ask_user_async(loop, file_prompt)

        file_path = file_answer['file_path']
        if not Path(file_path).is_file():
            print(f"File not found: {file_path}")
            return
        
        # Upload file to Flask server
        files = {'file': open(file_path, 'rb')}
        try:
            response = requests.post(f'http://{self.address}:{self.flask_server}/api/upload', files=files)
            response_data = response.json()
            if response.status_code == 200:
                file_url = response_data.get('file_url')
                print(f"File uploaded successfully. URL: {file_url}")

                # Send the file URL as a chat message
                await self.send_public_message(websocket, f"File shared: {file_url}")
            else:
                print(f"Failed to upload file: {response_data.get('error')}")
        except Exception as e:
            print(f"Error uploading file: {e}")

    async def download_file(self):
        """Downloads a file from the given URL and saves it locally."""
        file_url = input("Enter the URL of the file to download: ")

        if not file_url:
            print("File URL not provided or invalid input.")
            return

        try:
            response = requests.get(file_url)
            if response.status_code == 200:
                # Ensure the download directory exists
                download_dir = "/tmp/downloads"
                os.makedirs(download_dir, exist_ok=True)

                # Get file name from URL and save the file
                file_name = file_url.split("/")[-1]
                file_path = os.path.join(download_dir, file_name)
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                print(f"File downloaded successfully and saved at: {file_path}")
            else:
                print(f"Failed to download file: {response.status_code}")
        except Exception as e:
            print(f"Error downloading file: {e}")
    
    async def read_inputs(self, websocket):
        loop = asyncio.get_event_loop()
        action_prompt = [
            inquirer.List("action",
                message="Please select an action",
                choices=["Request client list", "Send message", "Send public message", "Upload file", "Download file", "Quit"],
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
                        continue
                    
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

                elif action_answer["action"] == "Send public message":
                    message_prompt = [
                        inquirer.Text("message", message="Please input text message"),
                    ]
                    message_answers = await self.ask_user_async(loop, message_prompt)
                    await self.send_public_message(websocket, message_answers["message"])
                elif action_answer["action"] == "Upload file":
                    await self.upload_file(websocket)
                elif action_answer["action"] == "Download file":
                    await self.download_file()
                elif action_answer["action"] == "Quit":
                    print("Closing connection...")
                    await websocket.close()
                    break

                # Wait for some time so that the user can see the response
                await asyncio.sleep(2)

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
        inquirer.Text("port", message="Server port", default="8000"),
        inquirer.Text("flask_server", message="Enter the port of the Flask server: ", default="5000")
    ]
    
    config = inquirer.prompt(prompt)
    server_uri = f"ws://{config['address']}:{config['port']}"
    client = Client(config)
    asyncio.run(client.client_handler())