const ws = new WebSocket("ws://localhost:6789");
let counter = 0;  // Monotonically increasing counter
let username = prompt("Enter your username:");
let clientPublicKeys = {};  // Dictionary to store public keys keyed by client identifier
let encryptionPublicKey = "Public Key Placeholder";  // Placeholder for public key
let signingPublicKey = "Public Key Placeholder";  // Placeholder for public key
let encryptionKeyPair;
let signingKeyPair;

// RSA-OAEP key pair
async function generateKeyPair() {
    encryptionKeyPair = await window.crypto.subtle.generateKey({
        name: "RSA-OAEP",
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: "SHA-256"
    }, true, ["encrypt", "decrypt"]);

    // Export the public key in PEM format
    const publicKeyBuffer = await window.crypto.subtle.exportKey("spki", encryptionKeyPair.publicKey);
    encryptionPublicKey = convertBinaryToPem(publicKeyBuffer, "PUBLIC KEY");
}

// RSA-PSS signing key pair
async function generateSigningKeyPair() {
    signingKeyPair = await window.crypto.subtle.generateKey({
        name: "RSA-PSS",
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: "SHA-256"
    }, true, ["sign", "verify"]);

    // Export the public key in PEM format
    const publicKeyBuffer = await window.crypto.subtle.exportKey("spki", signingKeyPair.publicKey);
    signingPublicKey = convertBinaryToPem(publicKeyBuffer, "PUBLIC KEY");
}

// Helper function to convert a buffer to a PEM formatted string
function convertBinaryToPem(binaryData, label) {
    const base64String = btoa(String.fromCharCode(...new Uint8Array(binaryData)));
    const pemString = `-----BEGIN ${label}-----\n${base64String.match(/.{1,64}/g).join("\n")}\n-----END ${label}-----`;
    return pemString;
}

ws.onopen = async () => {
    console.log("Connected to the WebSocket server");

    // Generate RSA key pair
    await generateKeyPair();
    await generateSigningKeyPair();

    // Send hello message with the actual public key
    let helloMessage = {
        "type": "signed_data",
        "data": {
            "type": "hello",
            "username": username,
            "public_key": encryptionPublicKey
        },
        "counter": counter,
        "signature": "<Base64 signature of data + counter>"  // Signature not required for "hello"
    };
    ws.send(JSON.stringify(helloMessage));
};

async function generateAESKey() {
    return window.crypto.subtle.generateKey(
        {
            name: "AES-GCM",
            length: 256,
        },
        true,
        ["encrypt", "decrypt"]
    );
}

async function encryptMessage(aesKey, iv, message) {
    const encoder = new TextEncoder();
    const encodedMessage = encoder.encode(message);
    const ciphertext = await window.crypto.subtle.encrypt(
        {
            name: "AES-GCM",
            iv: iv,
        },
        aesKey,
        encodedMessage
    );
    return new Uint8Array(ciphertext);
}

async function encryptAESKey(aesKey, publicKeyPem) {
    const publicKey = await window.crypto.subtle.importKey(
        "spki",
        convertPemToBinary(publicKeyPem),
        {
            name: "RSA-OAEP",
            hash: "SHA-256",
        },
        true,
        ["encrypt"]
    );
    const exportedKey = await window.crypto.subtle.exportKey("raw", aesKey);
    const encryptedKey = await window.crypto.subtle.encrypt(
        {
            name: "RSA-OAEP",
        },
        publicKey,
        exportedKey
    );
    return new Uint8Array(encryptedKey);
}

function convertPemToBinary(pem) {
    const base64 = pem.replace(/-----BEGIN [^-]+-----|-----END [^-]+-----|\s+/g, '');
    const binary = atob(base64);
    const buffer = new ArrayBuffer(binary.length);
    const view = new Uint8Array(buffer);
    for (let i = 0; i < binary.length; i++) {
        view[i] = binary.charCodeAt(i);
    }
    return buffer;
}

async function decryptMessage(encryptedMessageBase64, encryptedKeyBase64, ivBase64) {
    try {
        // Decode Base64 encoded values
        const iv = Uint8Array.from(atob(ivBase64), c => c.charCodeAt(0));
        const encryptedMessage = Uint8Array.from(atob(encryptedMessageBase64), c => c.charCodeAt(0));
        const encryptedKey = Uint8Array.from(atob(encryptedKeyBase64), c => c.charCodeAt(0));

        console.log('IV:', iv);
        console.log('Encrypted Message:', encryptedMessage);
        console.log('Encrypted Key:', encryptedKey);

        // Decrypt the AES key
        const decryptedKeyBuffer = await window.crypto.subtle.decrypt(
            {
                name: "RSA-OAEP",
            },
            encryptionKeyPair.privateKey,
            encryptedKey
        );

        console.log('Decrypted AES Key Buffer:', decryptedKeyBuffer);

        // Import the decrypted AES key
        const aesKey = await window.crypto.subtle.importKey(
            "raw",
            decryptedKeyBuffer,
            {
                name: "AES-GCM",
            },
            true,
            ["decrypt"]
        );

        console.log('Imported AES Key:', aesKey);

        // Decrypt the message
        const decryptedMessage = await window.crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv: iv,
            },
            aesKey,
            encryptedMessage
        );

        console.log('Decrypted Message:', decryptedMessage);

        const decoder = new TextDecoder();
        return decoder.decode(decryptedMessage);
    } catch (error) {
        console.error('Error during decryption:', error);
        throw error;
    }
}

