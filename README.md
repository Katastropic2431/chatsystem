# Chatsystem
This Advanced Secure Programming assignment is designed to help students apply the theoretical concepts covered in the lectures/RangeForce and learn about practice secure programming. This assignment is a group work assignment.

## **Contact**
**You can contact us through the secure programming discord server or via email:**
- [stefan.parenti@student.adelaide.edu.au](mailto:stefan.parenti@student.adelaide.edu.au)
- [tun-hsiang.chou@student.adelaide.edu.au](mailto:tun-hsiang.chou@student.adelaide.edu.au)
- [nathan.do@student.adelaide.edu.au](mailto:nathan.do@student.adelaide.edu.au)
- [ruian.zhou@student.adelaide.edu.au](mailto:ruian.zhou@student.adelaide.edu.au)


**Discord Server (Secure Programming - protocol design):**
1. Nathan Do: Katastropic

## File Structure
The repository include four folders
```
src/                        # Src folders without any backdoors
├── client.py                   # Python client 
├── server.py                   # Python server
└── app.py                      # Flask server
backDoorRelease/            # Backdoor folder with 2 known backdoors 
├── client.py                   # Python client 
├── server.py                   # Python server
├── app.py                      # Flask server
└── README.md                   # Explains the backdoors we implemented
decrepcated/                # Decrepcated code that we aren't using due to difficulty with javaScript
├── chat.js                     # Python client 
├── client.py                   # Python server
├── main.html                   # Flask server
└── README.md                   # Explains how to run the decrepated code
tests/                      # Unit Test
├── client_simulator.py         # Simulator for client 
├── test_file_transfer.py       # Test for file transfers
├── test_multi_server.py        # Test for Multiple Servers
└── test_one_server.py          # Tests for one server
```

###

## Installation
This Assignment is using Python 3.12. It is recommended to use **Python 3.12** to run the code.
1. **Install Python 3.12**:
    - If you haven't installed Python 3.12, you can download it from the official [Python website](https://www.python.org/downloads/).

2. **Set up your environment**:
    - Navigate to the folder containing `app.py`, `server.py`, and `client.py` in your terminal.
    
3. **Install the required dependencies**:
    - Run the following command to install the necessary Python libraries listed in the `requirements.txt` file:
      ```bash
      pip install -r requirements.txt
      ```

Once you've completed these steps, you will have everything needed to run the program.

## Server
1. Open a terminal and run the following command:
    ```bash
    python3 server.py
    ```

2. You will be prompted to enter a **Host Address**. For the first time setup, we recommend using `127.0.0.1`.

3. Next, you will be asked to enter the **Host port for messages**. We suggest using `8000` for the initial configuration.

4. You will then be prompted to provide the **Host port for file transfer**. We suggest usng `5000` and hitting enter <kbd>Enter</kbd>.
    - After this is done, the public key of the server in base64 format will be outputted to the terminal. **Please take note of this** if you are are wanting to create a neighbourhood of servers.

5. If you are adding multiple servers to the neighbour hood please hit `y` and if not hit `n`.

6. If you are adding multiple servers to the neighbourhood, enter the addresses of any neighborhood servers in the form `{address}:{port}` and hit <kbd>Enter</kbd>. Then copy over the outputted public key in base64 format of the specified neighbouring server. Once finished adding all neighbouring server leave the field blank and hit <kbd>Enter</kbd> to start up the server.
    - Please note, once a server starts there is no way to add or remoove a new server to the neighbourhood. Please ensure that all servers are added at this step and ensure all addresses and public keys are correct.

## Client
1. Open another terminal and run the following command:
    ```bash
    python3 client.py
    ```

2. You will be prompted to enter the **address** of your server. This should **match** the address you used when starting the server, e.g., `127.0.0.1`.

3. Next, you will need to enter the **Messaging port number**, such as `8000`, which should **match** the port used by the server you are trying to connect to.

4. Then, enter the **File transfer port number** such as `5000` that you initially set when running `server.py`.

5. That’s it! You can now choose from the available actions:
    > 1. Request client list  
    > 2. Send message 
    > 3. Send public message
    > 4. Upload file  
    > 5. Download file  
    > 6. Quit

**Note:** To send 

## Example Workflow Setting Up 2 Server Neighbourhood
1. Open up **2 terminals**.
   
2. In **Terminal 1**, run `server.py`.

3. In **Terminal 1**, leave the address as `127.0.0.1` and hit <kbd>Enter</kbd>.

4. In **Terminal 1**, leave the message port on `8000` and hit <kbd>Enter</kbd>.

5. In **Terminal 1**, leave the file transfer port on `5000` and hit <kbd>Enter</kbd>.

6. In **Terminal 2**, run `server.py`.

7. In **Terminal 2**, leave the address as `127.0.0.1` and hit <kbd>Enter</kbd>.

8. In **Terminal 2**, change the message port to `8001` and hit <kbd>Enter</kbd>.

9. In **Terminal 2**, change the file transfer port to `5001` and hit <kbd>Enter</kbd>.

10. In **Terminal 2**, input the neighboring address as `127.0.0.1:8000` and hit <kbd>Enter</kbd>.

