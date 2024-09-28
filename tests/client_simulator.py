import websockets
import asyncio
import json
from Crypto.PublicKey import RSA


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

        # wait for other clients to send hello
        for hello_event in others_hello_events:
            await hello_event.wait()

        await self.client.request_client_list(websocket)
        message = await websocket.recv()
        message_json = json.loads(message)
        self.client.cache_client_info(message_json)
        my_request_client_list_event.set()

        for request_event in others_request_client_list_events:
            await request_event.wait()


    async def quit(self):
        await self.websocket.close()


    async def recv_message(self):
        # Listen for incoming chat messages
        print('listening for message')
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
    

    async def send_message(self, message_text, recipient_public_keys=None):
        if recipient_public_keys is None:
            await self.client.send_public_message(self.websocket, message_text)
        else:
            # Send a chat message to the recipient using the public key
            await self.client.send_chat_message(
                self.websocket,
                [self.client.server_uri],
                recipient_public_keys, 
                message_text
            )

        await self.websocket.recv()


    async def simulate_relay_attack(self, messages, recipient_public_keys):
        await self.send_message(messages[0], recipient_public_keys)
        self.client.counter = 0
        await self.send_message(messages[1], recipient_public_keys)


    async def send_multiple_chat_messages(self, messages, recipient_public_keys):
        for message in messages:
            await self.client.send_chat_message(
                self.websocket,
                [self.client.server_uri],
                recipient_public_keys,
                message
            )


    async def send_multiple_messages_and_listen(
        self, 
        messages: list[str],
        recipient_public_keys: list[RSA.RsaKey],
    ):
        result, _ = await asyncio.gather(
            self.recv_multiple_messages(len(messages) * 2),
            self.send_multiple_chat_messages(
                messages,
                recipient_public_keys
            )
        )
        return result
