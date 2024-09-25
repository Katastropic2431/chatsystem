# chatsystem
This Advanced Secure Programming assignment is designed to help students apply the theoretical concepts covered in the lectures/RangeForce and learn about practice secure programming. This assignment is a group work assignment.  In groups of 2-4 students, you will engage in a hands-on assignment that requires the design, development, and evaluation of a secure overlay chat system utilising a standardised protocol created by all the students in this class. This system must adhere to class-specified protocol, have a secure implementation, have the secured implementation intentionally and ethically "backdoored", and then be tested in a controlled code review process. The course concludes with a friendly hackathon exercise.

Currently the code is only tested with python 3.12.

## Execution

Installation
```
pip install websockets
``````

Open your terminal, navigate to the folder containing your main.html, and run:

```
python3 -m http.server 8000
```

Then open browser then go to:
```
http://localhost:8000/main.html
```

Open your terminal, navigate to the `src` and run:
```
python server.py
```
Then open another terminal to run:
```
http://localhost:8000/main.html
```
Run server with:
```
python3 server.py
```
