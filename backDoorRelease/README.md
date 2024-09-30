# Execution
## Environment
- It is recommended to use **Python 3.12** to run the code.
- Please update [HERE](https://www.python.org/).
## Run the code
- **Navigate all terminals to the folder which contains `app.py`, `server.py` and `client.py`**.
### Server
- In one terminal, run:
    ```
    python3 server.py
    ```
- You will then be asked to enter a **Host Address**. For the first address, we recommend to use `127.0.0.1`.
- You then need to enter the **Host port**. For the first port, we recommend to use `8000`.
- You then need to enter the **websocket for flask server**. If it is the first one, *ignore* this and simply click <kbd>enter</kbd>.
- If you know there exists other servers, input `y`, otherwise, `N` (Be careful about the capital and small letter).
### Client
- In another terminal, run:
    ```
    python3 client.py
    ```
- You will be asked to enter the **address** that your server has. i.e. for the first one, you could enter `127.0.0.1`.
- Then enter the **port number** (i.e.`8000`).
- Done! You can now choose your actions!
    > 1. Request client list
    > 2. Send message
    > 3. Upload file
    > 4. Download file
    > 5. Quit

# Current List of Backdoors
## Arbitrary code execution (Done)
- In `app.py` in from lines 28 to 31, there is an unchecked system call which will work for either Unix or Windows machines.
- You can execute arbitrary command by making a request to upload a file and ensure that the file name is ending in either `;{some_mallicous_command}` for servers running on Unix like systems or `&&{some_mallicous_command}` for Windows system replacing `{some_mallicous_command}` with a OS command.
- A harmless example is to create a file called `file;ls>SomeFile.txt ` and attempt to upload it through a client You will see that you will create a file named `SomeFile.txt` where all the files in the directory have been listed.

## Buffer Overflow (Pending)
- Might be a bit hard in Python

## Backdoor Key (Done)
- Idea: We could use a small key on the client side e.g. one with an int size of 2 to then encrypt a message. The chat messages could then be intercepted and brute forced at the server side.
- This has been done in `clinet.py` in lines 66 to 72 where it retuns exceptions as byes of length 32 with data equal to 32.
- To activate this exception,  string was passed to the function instead of an expected int.
- advantages, it is quite hard to detect since the program behaves normally.
- To verify this works, copy and paste the following: 
    ``` 
    bytes = 32
    key = bytes.to_bytes((bytes.bit_length() + 7) // 8, byteorder='big').ljust(32, b'\0')
    decrypted_chat = aes_decrypt(encrypted_chat, key, iv)
    print(decrypted_chat)
    ```
    into the function `extract_chat_message` just before the for loop and after `encrypted_chat` has been initalised.
