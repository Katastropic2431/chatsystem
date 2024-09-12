import asyncio
import websockets
import json
import inquirer
from dataclasses import dataclass, field

@dataclass
class RemoteServer:
    server_address: str = ""
    websocket: object = None
    clients: list = field(default_factory=list)


class Server:
    def __init__(
        self, 
        address="127.0.0.1", 
        port=8000, 
        neighbourhood_server_addresses=[],
    ):
        # Dict of client's public key to its websocket connection
        self.clients = {}
        self.address = address
        self.port = port 
        self.uri = f"ws://{address}:{port}"
        self.neighbourhood_servers = [
            RemoteServer(server_address=address)
            for address in neighbourhood_server_addresses
        ]


    async def handle_client(self, websocket, path):
        public_key = None
        while True:
            try:
                message = await websocket.recv()
                message = json.loads(message)

                if message["type"] == "signed_data":
                    if message["data"]["type"] == "hello":
                        print(f"Received hello message from client")
                        public_key = message["data"]["public_key"]
                        self.clients[public_key] = websocket
                        # await broadcast_client_update()

                    elif message["data"]["type"] == "chat":
                        print("received chat message")
                        if self.uri in message["data"]["destination_servers"]:
                            await self.broadcast_to_all_clients(message)
                        # await self.forward_message_to_server(message)

                    elif message["data"]["type"] == "public_chat":
                        await self.broadcast_to_all_clients(message)

                elif message["type"] == "client_list_request":
                    print("received client_list_request")
                    await websocket.send(json.dumps(self.prepare_client_list()))

                elif message["type"] == "client_update":
                    await self.handle_client_update(message)

                elif message["type"] == "client_update_request":
                    await self.handle_client_update_request(websocket)

            except websockets.ConnectionClosed as e:
                if public_key:
                    if public_key in self.clients:
                        del self.clients[public_key]
                    await self.broadcast_client_update()
                    print(f"connection closed: {e}")
                break


    async def forward_message_to_server(self, message):
        destination_server = message["data"]["destination_servers"]
        for server in self.neighbourhood_servers:
            if server.server_address in destination_server:
                await server.websocket.send(json.dumps(message))


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


    async def handle_client_update(self, message):
        # Extract the list of clients from the message
        updated_clients = message["clients"]

        # Update the internal client list for this server
        # Assuming we store the clients by server address
        server_address = message.get("server_address")
        for server in self.neighbourhood_servers:
            if server.server_address == server_address:
                server.clients = updated_clients

        # Optionally, you can log or perform additional tasks based on the update
        print(f"Received client update from {server_address}")


    async def handle_client_update_request(self, websocket):
        # Prepare the client update message with the list of connected clients
        client_update_message = {
            "type": "client_update",
            "clients": list(self.clients.keys()),  # List of client fingerprints
            "server_address": self.uri  # Replace with actual server address
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


    async def server_handler(self):
        await self.connect_to_neighbourhood()
        async with websockets.serve(self.handle_client, self.address, self.port):
            print(f"listening on {self.uri}")
            await asyncio.Future()  # Run forever


    async def connect_to_neighbourhood(self):
        for server in self.neighbourhood_servers:
            # try to connect to other servers if they are already running
            try:
                websocket = await websockets.connect(server.server_address)
                server.websocket = websocket            
                await websocket.send(json.dumps({"type": "client_update_request"}))
            except ConnectionRefusedError:
                pass


if __name__ == "__main__":
    prompt = [
        inquirer.Text("address", message="Host address", default="127.0.0.1"),
        inquirer.Text("port", message="Host port", default="8000"),
    ]
    config = inquirer.prompt(prompt)
    
    server = Server(config["address"], config["port"])
    asyncio.run(server.server_handler())