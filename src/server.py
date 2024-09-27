import asyncio
import base64
import websockets
import hashlib
import json
import inquirer
from Crypto.Hash import SHA256
from Crypto.Signature import pss
from Crypto.PublicKey import RSA
from dataclasses import dataclass, field
import subprocess

@dataclass
class RemoteServer:
    server_address: str = ""
    websocket: object = None
    public_key: str = ""
    counter: int = 0
    clients: list = field(default_factory=list)

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
    
# Sign a message using PSS with SHA-256
def sign_message(data: dict, counter: int, private_key) -> str:
    data = json.dumps(data) + str(counter)
    h = SHA256.new(data.encode('utf-8'))
    signer = pss.new(private_key, salt_bytes=32)
    signature = signer.sign(h)
    return base64.b64encode(signature).decode('utf-8')

def get_fingerprint(public_key: RSA.RsaKey) -> str:
    return hashlib.sha256(public_key.export_key()).hexdigest()


class Server:
    def __init__(
        self, 
        address="127.0.0.1", 
        port=8000, 
        remote_servers=[],
    ):
        # Dict of client's public key to its websocket connection
        self.clients = {}
        # Dict of client's public key to its counter
        self.address = address
        self.port = port
        self.counter = 0
        self.uri = f"ws://{address}:{port}"
        self.neighbourhood_servers = remote_servers
        # Generate RSA Public key and print it so that it can be shared with other servers
        # Printed in base64 encoding so that it can be copied and pasted easily
        self.private_key = RSA.generate(bits=2048, e=65537)
        self.public_key = self.private_key.publickey()
        public_key_pem = self.public_key.export_key()
        public_key_base64 = base64.b64encode(public_key_pem).decode('utf-8')
        print(f"Public key (Base64 encoded):\n{public_key_base64}")

    async def handle_client(self, websocket):
        public_key = None
        while True:
            try:
                message = await websocket.recv()
                message = json.loads(message)

                if message["type"] == "signed_data":
                    if message["data"]["type"] == "hello":
                        if not verify_signature(message["data"], message["counter"],message["signature"], RSA.import_key(message["data"]["public_key"])):
                            print("Signature verification failed")
                            return
                        print(f"Received hello message from client")
                        public_key = message["data"]["public_key"]
                        self.clients[public_key] = websocket
                        await self.broadcast_client_update()

                    elif message["data"]["type"] == "chat":
                        from_server = False
                        # if message came from server, broadcast it to all clients if the server is in the destination list
                        for server in self.neighbourhood_servers:
                            if server.websocket == websocket:
                                from_server = True
                                if self.uri in message["data"]["destination_servers"]:
                                    await self.broadcast_to_all_clients(message)

                        # If the message came from a client, forward it to the destination servers
                        if not from_server:
                            if self.uri in message["data"]["destination_servers"]:
                                await self.broadcast_to_all_clients(message)
                            await self.forward_message_to_server(message)

                    elif message["data"]["type"] == "public_chat":
                        # if the message came from a server, broadcast it to all clients
                        from_server = False
                        for server in self.neighbourhood_servers:
                            if server.websocket == websocket:
                                from_server = True
                                # broadcast the message to all clients
                                await self.broadcast_to_all_clients(message)
                        if not from_server:
                            await self.broadcast_to_all_clients(message)
                            await self.flood_servers_with_message(message)

                    elif message["data"]["type"] == "server_hello":
                        # Find the server in the neighbourhood_servers list
                        for server in self.neighbourhood_servers:
                            # Check check for replay attack
                            if message["data"]["sender"] == server.server_address:
                                if message["counter"] < server.counter:
                                    print("Replay attack detected: Counter is not greater than the last counter.")
                                    return
                                # Check if the signature is valid
                                if not verify_signature(message["data"], message["counter"], message["signature"], RSA.import_key(server.public_key)):
                                    print("Signature verification failed")
                                    return
                                # Connection established
                                print(f"Connected to server {server.server_address}")
                                server.websocket = websocket
                                server.counter = message["counter"]

                elif message["type"] == "client_list_request":
                    print("received client_list_request")
                    await websocket.send(json.dumps(self.prepare_client_list()))

                elif message["type"] == "client_update":
                    print("received client_update")
                    await self.handle_client_update(message, websocket)

                elif message["type"] == "client_update_request":
                    print("received client_update_request")
                    await self.handle_client_update_request(websocket)

            except websockets.ConnectionClosed as e:
                if public_key:
                    if public_key in self.clients:
                        del self.clients[public_key]
                    await self.broadcast_client_update()
                    # print(f"connection closed: {e}")
                break


    async def forward_message_to_server(self, message):
        destination_server = message["data"]["destination_servers"]
        for server in self.neighbourhood_servers:
            if server.server_address in destination_server and server.websocket:
                await server.websocket.send(json.dumps(message))
            else:
                print(f"Server {server.server_address} not connected to the network")

    async def flood_servers_with_message(self, message):
        for server in self.neighbourhood_servers:
            if server.websocket:
                await server.websocket.send(json.dumps(message))
            else:
                print(f"Server {server.server_address} not connected to the network")

    async def broadcast_client_update(self):
        client_update = {
            "type": "client_update",
            "clients": list(self.clients.keys())
        }
        for server in self.neighbourhood_servers:
            await server.websocket.send(json.dumps(client_update))


    async def broadcast_to_all_clients(self, message):
        for client_ws in self.clients.values():
            await client_ws.send(json.dumps(message))


    async def handle_client_update(self, message, websocket):
        # Extract the list of clients from the message
        updated_clients = message["clients"]
        # Update the internal client list for this server
        for server in self.neighbourhood_servers:
            if websocket == server.websocket:
                server.clients = updated_clients
                print(f"Updated client list for server {server.server_address} with {updated_clients}")


    async def handle_client_update_request(self, websocket):
        # Prepare the client update message with the list of connected clients
        client_update_message = {
            "type": "client_update",
            "clients": list(self.clients.keys()),  # List of client fingerprints
        }

        # Send the update back to the requesting server
        await websocket.send(json.dumps(client_update_message))

        # Optionally log the event
        print("Sent client update in response to a client update request.")


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

        for server in self.neighbourhood_servers:
            client_list["servers"].append({
                "address": server.server_address,
                "clients": server.clients
            })

        return client_list

    async def send_server_hello(self, websocket):
        self.counter += 1
        data = {
            "type": "server_hello",
            "sender": f"{self.uri}",
        }
        signiture = sign_message(data, self.counter, self.private_key)
        full_message = {
            "type": "signed_data",
            "data": data,
            "counter": self.counter,
            "signature": signiture
        }
        await websocket.send(json.dumps(full_message))

    async def server_handler(self):
        # await self.prompt_for_servers()
        async with websockets.serve(self.handle_client, self.address, self.port):
            await self.connect_to_neighbourhood()
            print(f"listening on {self.uri}")
            await asyncio.Future()  # Run forever

    async def prompt_for_servers(self):
        prompt = [inquirer.Confirm("has_neighbourhood", message="Are there other servers in the neighborhood?", default=False)]
        answer = inquirer.prompt(prompt)
        if answer["has_neighbourhood"]:
            while True:
                server_address = inquirer.prompt([inquirer.Text("server_address", message="Enter the address of the neighboring server (or leave blank to finish)", default="127.0.0.1:8000")])["server_address"]
                if not server_address: break
                server_public_key = input("Enter the public key of the neighboring server in base64 encoding (or leave blank to finish): ")
                if not server_public_key: break
                # decode the base64 encoded public key
                ### ADD SOME ERROR HANDLING HERE ###
                server_public_key = base64.b64decode(server_public_key)
                self.neighbourhood_servers.append(RemoteServer(server_address=f"ws://{server_address}", public_key=server_public_key))
                print(f"Added server {server_address} to the neighborhood")


    async def connect_to_neighbourhood(self):
        for server in self.neighbourhood_servers:
            # try to connect to other servers if they are already running
            try:
                websocket = await websockets.connect(server.server_address)
                server.websocket = websocket 
                await self.send_server_hello(websocket)
                print(f"Connected to {server.server_address}")           
                await websocket.send(json.dumps({"type": "client_update_request"}))
                
                asyncio.create_task(self.listen_for_server_messages(websocket, server.server_address))
            except Exception as e:
                print(f"Could not connect to {server.server_address} make sure the server is running \n exception: {e}")
                pass

    async def listen_for_server_messages(self, websocket, server_address):
        try:
            async for message in websocket:
                message = json.loads(message)
                if message["type"] == "client_update":
                    print(f"Received client update from server {server_address}")
                    # Handle the message here
                    for server in self.neighbourhood_servers:
                        if server.server_address == server_address:
                            server.clients = message["clients"]
                elif message["data"]["type"] == "chat" or message["data"]["type"] == "public_chat":
                    await self.broadcast_to_all_clients(message)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    prompt = [
        inquirer.Text("address", message="Host address", default="127.0.0.1"),
        inquirer.Text("port", message="Host port", default="8000"),
        inquirer.Text("Flask server", message="Websocket for Flask server (You only need one running leave empty, if you are creating more than 1 servers) 5000 is default", default="")
    ]
    config = inquirer.prompt(prompt)
    if config["Flask server"] != "":
        subprocess.Popen(f'python3 app.py {config["Flask server"]}', shell=True)
    server = Server(config["address"], config["port"])
    
    asyncio.run(server.server_handler())