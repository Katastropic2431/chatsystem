import asyncio
import websockets
import json
import base64
import hashlib
from dataclasses import dataclass, field
from Crypto.Signature import pkcs1_15
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256

# Helper functions for signing and verifying
def sign_data(private_key, data, counter):
    message = json.dumps(data, sort_keys=True) + str(counter)
    hashed_message = SHA256.new(message.encode('utf-8'))
    signature = pkcs1_15.new(private_key).sign(hashed_message)
    return base64.b64encode(signature).decode('utf-8')

def verify_signature(public_key, data, counter, signature):
    message = json.dumps(data, sort_keys=True) + str(counter)
    hashed_message = SHA256.new(message.encode('utf-8'))
    try:
        pkcs1_15.new(public_key).verify(hashed_message, base64.b64decode(signature))
        return True
    except (ValueError, TypeError):
        return False

@dataclass
class RemoteServer:
    server_address: str = ""
    websocket: object = None
    clients: list = field(default_factory=list)

class Server:
    def __init__(self, address="127.0.0.1", port=8000, neighbourhood_server_addresses=[]):
        self.address = address
        self.port = port
        self.uri = f"ws://{address}:{port}"
        self.clients = {}  # Dict of client's public key (fingerprint) to its websocket
        self.client_counters = {}  # Tracks last counter value for each client
        self.neighbourhood_servers = [
            RemoteServer(server_address=addr) for addr in neighbourhood_server_addresses
        ]

    async def handle_client(self, websocket, path):
        public_key = None
        while True:
            try:
                message = await websocket.recv()
                message = json.loads(message)
                if message["type"] == "signed_data":
                    data = message["data"]
                    counter = message["counter"]
                    signature = message["signature"]

                    if data["type"] == "hello":
                        public_key = RSA.import_key(data["public_key"])
                        client_fingerprint = get_fingerprint(public_key)

                        # Verify message and signature
                        if not verify_signature(public_key, data, counter, signature):
                            print("Invalid signature. Disconnecting client.")
                            await websocket.close()
                            return
                        
                        # Check counter for replay attack protection
                        if client_fingerprint in self.client_counters and counter <= self.client_counters[client_fingerprint]:
                            print("Replay attack detected. Disconnecting client.")
                            await websocket.close()
                            return

                        # Add client to the clients dict
                        self.clients[client_fingerprint] = websocket
                        self.client_counters[client_fingerprint] = counter
                        print(f"Client {client_fingerprint} connected")

                        await self.broadcast_client_update()
                    elif data["type"] == "chat":
                        if self.uri in data["destination_servers"]:
                            await self.broadcast_to_all_clients(message)

                elif message["type"] == "client_list_request":
                    await websocket.send(json.dumps(self.prepare_client_list()))
            except websockets.ConnectionClosed:
                print(f"Client disconnected: {public_key}")
                if public_key:
                    client_fingerprint = get_fingerprint(public_key)
                    del self.clients[client_fingerprint]
                    await self.broadcast_client_update()
                break

    def prepare_client_list(self):
        client_list = {
            "type": "client_list",
            "servers": [
                {
                    "address": self.uri,
                    "clients": list(self.clients.keys())
                }
            ]
        }
        return client_list

    async def broadcast_client_update(self):
        client_update = {
            "type": "client_update",
            "clients": list(self.clients.keys())
        }
        for server in self.neighbourhood_servers:
            if server.websocket:
                await server.websocket.send(json.dumps(client_update))

    async def server_handler(self):
        await self.connect_to_neighbourhood()
        async with websockets.serve(self.handle_client, self.address, self.port):
            print(f"Listening on {self.uri}")
            await asyncio.Future()

    async def connect_to_neighbourhood(self):
        for server in self.neighbourhood_servers:
            try:
                websocket = await websockets.connect(server.server_address)
                server.websocket = websocket
                print(f"Connected to neighbor: {server.server_address}")
            except ConnectionRefusedError:
                print(f"Failed to connect to {server.server_address}. Retrying...")

def get_fingerprint(public_key):
    return hashlib.sha256(public_key.export_key()).hexdigest()

if __name__ == "__main__":
    address = input("Server address [127.0.0.1]: ") or "127.0.0.1"
    port = input("Port [8000]: ") or "8000"
    neighbours = input("Neighbour servers (comma separated) [ws://127.0.0.1:8001]: ")
    neighbours_list = neighbours.split(",") if neighbours else ["ws://127.0.0.1:8001"]
    
    server = Server(address, int(port), neighbours_list)
    asyncio.run(server.server_handler())
