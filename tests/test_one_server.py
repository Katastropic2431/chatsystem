import asyncio
import pytest
import websockets
import threading
import json
import sys
import os
import time
from typing import Optional
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


async def setup_client(
    client: Client,
    websocket: object,
    my_hello_event: asyncio.Event,
    others_hello_events: list[asyncio.Event],
    my_request_client_list_event: asyncio.Event,
    others_request_client_list_events: list[asyncio.Event],
):
    # Send hello to server
    await client.send_hello(websocket)
    my_hello_event.set()

    # wait for other clients to send hello
    for hello_event in others_hello_events:
        await hello_event.wait()

    await client.request_client_list(websocket)
    message = await websocket.recv()
    message_json = json.loads(message)
    client.cache_client_info(message_json)
    my_request_client_list_event.set()

    for request_event in others_request_client_list_events:
        await request_event.wait()


async def run_client_recv_message(
    client: Client, 
    my_hello_event: asyncio.Event, 
    others_hello_events: list[asyncio.Event],
    my_request_client_list_event: asyncio.Event,
    others_request_client_list_events: list[asyncio.Event],
):
    async with websockets.connect(client.server_uri) as websocket:
        await setup_client(
            client,
            websocket, 
            my_hello_event, 
            others_hello_events,
            my_request_client_list_event,
            others_request_client_list_events,
        )

        # Listen for incoming chat messages
        message = await websocket.recv()
        message_json = json.loads(message)
        if message_json["data"]["type"] == "chat":
            text, sender = client.extract_chat_message(message_json)
        elif message_json["data"]["type"] == "public_chat":
            text, sender = client.extract_public_chat(message_json)
        
    return text, sender
    

async def run_client_send_message(
    client: Client, 
    message_text: str,
    my_hello_event: asyncio.Event, 
    others_hello_events: list[asyncio.Event],
    my_request_client_list_event: asyncio.Event,
    others_request_client_list_events: list[asyncio.Event],
    recipient_public_keys: Optional[list[RSA.RsaKey]] = None,
):
    async with websockets.connect(client.server_uri) as websocket:
        await setup_client(
            client,
            websocket, 
            my_hello_event, 
            others_hello_events,
            my_request_client_list_event,
            others_request_client_list_events,
        )

        if recipient_public_keys is None:
            await client.send_public_message(websocket, message_text)
        else:
            # Send a chat message to the recipient using the public key
            await client.send_chat_message(
                websocket,
                [client.server_uri],
                recipient_public_keys, 
                message_text
            )
        
        await websocket.recv()


@pytest.mark.asyncio
async def test_single_client_send_message_to_another_client(run_server):
    server_uri = "ws://127.0.0.1:8000"
    client1 = Client(server_uri)
    client2 = Client(server_uri)
    message_text = "Hello from client 2!"

    client1_hello_event = asyncio.Event()
    client2_hello_event = asyncio.Event()
    client1_request_client_list_event = asyncio.Event()
    client2_request_client_list_event = asyncio.Event()

    # Run Client 1 (listening for messages) and Client 2 (sending a message)
    client1_task = run_client_recv_message(
        client1, 
        client1_hello_event,
        [client2_hello_event],
        client1_request_client_list_event,
        [client2_request_client_list_event],
    )
    client2_task = run_client_send_message(
        client2, 
        message_text,
        client2_hello_event,
        [client1_hello_event],
        client2_request_client_list_event,
        [client1_request_client_list_event],
        [client1.public_key],
    )

    # Start both tasks concurrently
    client1_result, _ = await asyncio.gather(client1_task, client2_task)

    # Validate that Client 1 received the chat message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint


