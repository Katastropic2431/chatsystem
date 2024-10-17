# Current List of Backdoors
This folder contains the backdoored version of the chat application. Under no circumstances should this be used for any real world application!

## Arbitrary code execution (Done)
- In `app.py` in from lines 28 to 31, there is an unchecked system call which will work for either Unix or Windows machines.
- You can execute arbitrary command by making a request to upload a file and ensure that the file name is ending in either `;{some_mallicous_command}` for servers running on Unix like systems or `&&{some_mallicous_command}` for Windows system replacing `{some_mallicous_command}` with a OS command.
- A harmless example is to create a file called `file;ls>SomeFile.txt` and attempt to upload it through a client You will see that you will create a file named `SomeFile.txt` where all the files in the directory have been listed.

## Backdoor Key (Done)
- Idea: We could use a small key on the client side e.g. one with an int size of 2 to then encrypt a message. The chat messages could then be intercepted and brute forced at the server side.
- This has been done in `clinet.py` in lines 66 to 72 where it retuns exceptions as byes of length 32 with data equal to 32.
- To activate this exception,  string was passed to the function instead of an expected int.
- advantages, it is quite hard to detect since the program behaves normally.
- To verify this works, copy and paste the following: 
    ``` 
    bytes = 16
    key = bytes.to_bytes((bytes.bit_length() + 7) // 8, byteorder='big').ljust(16, b'\0')
    decrypted_chat = aes_decrypt(encrypted_chat, key, iv)
    print(decrypted_chat)
    ```
    into the function `extract_chat_message` just before the for loop and after `encrypted_chat` has been initalised.
