# Current List of Backdoors
## Arbitrary code execution (done)
- In `app.py` in from lines 28 to 31, there is an unchecked system call which will work for either Unix or Windows machines.
- You can execute arbitrary command by making a request to upload a file and ensure that the file name is ending in either `;{some_mallicous_command}` for servers running on Unix like systems or `&&{some_mallicous_command}` for Windows system replacing `{some_mallicous_command}` with a OS command.
- A harmless example is to create a file called `file;ls>SomeFile.txt ` and attempt to upload it through a client You will see that you will create a file named `SomeFile.txt` where all the files in the directory have been listed.

## Buffer Overflow (pending)
- Might be a bit hard in Python

## Backdoor Key (pending)
- We could use a small key on the client side e.g. one with an int size of 2 to then encrypt a message. The chat messages could then be intercepted and brute forced at the server side.