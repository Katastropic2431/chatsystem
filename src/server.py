import asyncio
import websockets
import json
import inquirer
import hashlib
from Crypto.PublicKey import RSA
from Crypto.Signature import pss
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes


class Server:
    def __init__(self, address="127.0.0.1", port=8000):
        self.clients = {}
        # List of WebSocket connections to other servers
        self.neighbourhood_servers = [] 
        self.address = address
        self.port = port 
        self.uri = f"ws://{address}:{port}"

    async def handle_client(self, websocket, path):
        public_key = None
        while True:
            try:
                message = await websocket.recv()
                message = json.loads(message)

                if "data" in message:
                    if message["data"]["type"] == "hello":
                        public_key = message["data"]["public_key"]
                        # fingerprint = hashlib.sha256(public_key.encode()).hexdigest()
                        # self.clients[fingerprint] = websocket
                        self.clients[public_key] = websocket
                        print(f"Received hello message from client")
                        # await broadcast_client_update()

                    elif message["data"]["type"] == "chat":
                        print("received message")
                        await self.broadcast_to_all_clients(message)
                        # await forward_message_to_server(message)

                    elif message["data"]["type"] == "public_chat":
                        await self.broadcast_to_all_clients(message)

                elif "type" in message:
                    if message["type"] == "client_list_request":
                        print("received client_list_request")
                        await websocket.send(json.dumps(self.prepare_client_list()))

                    elif message["type"] == "client_update":
                        await self.handle_client_update(message)

                    elif message["type"] == "client_update_request":
                        await self.handle_client_update_request(websocket)

            except websockets.ConnectionClosed as e:
                if public_key:
                    # fingerprint = hashlib.sha256(public_key.encode()).hexdigest()
                    if public_key in self.clients:
                        del self.clients[public_key]
                    await self.broadcast_client_update()
                    print(f"connection closed: {e}")
                break

    async def forward_message_to_server(self, message):
        destination_server = message["data"]["destination_server"]
        for server in self.neighbourhood_servers:
            if server.remote_address[0] == destination_server:
                await server.send(json.dumps(message))

    async def broadcast_client_update(self):
        client_update = {
            "type": "client_update",
            "clients": list(self.clients.keys())
        }
        for server in self.neighbourhood_servers:
            await server.send(json.dumps(client_update))

    async def broadcast_to_all_clients(self, message):
        for client_ws in self.clients.values():
            await client_ws.send(json.dumps(message))

    async def handle_client_update(self, message):
        # Extract the list of clients from the message
        updated_clients = message["clients"]
        
        # Update the internal client list for this server
        # Assuming we store the clients by server address
        server_address = message.get("server_address")
        # if server_address:
        #     server_client_lists[server_address] = updated_clients

        # Optionally, you can log or perform additional tasks based on the update
        print(f"Received client update from {server_address}: {updated_clients}")

    async def handle_client_update_request(self, websocket):
        # Prepare the client update message with the list of connected clients
        client_update_message = {
            "type": "client_update",
            "clients": list(self.clients.keys()),  # List of client fingerprints
            "server_address": "your_server_address"  # Replace with actual server address
        }

        # Send the update back to the requesting server
        await websocket.send(json.dumps(client_update_message))

        # Optionally log the event
        print("Sent client update in response to a client update request.")


    def prepare_client_list(self):
        return {
            "type": "client_list",
            "servers": [
                {
                    "address": self.uri,
                    "clients": list(self.clients.keys())
                }
            ]
        }

    async def server_handler(self):
        async with websockets.serve(self.handle_client, self.address, self.port):
            print(f"listening on {self.uri}")
            await asyncio.Future()  # Run forever

    async def connect_to_neighbourhood(self):
        for address in self.neighbourhood_servers:
            websocket = await websockets.connect(f"ws://{address}")
            self.neighbourhood_servers.append(websocket)
            await websocket.send(json.dumps({"type": "client_update_request"}))

if __name__ == "__main__":
    prompt = [
        inquirer.Text("address", message="Host address", default="127.0.0.1"),
        inquirer.Text("port", message="Host port", default="8000")
    ]
    config = inquirer.prompt(prompt)
    server = Server(config["address"], config["port"])
    asyncio.run(server.server_handler())