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

    async def broadcast_client_update(self):
        client_update = {
            "type": "client_update",
            "clients": list(self.clients.keys()),  # List of connected client public keys
            "server_address": self.uri  # The address of the server sending the update
        }
        
        for server in self.neighbourhood_servers:
            if server.websocket is not None:
                await server.websocket.send(json.dumps(client_update))

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
                        self.clients[public_key] = websocket  # Store the public key of the new client
                        await self.broadcast_client_update()  # Broadcast the new client list to neighbors
                        print("Broadcasted client update to neighbors")

                    elif message["data"]["type"] == "chat":
                        print("Received chat message")

                        # Check if the message is for a client on this server
                        if self.uri in message["data"]["destination_servers"]:
                            # Send the message to the clients on this server
                            await self.broadcast_to_all_clients(message)
                        else:
                            # Forward the message to the correct server(s)
                            await self.forward_message_to_server(message)

                    elif message["data"]["type"] == "public_chat":
                        await self.broadcast_to_all_clients(message)

                elif message["type"] == "client_list_request":
                    print("Received client_list_request")
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
                    print(f"Connection closed: {e}")
                break


    async def connect_to_neighbourhood(self):
        for server in self.neighbourhood_servers:
            try:
                websocket = await websockets.connect(server.server_address)
                server.websocket = websocket
                print(f"Connected to neighbor {server.server_address}")
                
                # Request client update from the neighbor
                await websocket.send(json.dumps({"type": "client_update_request"}))

            except ConnectionRefusedError:
                print(f"Failed to connect to {server.server_address}. Retrying...")
                await asyncio.sleep(5)
                asyncio.create_task(self.connect_to_neighbourhood())


    async def forward_message_to_server(self, message):
        destination_servers = message["data"]["destination_servers"]
        for server in self.neighbourhood_servers:
            if server.server_address in destination_servers:
                print(f"Forwarding message to {server.server_address}")
                await server.websocket.send(json.dumps(message))



    async def broadcast_to_all_clients(self, message):
        for client_ws in self.clients.values():
            await client_ws.send(json.dumps(message))


    async def handle_client_update(self, message):
        updated_clients = message["clients"]
        server_address = message.get("server_address")

        print(f"Received client update from {server_address} with {len(updated_clients)} clients")

        # Update the internal list of clients for the neighbor server
        for server in self.neighbourhood_servers:
            if server.server_address == server_address:
                # Merge the client lists
                for client in updated_clients:
                    if client not in server.clients:
                        server.clients.append(client)
        
        print(f"Updated clients for server {server_address}: {updated_clients}")

    async def handle_client_update_request(self, websocket):
        # Prepare the client update message with the list of connected clients
        client_update_message = {
            "type": "client_update",
            "clients": list(self.clients.keys()),  # List of client public keys
            "server_address": self.uri  # The server address sending the update
        }

        # Send the client update back to the requesting server
        await websocket.send(json.dumps(client_update_message))

        # Log the event
        print(f"Sent client update from {self.uri} to neighbor in response to request.")

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

        # Include the clients from the neighbors
        for server in self.neighbourhood_servers:
            client_list["servers"].append({
                "address": server.server_address,
                "clients": server.clients  # Add the clients from each neighboring server
            })

        print(f"Prepared client list: {client_list}")
        return client_list



    async def server_handler(self):
        await self.connect_to_neighbourhood()
        async with websockets.serve(self.handle_client, self.address, self.port):
            print(f"listening on {self.uri}")
            await asyncio.Future()  # Run forever


    async def connect_to_neighbourhood(self):
        for server in self.neighbourhood_servers:
            try:
                websocket = await websockets.connect(server.server_address)
                server.websocket = websocket
                print(f"Connected to neighbor {server.server_address}")
                
                # Request client update from the neighbor
                await websocket.send(json.dumps({"type": "client_update_request"}))

            except ConnectionRefusedError:
                print(f"Failed to connect to {server.server_address}. Retrying...")
                await asyncio.sleep(5)
                asyncio.create_task(self.connect_to_neighbourhood())



if __name__ == "__main__":  
    prompt = [
        inquirer.Text("address", message="Host address", default="127.0.0.1"),
        inquirer.Text("port", message="Host port", default="8000"),
        inquirer.Text("neighbours", message="Comma-separated list of neighbour servers", default="ws://127.0.0.1:8001")
    ]
    config = inquirer.prompt(prompt)
    
    neighbours = config["neighbours"].split(",") if config["neighbours"] else []
    
    server = Server(config["address"], config["port"], neighbours)
    asyncio.run(server.server_handler())