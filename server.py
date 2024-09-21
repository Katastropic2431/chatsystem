import asyncio
import websockets
import json
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization

serverlist = {} # Dictionary to store address and client public key
connected_clients = {}  # Dictionary to store websocket connection and the last counter
client_public_keys = {} # Dictionary to store public keys, keyed by WebSocket connection

# Function to verify the signature
def verify_signature(public_key_pem, signature, message, counter):
    public_key = serialization.load_pem_public_key(public_key_pem)
    message_to_verify = message + str(counter)

    try:
        public_key.verify(
            base64.b64decode(signature),
            message_to_verify.encode(),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )
        return True
    except Exception as e:
        print(f"Signature verification failed: {e}")
        return False
    
def get_public_key_for_client(websocket):
    # Return the public key for the given client (identified by WebSocket)
    return client_public_keys.get(websocket, None)

async def handle_client(websocket, path):
    # Register the new client by adding to connected_clients


    try:
        async for message in websocket:
            message_data = json.loads(message)
            
            if message_data["type"] == "client_list_request":
                client_list = [public_key for websocket, public_key in client_public_keys.items()]
                await websocket.send(json.dumps({
                        "type": "client_list",
                        "servers": [
                            {
                                "address": "localhost",  # Replace this with your actual server address
                                "clients": client_list   # List of public keys
                            }
                        ]
                    }))
                
            # Process hello message
            elif message_data["data"]["type"] == "hello":
                connected_clients[websocket] = {"counter": 0}
                await notify_users(f"A user has joined the chat. Total users: {len(connected_clients)}")
                print("Received hello message with public key:", message_data["data"]["public_key"])
                client_public_keys[websocket] = {"publicKey": message_data["data"]["public_key"]}


            # Process signed_data messages
            elif message_data["type"] == "signed_data":
                counter = message_data["counter"]
                print(f'counter from message = {message_data["counter"]}')
                # Check if the new counter is greater than the last stored counter
                if counter > connected_clients[websocket]["counter"]:
                    connected_clients[websocket]["counter"] = counter  # Update the counter
                    await broadcast_message(message)  # Broadcast the message to all clients
                else:
                    print("Replay attack detected: Counter is not greater than the last counter.")

    finally:
        # Unregister the client
        del connected_clients[websocket]
        await notify_users(f"A user has left the chat. Total users: {len(connected_clients)}")

async def broadcast_message(message):
    # Broadcast the message to all connected clients
    for client in connected_clients:
        await client.send(message)

async def notify_users(message):
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients])

async def main():
    async with websockets.serve(handle_client, "localhost", 6789):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
