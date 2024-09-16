const ws = new WebSocket("ws://localhost:6789");
let counter = 0;  // Monotonically increasing counter
let username = prompt("Enter your username:");
let publicKey = "Public Key Placeholder";  // Placeholder for public key

// Function to update the recipient list dynamically
function updateRecipientList(users) {
    const recipientSelect = document.getElementById("recipient");
    recipientSelect.innerHTML = '';  // Clear the current options

    // Add an option to broadcast to everyone
    const broadcastOption = document.createElement("option");
    broadcastOption.value = "broadcast";
    broadcastOption.textContent = "Broadcast (everyone)";
    recipientSelect.appendChild(broadcastOption);

    // Add other users to the select element
    users.forEach(user => {
        const option = document.createElement("option");
        option.value = user.id;  // Assuming user has a unique 'id' field
        option.textContent = user.name || user.id;  // Use name or id
        recipientSelect.appendChild(option);
    });
}

ws.onopen = async () => {
    console.log("Connected to the WebSocket server");

    // Generate RSA key pair
    keyPair = await generateKeyPair();
    publicKey = keyPair.publicKeyPem;  // Assign the exported public key

    // Send hello message with the actual public key
    let helloMessage = {
        "type": "signed_data",
        "data": {
            "type": "hello",
            "public_key": publicKey
        },
        "counter": counter,
        "signature": "<Base64 signature of data + counter>"  // Signature not required for "hello"
    };
    ws.send(JSON.stringify(helloMessage));
};

ws.onmessage = (event) => {
    const chatbox = document.getElementById("chatbox");

    try {
        // Try to parse the incoming message as JSON
        const parsedMessage = JSON.parse(event.data);

        // Check the type of the message and display only the relevant content
        if (parsedMessage.data && parsedMessage.data.type === "chat") {
            const message = document.createElement("div");
            message.textContent = parsedMessage.data.message;  // Display the chat message content
            chatbox.appendChild(message);
        } else {
            // For non-chat messages, you could log them or show them differently
            const infoMessage = document.createElement("div");
            infoMessage.textContent = "Info: " + parsedMessage.data;  // Handle non-chat messages
            chatbox.appendChild(infoMessage);
        }
    } catch (e) {
        // If the message is not valid JSON, handle it as a plain text message 
        const systemMessage = document.createElement("div");
        systemMessage.textContent = event.data;  // Display the plain text message
        chatbox.appendChild(systemMessage);
    }
};


// Function to sign the message using the private key
async function signMessage(privateKey, message, counter) {
    const encoder = new TextEncoder();
    const dataToSign = encoder.encode(message + counter);

    // Use RSA-PSS for signing, not RSA-OAEP
    const signature = await window.crypto.subtle.sign(
        {
            name: "RSA-PSS",
            saltLength: 32,  // Recommended salt length for RSA-PSS
        },
        privateKey,
        dataToSign
    );

    // Return the Base64-encoded signature
    return btoa(String.fromCharCode(...new Uint8Array(signature)));  
}


async function sendMessage() {
    const input = document.getElementById("message");
    const message = `${username}: ${input.value}`;
    
    counter += 1;  // Increment counter for replay prevention
    
    // Sign the message + counter
    const signature = await signMessage(keyPair.privateKey, message, counter);

    let chatMessage = {
        "type": "signed_data",
        "data": {
            "type": "chat",
            "message": message
        },
        "counter": counter,
        "signature": signature
    };
    console.log(`Sending message with counter: ${counter}`);

    ws.send(JSON.stringify(chatMessage));
    input.value = "";  // Clear input after sending
}

// Function to generate RSA key pair and export them in PEM format
async function generateKeyPair() {
    const keyPair = await window.crypto.subtle.generateKey({
        name: "RSA-PSS",
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: "SHA-256"
    }, true, ["sign", "verify"]);

    // Export the public key in PEM format
    const publicKeyBuffer = await window.crypto.subtle.exportKey("spki", keyPair.publicKey);
    const publicKeyPem = convertBinaryToPem(publicKeyBuffer, "PUBLIC KEY");

    // Export the private key
    const privateKeyBuffer = await window.crypto.subtle.exportKey("pkcs8", keyPair.privateKey);
    const privateKeyPem = convertBinaryToPem(privateKeyBuffer, "PRIVATE KEY");

    return { publicKeyPem, privateKey: keyPair.privateKey };
}

// Helper function to convert a buffer to a PEM formatted string
function convertBinaryToPem(binaryData, label) {
    const base64String = btoa(String.fromCharCode(...new Uint8Array(binaryData)));
    const pemString = `-----BEGIN ${label}-----\n${base64String.match(/.{1,64}/g).join("\n")}\n-----END ${label}-----`;
    return pemString;
}

let keyPair;
generateKeyPair().then(keys => {
    keyPair = keys;
    console.log("Keys generated!", keys);
});