11. Copy the public key initially generated by **Terminal 1** into the input of **Terminal 2** and hit <kbd>Enter</kbd>.

12. In **Terminal 2**, hit <kbd>Enter</kbd> leaving the field blank, and the server should begin running.

13. In **Terminal 1**, input the neighboring address as `127.0.0.1:8001` and hit <kbd>Enter</kbd>.

14. Copy the public key initially generated by **Terminal 2** into the input of **Terminal 1** and hit <kbd>Enter</kbd>.

15. In **Terminal 1**, hit <kbd>Enter</kbd>, and the server should begin running.

---

If all that was done correctly, you should have **2 servers running in a neighborhood**. You can now add clients to both of them by making new terminals and connecting them to the respective addresses and ports.


### File Transfer (Extra Details)

1. **Upload**
   - Enter the **absolute full path** of the file you wish to upload.

2. **Download**
   - Enter the download URL in the format: `http://127.0.0.1:5000/uploads/api/{filename}`, where `127.0.0.1` is the **sender's host address** and `5000` is the **sender's host file transfer port**.
   - The downloaded file will be saved in the `/tmp/downloads/` directory.

## Test Overview

### Running the Tests

To run the tests, use the following command:

```bash
pytest tests
```

Use -k option for running a single test. For example,
```bash
pytest -k test_public_chat
```

### test_one_server.py
The test suite is designed to verify the correctness of client-server interactions in a WebSocket environment with one server.

#### Test Fixtures
   - **`run_server`**: This fixture initializes and runs the WebSocket server in a separate thread, ensuring it is available for all test cases. After the tests complete, the server is gracefully shut down.

#### Test Cases

- `test_single_client_send_hello_and_request_client_list`  
  This test simulates a single client connecting to the server, sending a "hello" message, and requesting the client list from the server. It asserts that the server responds with a list containing only the connecting client.

- `test_single_client_send_message_to_self`  
  A client connects to the server and sends a chat message to itself. The test ensures that the client receives its own message correctly, validating that the message content and sender are correct.

- `test_single_client_send_message_to_another_client`  
  Two clients connect to the server. Client 2 sends a message to Client 1, and the test verifies that Client 1 receives the message. The correct content and sender details are asserted.

- `test_message_from_unknown_sender`  
  This test ensures that if a message is received from an unknown client (i.e., a client whose public key is not cached), the system cannot verify the signature. The test confirms that both the message and sender are `None`.

- `test_third_client_does_not_receive_private_message`  
  When one client sends a private message to another, a third connected client should not receive the message. This test checks that only the intended recipient gets the message, and the third client receives no communication.

- `test_send_message_to_multiple_clients`  
  A client sends a message to multiple recipients (Client 1 and Client 3). The test confirms that both clients receive the message with the correct sender details.

- `test_multiturn_dialogue`  
  In this test, two clients engage in a multi-turn dialogue, each sending multiple messages. The test ensures that all messages are exchanged correctly and that both clients receive the expected sequence of messages.

- `test_public_chat`  
  This test simulates a public chat where a message is sent to all connected clients. The test ensures that all clients receive the public message from the sender.

- `test_check_for_relay_attack`  
  This test simulates a replay attack scenario where the same message is sent twice with an invalid counter. It verifies that the receiving client detects the replay attack and only processes the valid message.

- `test_send_message_to_offline_client`  
  The test validates that sending a message to an offline client does not cause any errors. The client attempts to send a message after the recipient has disconnected, ensuring that no exception occurs.

### test_multi_server.py
The tests verify the correctness of communication with more than one server.

#### Test Cases
- `test_client_send_message_to_another_client_on_two_servers`:
  Two clients connect to two different servers in a neighbourhood. Client 2 sends a message to Client 1, and the test verifies that Client 1 receives the message. The correct content and sender details are asserted.

### test_file_transfer.py
The test suite verifies both the success and error scenarios for uploading and retrieving files.

#### Test Cases
- `test_upload_file_success`  
  Tests successful file upload and verifies that the file is saved in the correct location.

- `test_upload_file_no_file`  
  Tests the scenario where no file is provided in the request.

- `test_upload_file_no_filename`  
  Tests the scenario where a file is uploaded with an empty filename.

- `test_get_file_success`  
  Verifies that an uploaded file can be successfully downloaded.

- `test_get_file_not_found`  
  Tests the case where a non-existent file is requested.

### client_simulator.py

The `ClientSimulator` class, defined in `tests/client_simulator.py`, is used to simulate client behavior during tests. It provides methods for setting up WebSocket connections, sending and receiving messages, and handling more advanced scenarios such as replay attacks and multi-client message distribution.

- `setup()`: Initializes a simulated client, sends a hello message, and requests the client list from the server. It also handles synchronization between multiple clients.
- `quit()`: Closes the WebSocket connection.
- `recv_message()`: Listens for incoming messages and extracts chat or public chat messages.
- `recv_multiple_messages()`: Waits for a specified number of messages to be received.
- `send_message()`: Sends either a private or public chat message to other clients.
- `simulate_relay_attack()`: Simulates a replay attack by sending a message with an invalid counter.
- `send_multiple_messages_and_listen()`: Sends multiple messages and listens for responses from other clients.
