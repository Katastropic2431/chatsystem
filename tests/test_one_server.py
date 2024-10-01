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
from client_simulator import setup_simulators, close_connections


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

config = {
    "address": "127.0.0.1",
    "port": 8000,
    "flask_server": 5000,
}

@pytest.mark.asyncio
async def test_single_client_send_hello_and_request_client_list(run_server):
    client = Client(config=config)

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
    client = Client(config=config)
    message_text = "Hello World!"
    
    async with websockets.connect(client.server_uri) as websocket:
        # Send hello message
        await client.send_hello(websocket)
        await client.send_chat_message(
            websocket, 
            [client.server_uri],
            [client.public_key],
            message_text
        )

        message = await websocket.recv()
        message_json = json.loads(message)
        text, sender = client.extract_chat_message(message_json)
    
    assert text == message_text
    assert sender == client.fingerprint


@pytest.mark.asyncio
async def test_single_client_send_message_to_another_client(run_server):
    client1 = Client(config=config)
    client2 = Client(config=config)
    message_text = "Hello from client 2!"

    simulators = await setup_simulators([client1, client2])
    client1_task = simulators[0].recv_message()
    client2_task = simulators[1].send_message_and_listen(
        message_text,
        [client1.server_uri], 
        [client1.public_key]
    )

    # Start both tasks concurrently
    client1_result, _ = await asyncio.gather(client1_task, client2_task)

    await close_connections(simulators)

    # Validate that Client 1 received the chat message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint


@pytest.mark.asyncio
async def test_message_from_unknown_sender(run_server):
    client1 = Client(config=config)
    client2 = Client(config=config)
    message_text = "Hello from client 2!"

    simulators = await setup_simulators([client1, client2])
    client1_task = simulators[0].recv_message_no_client_info()
    client2_task = simulators[1].send_message_and_listen(
        message_text,
        [client1.server_uri], 
        [client1.public_key]
    )

    # Start tasks concurrently
    client1_result, _ = await asyncio.gather(client1_task, client2_task)

    await close_connections(simulators)

    # Cannot verify signature of message from unknown sender
    assert client1_result[0] == None
    assert client1_result[1] == None


@pytest.mark.asyncio
async def test_third_client_does_not_receive_private_message(run_server):
    """One client sends a message to another client. The third client should not receive the message."""
    client1 = Client(config=config)
    client2 = Client(config=config)
    client3 = Client(config=config)
    message_text = "Hello from client 2!"

    simulators = await setup_simulators([client1, client2, client3])
    client1_task = simulators[0].recv_message()
    client2_task = simulators[1].send_message_and_listen(
        message_text, 
        [client1.server_uri],
        [client1.public_key]
    )
    client3_task = simulators[2].recv_message()

    # Start tasks concurrently
    client1_result, _, client3_result = await asyncio.gather(client1_task, client2_task, client3_task)

    await close_connections(simulators)

    # Validate that Client 1 received the chat message from Client 2
    # Client 3 should not receive any message
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint
    assert client3_result[0] == None
    assert client3_result[1] == None


@pytest.mark.asyncio
async def test_send_message_to_multiple_clients(run_server):
    client1 = Client(config=config)
    client2 = Client(config=config)
    client3 = Client(config=config)
    message_text = "Hello from client 2!"

    simulators = await setup_simulators([client1, client2, client3])
    client1_task = simulators[0].recv_message()
    client2_task = simulators[1].send_message_and_listen(
        message_text,
        [client1.server_uri, client3.server_uri], 
        [client1.public_key, client3.public_key]
    )
    client3_task = simulators[2].recv_message()

    # Start tasks concurrently
    client1_result, _, client3_result = await asyncio.gather(client1_task, client2_task, client3_task)

    await close_connections(simulators)

    # Validate that Client 1 and Client 3 received the chat message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint
    assert client3_result[0] == message_text
    assert client3_result[1] == client2.fingerprint


@pytest.mark.asyncio
async def test_multiturn_dialogue(run_server):
    client1 = Client(config=config)
    client2 = Client(config=config)
    client1_messages = ["Hello from client 1!", "Hello from client 1 again!"]
    client2_messages = ["Hello from client 2!", "Hello from client 2 again!"]

    simulators = await setup_simulators([client1, client2])
    client1_task = simulators[0].send_multiple_messages_and_listen(
        client1_messages, 
        [client2.server_uri], 
        [client2.public_key]
    )
    client2_task = simulators[1].send_multiple_messages_and_listen(
        client2_messages, 
        [client1.server_uri],
        [client1.public_key]
    )

    # Start tasks concurrently
    client1_result, client2_result = await asyncio.gather(client1_task, client2_task)

    await close_connections(simulators)

    # Validate Client 1 receives all the messages from Client 2, and vice versa
    assert client1_result[0] == client2_messages
    assert client2_result[0] == client1_messages


@pytest.mark.asyncio
async def test_public_chat(run_server):
    client1 = Client(config=config)
    client2 = Client(config=config)
    client3 = Client(config=config)
    message_text = "Hello from client 2!"

    simulators = await setup_simulators([client1, client2, client3])
    client1_task = simulators[0].recv_message()
    client2_task = simulators[1].send_message_and_listen(message_text)
    client3_task = simulators[2].recv_message()

    # Start tasks concurrently
    client1_result, _, client3_result = await asyncio.gather(client1_task, client2_task, client3_task)

    await close_connections(simulators)

    # Validate that Client 1 and Client 3 received the public message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint
    assert client3_result[0] == message_text
    assert client3_result[1] == client2.fingerprint


@pytest.mark.asyncio
async def test_check_for_relay_attack(run_server):
    client1 = Client(config=config)
    client2 = Client(config=config)
    messages = ["First message from client 1", "Replay attack message from client 1"]

    simulators = await setup_simulators([client1, client2])
    # Send two messages, with the counter of the second message set to 0
    client1_task = simulators[0].simulate_relay_attack(
        messages,
        [client2.server_uri], 
        [client2.public_key]
    )
    client2_task = simulators[1].recv_multiple_messages(num_message=2)

    # Start tasks concurrently
    _, (messages, senders) = await asyncio.gather(client1_task, client2_task)

    await close_connections(simulators)

    # Client 2 should only receive one message
    assert len(messages) == 1
    assert len(senders) == 1


@pytest.mark.asyncio
async def test_send_message_to_offline_client(run_server):
    client1 = Client(config=config)
    client2 = Client(config=config)
    message_text = "message from client 1"

    simulators = await setup_simulators([client1, client2])
    # Validate sending a message to an offline client would not cause any exception
    client1_task = simulators[0].sleep_and_send_message(
        message_text,
        [client2.server_uri], 
        [client2.public_key]
    )
    client2_task = simulators[1].quit()

    # Start tasks concurrently
    await asyncio.gather(client1_task, client2_task)

    await simulators[0].quit()
