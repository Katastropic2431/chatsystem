import asyncio
import pytest
import websockets
import threading
import json
import sys
import os
import time
from Crypto.PublicKey import RSA

# Adjust the path to include the src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from server import Server
from client import Client


# https://stackoverflow.com/questions/76488582/python-proper-way-to-run-an-async-routine-in-a-pytest-fixture
def _run_server():
    global loop, server
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    s = Server()
    server = loop.create_task(s.server_handler())
    try:
        loop.run_until_complete(server)
    except asyncio.CancelledError:
        pass
    loop.close()


@pytest.fixture
def run_server():
    thread = threading.Thread(target=_run_server)
    thread.start()
    time.sleep(1)
    yield thread
    loop.call_soon_threadsafe(server.cancel)
    thread.join()


@pytest.mark.asyncio
async def test_single_client_send_hello_and_request_client_list(run_server):
    server_uri = "ws://127.0.0.1:8000"
    client = Client(server_uri)

    async with websockets.connect(client.server_uri) as websocket:
        # Send hello message
        await client.send_hello(websocket)
        # Request client list
        await client.request_client_list(websocket)
        # Listen for messages        
        message = await websocket.recv()

    client_list = json.loads(message)

    assert client_list['type'] == 'client_list'

    # The client list should include only one client (itself)
    assert len(client_list['servers'][0]['clients']) == 1

    assert client_list['servers'][0]['clients'][0] == client.public_key.export_key().decode('utf-8')


@pytest.mark.asyncio
async def test_single_client_send_message_to_self(run_server):
    server_uri = "ws://127.0.0.1:8000"
    client = Client(server_uri)
    message_text = "Hello World!"
    
    async with websockets.connect(client.server_uri) as websocket:
        # Send hello message
        await client.send_hello(websocket)
        await client.send_chat_message(
            websocket, 
            [server_uri],
            [client.public_key],
            message_text
        )

        message = await websocket.recv()
        message_json = json.loads(message)
        text, sender = client.extract_chat_message(message_json)
    
    assert text == message_text
    assert sender == client.fingerprint


@pytest.mark.asyncio
async def test_single_client_send_message_to_another_client_on_one_server(run_server):
    server_uri = "ws://127.0.0.1:8000"
    client1 = Client(server_uri)
    client2 = Client(server_uri)
    message_text = "Hello from client 2!"

    client1_hello_event = asyncio.Event()
    client2_hello_event = asyncio.Event()

    async def run_client_send_hello(client):
        """Client 1: Send hello and listen for chat messages."""
        async with websockets.connect(client.server_uri) as websocket:
            # Send hello to server
            await client.send_hello(websocket)
            client1_hello_event.set()

            # wait for client 2 to send hello
            await client2_hello_event.wait()

            # Request client list
            await client.request_client_list(websocket)
            message = await websocket.recv()
            message_json = json.loads(message)
            client.cache_client_info(message_json)

            # Listen for incoming chat messages
            message = await websocket.recv()
            message_json = json.loads(message)
            text, sender = client.extract_chat_message(message_json)
            return text, sender

    async def run_client_request_and_send_chat(client, message_text):
        """Client 2: Request client list and send chat message."""
        # Let client 1 connects to the server first
        await client1_hello_event.wait()
        async with websockets.connect(client.server_uri) as websocket:
            # Send hello to server
            await client.send_hello(websocket)
            client2_hello_event.set()
            
            # Request client list
            await client.request_client_list(websocket)
            message = await websocket.recv()
            client_list = json.loads(message)

            # Find the public key of the first client
            public_key_pem = client_list['servers'][0]['clients'][0]
            public_key = RSA.import_key(public_key_pem)

            # Send a chat message to the recipient using the public key
            await client.send_chat_message(
                websocket,
                [client.server_uri],
                [public_key], 
                message_text
            )

    # Run Client 1 (listening for messages) and Client 2 (sending a message)
    client1_task = run_client_send_hello(client1)
    client2_task = run_client_request_and_send_chat(client2, message_text)

    # Start both tasks concurrently
    client1_result, _ = await asyncio.gather(client1_task, client2_task)

    # Validate that Client 1 received the chat message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint
