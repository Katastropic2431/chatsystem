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
def verify_signature(websocket, signature, data, counter):
    # Get the signing pem key for the client
    if websocket not in client_public_keys:
        print("Client not found")
        return False
    
    signing_pem = client_public_keys[websocket]["signingKey"].encode('utf-8')
    signing_key = serialization.load_pem_public_key(signing_pem)
    data_string = json.dumps(data, separators=(',', ':'))
    message_to_verify = data_string + str(counter)
    message_bytes = message_to_verify.encode('utf-8')
    
    # Decode the Base64 signature
    signature_bytes = base64.b64decode(signature)
    
    # Verify the signature using the public key with RSA-PSS
    try:
        signing_key.verify(
            signature_bytes,
            message_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=32
            ),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        print(f"Signature verification failed: {e}")
        return False
    
def get_public_key_for_client(websocket):
    # Return the public key for the given client (identified by WebSocket)
    return client_public_keys.get(websocket, None)

async def handle_client(websocket, path):
    try:
        async for message in websocket:
            message_data = json.loads(message)
            
            if message_data["type"] == "client_list_request":
                client_list = [{"username": public_key["username"], "publicKey": public_key["publicKey"]} for websocket, public_key in client_public_keys.items()]
                await websocket.send(json.dumps({
                        "type": "client_list",
                        "servers": [
                            {
                                "address": "localhost",  # Replace this with your actual server address
                                "clients": client_list   # List of usernames and public keys
                            }
                        ]
                    }))
                
            # Process hello message
            elif message_data["data"]["type"] == "hello":
                username = message_data["data"]["username"]
                public_key = message_data["data"]["public_key"]
                signing_key = message_data["data"]["signing_key"]
                connected_clients[websocket] = {"counter": 0}
                await notify_users(f"{username} has joined the chat. Total users: {len(connected_clients)}")
                print(f"Received hello message from {username} with public key: {public_key}")
                client_public_keys[websocket] = {"username": username, "publicKey": public_key, "signingKey": signing_key}

            # Process signed_data messages
            elif message_data["type"] == "signed_data":
                # Verify the signature
                verify_signature_result = verify_signature(websocket, message_data["signature"], message_data["data"], message_data["counter"])
                if not verify_signature_result:
                    #send error message
                    await websocket.send("Signature verification failed")
                    return
                print(f"Signature verification result: {verify_signature_result}")
                counter = message_data["counter"]
                print(f'counter from message = {message_data["counter"]}')
                # Check if the new counter is greater than the last stored counter
                if counter > connected_clients[websocket]["counter"]:
                    connected_clients[websocket]["counter"] = counter  # Update the counter
                    if message_data["data"]["type"] == "chat":
                        await forward_message(message_data)  # Forward the chat message to the intended recipients
                else:
                    print("Replay attack detected: Counter is not greater than the last counter.")

    finally:
        # Unregister the client
        del connected_clients[websocket]
        del client_public_keys[websocket]
        await notify_users(f"A user has left the chat. Total users: {len(connected_clients)}")

async def forward_message(message_data):
    # Forward the message to the specified recipients
    print(f"Forwarding message: {message_data}")
    recipients = message_data["data"]["destination_servers"]
    for client, client_info in client_public_keys.items():
        if client_info["username"] in recipients:
            try:
                await client.send(json.dumps(message_data))
                print(f"Message forwarded to {client_info['username']}")
            except Exception as e:
                print(f"Error sending message to client: {e}")
                del connected_clients[client]

async def broadcast_message(message):
    # Broadcast the message to all connected clients
    for client in list(connected_clients.keys()):
        try:
            await client.send(message)
        except Exception as e:
            print(f"Error sending message to client: {e}")
            # Optionally, remove the client from the list of connected clients
            del connected_clients[client]

async def notify_users(message):
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients])

async def main():
    async with websockets.serve(handle_client, "localhost", 6789):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())