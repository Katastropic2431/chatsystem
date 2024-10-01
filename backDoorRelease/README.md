# Execution
## Environment
- It is recommended to use **Python 3.12** to run the code.
- Please update [HERE](https://www.python.org/).
## To start with...
- **Whenever you start a new terminal, please navigate the path to the folder which contains `app.py`, `server.py` and `client.py`**.
- *First* type in
    ```
    pip install -r requirements.txt
    ```
    You will then have all libraries needed to run the program.
## Server
- In one terminal, run:
    ```
    python3 server.py
    ```
- You will then be asked to enter a **Host Address**. For the first address, we recommend to use `127.0.0.1`.
- You then need to enter the **Host port**. For the first port, we recommend to use `8000`.
- You then need to enter the **websocket for flask server**. If it is the first one, *ignore* this and simply click <kbd>enter</kbd>.
- If you know there exists other servers, input `y`, otherwise, `N` (Be careful about the capital and small letter).
## Client
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

## File transfer
### Upload
- Please enter the **absolute full path** of the file.
### Download
- Please enter a format like `http//127.0.0.1/uploads/api/{filename}` where `127.0.0.1` is the **sender's Host address** in this case.
- The file will be downloaded to `/tmp/downloads/`.