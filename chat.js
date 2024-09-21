const ws = new WebSocket("ws://localhost:6789");
let counter = 0;  // Monotonically increasing counter
let username = prompt("Enter your username:");
let publicKey = "Public Key Placeholder";  // Placeholder for public key
let clientPublicKeys = {};  // Dictionary to store public keys keyed by client identifier

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
            "username": username,
            "public_key": publicKey
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

ws.onmessage = async (event) => {
    const chatbox = document.getElementById("chatbox");

    try {
        const parsedMessage = JSON.parse(event.data);

        if (parsedMessage.data && parsedMessage.data.type === "chat") {
            const iv = Uint8Array.from(atob(parsedMessage.data.iv), c => c.charCodeAt(0));
            const encryptedMessage = Uint8Array.from(atob(parsedMessage.data.chat), c => c.charCodeAt(0));
            const encryptedKey = Uint8Array.from(atob(parsedMessage.data.symm_keys[0]), c => c.charCodeAt(0));

            // Decrypt the AES key
            const aesKey = await window.crypto.subtle.decrypt(
                {
                    name: "RSA-OAEP",
                },
                keyPair.privateKey,
                encryptedKey
            );

            // Decrypt the message
            const decryptedMessage = await window.crypto.subtle.decrypt(
                {
                    name: "AES-GCM",
                    iv: iv,
                },
                aesKey,
                encryptedMessage
            );

            const decoder = new TextDecoder();
            const message = decoder.decode(decryptedMessage);

            const messageElement = document.createElement("div");
            messageElement.textContent = message;
            chatbox.appendChild(messageElement);
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
        const errorMessage = document.createElement("div");
        errorMessage.textContent = "System Info: " + event.data;
        chatbox.appendChild(errorMessage);
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
    const recipientDropdown = document.getElementById("recipientDropdown");
    const selectedRecipient = recipientDropdown.value;

    if (!selectedRecipient) {
        alert("Please select a recipient.");
        return;
    }

    const message = `${username}: ${input.value}`;
    
    counter += 1;  // Increment counter for replay prevention
    
    // Generate AES key and IV
    const aesKey = await generateAESKey();
    const iv = window.crypto.getRandomValues(new Uint8Array(12));  // AES-GCM IV is 12 bytes

    // Encrypt the message
    const encryptedMessage = await encryptMessage(aesKey, iv, message);
    const encryptedMessageBase64 = btoa(String.fromCharCode(...encryptedMessage));

    // Encrypt the AES key for the selected recipient
    const publicKey = clientPublicKeys[selectedRecipient];
    const encryptedKey = await encryptAESKey(aesKey, publicKey);
    const encryptedKeyBase64 = btoa(String.fromCharCode(...encryptedKey));

    // Construct the chat message payload
    const chatMessage = {
        "type": "signed_data",
        "data": {
            "type": "chat",
            "destination_servers": [selectedRecipient],  // Send to the selected recipient
            "iv": btoa(String.fromCharCode(...iv)),
            "symm_keys": [encryptedKeyBase64],
            "chat": encryptedMessageBase64
        },
        "counter": counter,
        "signature": await signMessage(keyPair.privateKey, message, counter)
    };

    console.log(`Sending encrypted message with counter: ${counter}`);
    ws.send(JSON.stringify(chatMessage));
    input.value = "";  // Clear input after sending
}

async function requestClientList() {
    let client_list = {
        "type": "client_list_request",
    }

    ws.send(JSON.stringify(client_list));
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
