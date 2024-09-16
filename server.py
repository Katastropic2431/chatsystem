import asyncio
import websockets
import json
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization

client_counters = {}  # Dictionary to store the last counter value for each client
connected_clients = {}  # Dictionary to store websocket connection and the last counter
client_public_keys = {} # Dictionary to store public keys, keyed by WebSocket connection or client ID


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

# Handle incoming messages
async def handle_message(websocket, path):
    async for message in websocket:
        data = json.loads(message)

        # Check if the message is a "hello" message
        if data['data']['type'] == "hello":
            public_key_pem = data['data']['public_key']

            # Store the public key for this client, using their WebSocket connection as the key
            client_public_keys[websocket] = public_key_pem

            print(f"Stored public key for client: {websocket.remote_address}")
        elif data['type'] == "signed_data":
            message_content = data['data']['message']
            counter = data['counter']
            signature = data['signature']

            # Fetch the public key for this client
            public_key = get_public_key_for_client(websocket)

            # Continue with verification and counter validation...
            if is_counter_valid(websocket, counter) and verify_signature(public_key, signature, message_content, counter):
                print("Message verified and valid!")
                # Process the message
                client_counters[websocket] = counter  # Update the counter for this client
            else:
                print("Invalid message or possible replay attack!")



def is_counter_valid(client, counter):
    # Check if the counter is greater than the last stored counter
    if client in client_counters:
        if counter > client_counters[client]:
            return True
        else:
            print(f"Replay attack detected: {counter} <= {client_counters[client]}")
            return False
    else:
        # First time seeing this client, initialize their counter
        client_counters[client] = counter
        return True

async def handle_client(websocket, path):
    # Register the new client by adding to connected_clients
    connected_clients[websocket] = {"counter": 0}
    await notify_users(f"A user has joined the chat. Total users: {len(connected_clients)}")
    
    try:
        async for message in websocket:
            message_data = json.loads(message)

            # Process hello message
            if message_data["data"]["type"] == "hello":
                print("Received hello message with public key:", message_data["data"]["public_key"])

            # Process signed_data messages
            if message_data["type"] == "signed_data":
                counter = message_data["counter"]
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