ws.onmessage = async (event) => {
    const chatbox = document.getElementById("chatbox");

    try {
        const parsedMessage = JSON.parse(event.data);
        console.log("Received message:", parsedMessage);

        if (parsedMessage.data && parsedMessage.data.type === "chat") {
            console.log('Processing chat message');
            const ivBase64 = parsedMessage.data.iv;
            const encryptedMessageBase64 = parsedMessage.data.chat;
            
            // Find the correct encrypted key for the current user
            const recipientUsername = username;  // Assume the current user is the recipient
            const recipientIndex = parsedMessage.data.destination_servers.indexOf(recipientUsername);
            if (recipientIndex === -1) {
                console.error('Recipient not found in destination servers');
                return;
            }
            const encryptedKeyBase64 = parsedMessage.data.symm_keys[recipientIndex];

            console.log('IV Base64:', ivBase64);
            console.log('Encrypted Message Base64:', encryptedMessageBase64);
            console.log('Encrypted Key Base64:', encryptedKeyBase64);

            try {
                const decryptedMessage = await decryptMessage(encryptedMessageBase64, encryptedKeyBase64, ivBase64);
                console.log(`Decrypted message: ${decryptedMessage}`);

                const messageElement = document.createElement("div");
                messageElement.textContent = decryptedMessage;
                chatbox.appendChild(messageElement);
            } catch (error) {
                console.error('Error decrypting message:', error);
            }
        } else if (parsedMessage.type === "client_list") {
            const clientListContainer = document.createElement("div");
            clientListContainer.innerHTML = "<strong>Client Public Keys:</strong><br>";

            const recipientDropdown = document.getElementById("recipientDropdown");
            recipientDropdown.innerHTML = '<option value="">Select a recipient</option>';  // Clear existing options

            parsedMessage.servers[0].clients.forEach(client => {
                const clientKey = document.createElement("div");
                clientKey.textContent = `${client.username}: ${client.publicKey}`;
                clientListContainer.appendChild(clientKey);

                // Store the public key
                clientPublicKeys[client.username] = client.publicKey;

                // Add option to dropdown
                const option = document.createElement("option");
                option.value = client.username;
                option.textContent = client.username;  // Display client username
                recipientDropdown.appendChild(option);
            });
            chatbox.appendChild(clientListContainer);
        } else {
            const infoMessage = document.createElement("div");
            infoMessage.textContent = "Info: " + parsedMessage.data;
            chatbox.appendChild(infoMessage);
        }
    } catch (e) {
        console.error('Error processing message:', e);
        const errorMessage = document.createElement("div");
        errorMessage.textContent = "System Info: " + event.data;
        chatbox.appendChild(errorMessage);
    }
};

// Function to sign the message using the private key
async function signMessage(privateKey, data, counter) {
    // Convert data object to JSON string
    const dataString = JSON.stringify(data);
    
    // Concatenate data string and counter
    const message = dataString + counter;
    
    // Create SHA-256 hash of the message
    const encoder = new TextEncoder();
    const messageBuffer = encoder.encode(message);
    const hashBuffer = await window.crypto.subtle.digest('SHA-256', messageBuffer);
    
    // Sign the hash using the private key with RSA-PSS
    const signatureBuffer = await window.crypto.subtle.sign(
        {
            name: 'RSA-PSS',
            saltLength: 32
        },
        privateKey,
        hashBuffer
    );
    
    // Encode the signature in Base64 format
    const signatureArray = new Uint8Array(signatureBuffer);
    const signatureBase64 = btoa(String.fromCharCode(...signatureArray));
    
    return signatureBase64;
}

async function sendMessage() {
    const input = document.getElementById("message");
    const recipientDropdown = document.getElementById("recipientDropdown");
    const selectedRecipients = Array.from(recipientDropdown.selectedOptions).map(option => option.value);

    if (selectedRecipients.length === 0) {
        alert("Please select at least one recipient.");
        return;
    }

    if (!signingKeyPair) {
        alert("Signing key pair not initialized.");
        return;
    }

    const message = `${username}: ${input.value}`;
    
    counter += 1;  // Increment counter for replay prevention
    
    // Generate AES key and IV
    const aesKey = await generateAESKey();
    const iv = window.crypto.getRandomValues(new Uint8Array(12));  // AES-GCM IV is 12 bytes

    // Encrypt the message
    const encryptedMessage = await encryptMessage(aesKey, iv, message);
    const encryptedMessageBase64 = btoa(String.fromCharCode(...new Uint8Array(encryptedMessage)));

    // Encrypt the AES key for each selected recipient
    const encryptedKeysBase64 = await Promise.all(selectedRecipients.map(async recipient => {
        const publicKey = clientPublicKeys[recipient];
        const encryptedKey = await encryptAESKey(aesKey, publicKey);
        return btoa(String.fromCharCode(...new Uint8Array(encryptedKey)));
    }));

    // Log the encrypted message and keys
    console.log("Encrypted Message (Base64):", encryptedMessageBase64);
    console.log("Encrypted AES Keys (Base64):", encryptedKeysBase64);

    // Construct the chat message payload
    const data = {
        "type": "chat",
        "destination_servers": selectedRecipients,  // Send to the selected recipients
        "iv": btoa(String.fromCharCode(...new Uint8Array(iv))),
        "symm_keys": encryptedKeysBase64,
        "chat": encryptedMessageBase64
    };
    const chatMessage = {
        "type": "signed_data",
        "data": data,
        "counter": counter,
        "signature": await signMessage(signingKeyPair.privateKey, data, counter)
    };

    console.log(`Sending encrypted message with counter: ${counter}`);
    ws.send(JSON.stringify(chatMessage));
    input.value = "";  // Clear input after sending

    // Append the message to the chat box
    const chatbox = document.getElementById("chatbox");
    const messageElement = document.createElement("div");
    messageElement.textContent = message;
    chatbox.appendChild(messageElement);
}

async function requestClientList() {
    let client_list = {
        "type": "client_list_request",
    }

    ws.send(JSON.stringify(client_list));
}