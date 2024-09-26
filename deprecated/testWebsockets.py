import asyncio
import websockets

connected_clients = set()

async def handle_client(websocket, path):
    # Register the new client
    connected_clients.add(websocket)
    await notify_users(f"A user has joined the chat. Total users: {len(connected_clients)}")
    try:
        async for message in websocket:
            # Broadcast the message to all connected clients
            await asyncio.gather(*[client.send(message) for client in connected_clients])
    finally:
        # Unregister the client
        connected_clients.remove(websocket)
        await notify_users(f"A user has left the chat. Total users: {len(connected_clients)}")

async def notify_users(message):
    if connected_clients:  # asyncio.gather doesn't accept an empty list
        await asyncio.gather(*[client.send(message) for client in connected_clients])

async def main():
    server = await websockets.serve(handle_client, "localhost", 6789)
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
