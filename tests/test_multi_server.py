import asyncio
import pytest
import threading
import sys
import os
import time
import warnings
from typing import Optional
from Crypto.PublicKey import RSA

# Adjust the path to include the src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from server import Server, RemoteServer
from client import Client
from client_simulator import setup_simulators, close_connections


def export_remote_server(server):
    public_key_pem = server.public_key.export_key()
    return RemoteServer(
        server_address=server.uri, 
        public_key=public_key_pem,
    )


def _run_servers(server1, server2):
    global loop, server1_task, server2_task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Schedule both server handlers to run in the same event loop
    server1_task = loop.create_task(server1.server_handler())
    server2_task = loop.create_task(server2.server_handler())

    try:
        # Run the event loop until both servers are stopped
        loop.run_until_complete(asyncio.gather(server1_task, server2_task))
    except asyncio.CancelledError:
        pass
    loop.close()


@pytest.fixture
def run_servers():
    server1 = Server()  # First server instance
    server2 = Server(address="127.0.0.1", port=8001)  # Second server instance

    server1.neighbourhood_servers.append(export_remote_server(server2))
    server2.neighbourhood_servers.append(export_remote_server(server1))

    # Create a thread to run both servers in the same event loop
    thread = threading.Thread(target=_run_servers, args=(server1, server2))
    thread.start()

    # Give some time for the servers to start
    time.sleep(1)

    # Yield both servers to the test
    yield server1, server2

    for server_task in [server1_task, server2_task]:
        loop.call_soon_threadsafe(server_task.cancel)

    # Join the thread after stopping the servers
    thread.join()



@pytest.mark.asyncio
async def test_client_send_message_to_another_client_on_two_servers(run_servers):
    client1 = Client(config = {
        "address": "127.0.0.1",
        "port": 8000,
        "flask_server": 5000,
    })
    client2 = Client(config = {
        "address": "127.0.0.1",
        "port": 8001,
        "flask_server": 5000,
    })
    message_text = "Hello from client 2!"

    simulators = await setup_simulators([client1, client2])
    client1_task = simulators[0].recv_message()
    client2_task = simulators[1].send_message(message_text, [client1.server_uri], [client1.public_key])

    # Start both tasks concurrently
    client1_result, _ = await asyncio.gather(client1_task, client2_task)

    await close_connections(simulators)

    # Validate that Client 1 received the chat message from Client 2
    assert client1_result[0] == message_text
    assert client1_result[1] == client2.fingerprint