import websockets
import asyncio
import json
from Crypto.PublicKey import RSA


async def setup_simulators(clients):
    hello_events = [asyncio.Event() for _ in range(len(clients))]
    request_client_list_events = [asyncio.Event() for _ in range(len(clients))]
    
    simulators, setup_tasks = [], []
    for i, client in enumerate(clients):
        simulator = ClientSimulator(client)
        other_hello_events = hello_events[:i] + hello_events[i+1:]
        other_request_client_list_events = request_client_list_events[:i] + request_client_list_events[i+1:]
        # Send hello and client list request to server,
        # and wait for other clients to finish
        setup = simulator.setup(
            hello_events[i],
            other_hello_events,
            request_client_list_events[i],
            other_request_client_list_events
        )

        simulators.append(simulator)
        setup_tasks.append(setup)

    await asyncio.gather(*setup_tasks)
    return simulators


async def close_connections(simulators):
    for s in simulators:
        await s.quit()


class ClientSimulator:
    def __init__(self, client):
        self.client = client
        self.websocket = None


    async def setup(
        self,
        my_hello_event: asyncio.Event,
        others_hello_events: list[asyncio.Event],
        my_request_client_list_event: asyncio.Event,
        others_request_client_list_events: list[asyncio.Event],
    ):
        websocket = await websockets.connect(self.client.server_uri)
        self.websocket = websocket
        
        # Send hello to server
        await self.client.send_hello(websocket)
        my_hello_event.set()

        # Wait for other clients to send hello
        for hello_event in others_hello_events:
            await hello_event.wait()
        
        await asyncio.sleep(1)

        # Send request_client_list to server
        await self.client.request_client_list(websocket)
        message = await websocket.recv()
        message_json = json.loads(message)
        self.client.cache_client_info(message_json)
        my_request_client_list_event.set()

        # Wait for other clients to send request_client_list
        for request_event in others_request_client_list_events:
            await request_event.wait()


    async def quit(self):
        await self.websocket.close()


    async def recv_message(self):
        # Listen for incoming chat messages
        message = await self.websocket.recv()
        message_json = json.loads(message)
        if message_json["data"]["type"] == "chat":
            text, sender = self.client.extract_chat_message(message_json)
        elif message_json["data"]["type"] == "public_chat":
            text, sender = self.client.extract_public_chat(message_json)
        else:
            return None, None
        return text, sender
    

    async def recv_message_no_client_info(self):
        self.client.fingerprint_to_public_key = {}
        text, sender = await self.recv_message()
        return text, sender
    

    async def recv_multiple_messages(self, num_message):
        messages, senders = [], []
        for _ in range(num_message):
            text, sender = await self.recv_message()
            
            if text is not None:
                messages.append(text)
            if sender is not None:
                senders.append(sender)    
        
        return messages, senders
    

    async def send_message(self, message_text, server_uri_list=None, recipient_public_keys=None):
        if recipient_public_keys is None:
            await self.client.send_public_message(self.websocket, message_text)
        else:
            # Send a chat message to the recipient using the public key
            await self.client.send_chat_message(
                self.websocket,
                server_uri_list,
                recipient_public_keys, 
                message_text
            )
    

    async def send_message_and_listen(self, message_text, server_uri_list=None, recipient_public_keys=None):
        await self.send_message(message_text, server_uri_list, recipient_public_keys)
        await self.websocket.recv()


    async def sleep_and_send_message(self, message_text, server_uri_list, recipient_public_keys):
        # wait for another client to quit
        await asyncio.sleep(1)
        await self.send_message_and_listen(message_text, server_uri_list, recipient_public_keys)


    async def simulate_relay_attack(self, messages, server_uri_list, recipient_public_keys):
        await self.send_message_and_listen(messages[0], server_uri_list, recipient_public_keys)
        self.client.counter = 0
        await self.send_message_and_listen(messages[1], server_uri_list, recipient_public_keys)


    async def send_multiple_chat_messages(self, messages, server_uri_list, recipient_public_keys):
        for message in messages:
            await self.client.send_chat_message(
                self.websocket,
                server_uri_list,
                recipient_public_keys,
                message
            )


    async def send_multiple_messages_and_listen(
        self, 
        messages: list[str],
        server_uri_list: list[str],
        recipient_public_keys: list[RSA.RsaKey],
    ):
        result, _ = await asyncio.gather(
            self.recv_multiple_messages(len(messages) * 2),
            self.send_multiple_chat_messages(
                messages,
                server_uri_list,
                recipient_public_keys
            )
        )
        return result