@pytest.mark.asyncio
async def test_message_from_unknown_sender(run_server):
    async def run_client_recv_message_no_client_info(
        client: Client, 
        my_hello_event: asyncio.Event, 
        others_hello_events: list[asyncio.Event],
        my_request_client_list_event: asyncio.Event,
        others_request_client_list_events: list[asyncio.Event],
    ):
        async with websockets.connect(client.server_uri) as websocket:
            await setup_client(
                client,
                websocket, 
                my_hello_event, 
                others_hello_events,
                my_request_client_list_event,
                others_request_client_list_events,
            )

            # Simulate that the client has no information about the other clients
            client.fingerprint_to_public_key = {}

            # Listen for incoming chat messages
            message = await websocket.recv()
            message_json = json.loads(message)
            text, sender = client.extract_chat_message(message_json)
            return text, sender
    
    server_uri = "ws://127.0.0.1:8000"
    client1 = Client(server_uri)
    client2 = Client(server_uri)
    message_text = "Hello from client 2!"

    client1_hello_event = asyncio.Event()
    client2_hello_event = asyncio.Event()
    client1_request_client_list_event = asyncio.Event()
    client2_request_client_list_event = asyncio.Event()

    # Run Client 1 (listening for messages) and Client 2 (sending a message)
    client1_task = run_client_recv_message_no_client_info(
        client1, 
        client1_hello_event,
        [client2_hello_event],
        client1_request_client_list_event,
        [client2_request_client_list_event],
    )
    client2_task = run_client_send_message(
        client2, 
        message_text,
        client2_hello_event,
        [client1_hello_event],
        client2_request_client_list_event,
        [client1_request_client_list_event],
        [client1.public_key],
    )

    # Start tasks concurrently
    client1_result, _ = await asyncio.gather(client1_task, client2_task)

    # Cannot verify signature of message from unknown sender
    assert client1_result[0] == None
    assert client1_result[1] == None


@pytest.mark.asyncio
async def test_third_client_does_not_receive_private_message(run_server):
    """One client sends a message to another client. The third client should not receive the message."""

    server_uri = "ws://127.0.0.1:8000"
    client1 = Client(server_uri)
    client2 = Client(server_uri)
    client3 = Client(server_uri)
    message_text = "Hello from client 2!"

    client1_hello_event = asyncio.Event()
    client2_hello_event = asyncio.Event()
    client3_hello_event = asyncio.Event()
    client1_request_client_list_event = asyncio.Event()
    client2_request_client_list_event = asyncio.Event()
    client3_request_client_list_event = asyncio.Event()

    client1_task = run_client_recv_message(
        client1, 
        client1_hello_event,
        [client2_hello_event, client3_hello_event],
        client1_request_client_list_event,
        [client2_request_client_list_event, client3_request_client_list_event]
    )
    client2_task = run_client_send_message(
        client2, 
        message_text,
        client2_hello_event,
        [client1_hello_event, client3_hello_event],
        client2_request_client_list_event,
        [client1_request_client_list_event, client3_request_client_list_event],
        [client1.public_key],
    )
    client3_task = run_client_recv_message(
        client3, 
        client3_hello_event,
        [client1_hello_event, client2_hello_event],
        client3_request_client_list_event,
        [client1_request_client_list_event, client2_request_client_list_event]
    )

    # Start tasks concurrently
    client1_result, _, client3_result = await asyncio.gather(client1_task, client2_task, client3_task)

    # Validate that Client 1 received the chat message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint
    assert client3_result[0] == None
    assert client3_result[1] == None


@pytest.mark.asyncio
async def test_send_message_to_multiple_clients(run_server):
    server_uri = "ws://127.0.0.1:8000"
    client1 = Client(server_uri)
    client2 = Client(server_uri)
    client3 = Client(server_uri)
    message_text = "Hello from client 2!"

    client1_hello_event = asyncio.Event()
    client2_hello_event = asyncio.Event()
    client3_hello_event = asyncio.Event()
    client1_request_client_list_event = asyncio.Event()
    client2_request_client_list_event = asyncio.Event()
    client3_request_client_list_event = asyncio.Event()

    client1_task = run_client_recv_message(
        client1, 
        client1_hello_event,
        [client2_hello_event, client3_hello_event],
        client1_request_client_list_event,
        [client2_request_client_list_event, client3_request_client_list_event]
    )
    client2_task = run_client_send_message(
        client2, 
        message_text,
        client2_hello_event,
        [client1_hello_event, client3_hello_event],
        client2_request_client_list_event,
        [client1_request_client_list_event, client3_request_client_list_event],
        [client1.public_key, client3.public_key],
    )
    client3_task = run_client_recv_message(
        client3, 
        client3_hello_event,
        [client1_hello_event, client2_hello_event],
        client3_request_client_list_event,
        [client1_request_client_list_event, client2_request_client_list_event]
    )

    # Start tasks concurrently
    client1_result, _, client3_result = await asyncio.gather(client1_task, client2_task, client3_task)

    # Validate that Client 1 and Client 3 received the chat message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint
    assert client3_result[0] == message_text
    assert client3_result[1] == client2.fingerprint


async def send_multiple_messages(
    client, 
    websocket, 
    recipient_public_keys, 
    messages
):
    for message in messages:
        await client.send_chat_message(
            websocket,
            [client.server_uri],
            recipient_public_keys,
            message
        )


async def listen_for_multiple_messages(client, websocket, num_message):
    messages = []
    for _ in range(num_message):
        message = await websocket.recv()
        message_json = json.loads(message)
        text, sender = client.extract_chat_message(message_json)
        
        # Exclude messages from client itself
        if text is not None:
            messages.append(text)
    
    return messages


async def send_multiple_messages_and_listen(
    client: Client, 
    messages: list[str],
    recipient_public_keys: list[RSA.RsaKey],
    my_hello_event: asyncio.Event, 
    others_hello_events: list[asyncio.Event],
    my_request_client_list_event: asyncio.Event,
    others_request_client_list_events: list[asyncio.Event],
):
    async with websockets.connect(client.server_uri) as websocket:
        await setup_client(
            client,
            websocket, 
            my_hello_event, 
            others_hello_events,
            my_request_client_list_event,
            others_request_client_list_events,
        )
        
        messages, _ = await asyncio.gather(
            listen_for_multiple_messages(client, websocket, len(messages) * 2),
            send_multiple_messages(
                client,
                websocket,
                recipient_public_keys, 
                messages
            )
        )
        
    return messages


@pytest.mark.asyncio
async def test_multiturn_dialogue(run_server):
    server_uri = "ws://127.0.0.1:8000"
    client1 = Client(server_uri)
    client2 = Client(server_uri)
    client1_messages = ["Hello from client 1!", "Hello from client 1 again!"]
    client2_messages = ["Hello from client 2!", "Hello from client 2 again!"]

    client1_hello_event = asyncio.Event()
    client2_hello_event = asyncio.Event()
    client1_request_client_list_event = asyncio.Event()
    client2_request_client_list_event = asyncio.Event()

    client1_task = send_multiple_messages_and_listen(
        client1,
        client1_messages,
        [client2.public_key],
        client1_hello_event,
        [client2_hello_event],
        client1_request_client_list_event,
        [client2_request_client_list_event],
    )
    client2_task = send_multiple_messages_and_listen(
        client2, 
        client2_messages,
        [client1.public_key],
        client2_hello_event,
        [client1_hello_event],
        client2_request_client_list_event,
        [client1_request_client_list_event],
    )

    # Start tasks concurrently
    client1_received_messasges, client2_received_messages = await asyncio.gather(client1_task, client2_task)

    assert client1_received_messasges == client2_messages
    assert client2_received_messages == client1_messages


@pytest.mark.asyncio
async def test_public_chat(run_server):
    server_uri = "ws://127.0.0.1:8000"
    client1 = Client(server_uri)
    client2 = Client(server_uri)
    client3 = Client(server_uri)
    message_text = "Hello from client 2!"

    client1_hello_event = asyncio.Event()
    client2_hello_event = asyncio.Event()
    client3_hello_event = asyncio.Event()
    client1_request_client_list_event = asyncio.Event()
    client2_request_client_list_event = asyncio.Event()
    client3_request_client_list_event = asyncio.Event()

    client1_task = run_client_recv_message(
        client1, 
        client1_hello_event,
        [client2_hello_event, client3_hello_event],
        client1_request_client_list_event,
        [client2_request_client_list_event, client3_request_client_list_event]
    )
    # Send public message by not specifying recipients' public keys
    client2_task = run_client_send_message(
        client2, 
        message_text,
        client2_hello_event,
        [client1_hello_event, client3_hello_event],
        client2_request_client_list_event,
        [client1_request_client_list_event, client3_request_client_list_event]
    )
    client3_task = run_client_recv_message(
        client3, 
        client3_hello_event,
        [client1_hello_event, client2_hello_event],
        client3_request_client_list_event,
        [client1_request_client_list_event, client2_request_client_list_event]
    )

    # Start tasks concurrently
    client1_result, _, client3_result = await asyncio.gather(client1_task, client2_task, client3_task)

    # Validate that Client 1 and Client 3 received the chat message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint
    assert client3_result[0] == message_text
    assert client3_result[1] == client2.fingerprint


# @pytest.mark.asyncio
# async def test_check_for_relay_attack(run_server):
#     pass


# @pytest.mark.asyncio
# async def test_send_message_to_offline_client(run_server):
#     pass


# @pytest.mark.asyncio
# async def test_upload_and_download_file(run_server):
#     pass