import crypto from 'crypto';
import WebSocket from 'ws';
import { v4 as uuidv4 } from 'uuid';

// Configuration
const API_KEY = "419f4d571f75936998447c2af41691c0d4dafe3af0fff58f85d64623660a0f79";
const VARIABLES = ["temperature", "humidity", "pressure"];

// State Variables
let NODE_ID, connection_key, bind_sec, device_id;
let stream_id, stream_url;
let token_id, token;
let ws = null;

/**
 * Generates the SHA256 signature for Anedya WebSocket Auth
 */
function generateAnedyaSignature(token, timestamp, requestBody = "") {
    const bodyHash = crypto.createHash('sha256').update(requestBody).digest();
    
    // Create an 8-byte big-endian buffer for the timestamp
    const tsBuffer = Buffer.alloc(8);
    tsBuffer.writeBigUInt64BE(BigInt(timestamp));
    
    const sigVersionBytes = Buffer.from("v1");
    const tokenBytes = Buffer.from(token);

    const combined = Buffer.concat([bodyHash, tsBuffer, sigVersionBytes, tokenBytes]);
    return crypto.createHash('sha256').update(combined).digest('hex');
}

async function createNode() {
    const url = "https://api.anedya.io/v1/node/create";
    const payload = {
        node_name: "Stream Test Node JS",
        node_desc: "Node created from JS script for stream testing.",
        tags: [{ key: "Key1", value: "1.00" }],
        preAuthorize: false,
    };

    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const info = await resp.json();
    NODE_ID = info.nodeId;

    // Get Node Details
    const detailsUrl = "https://api.anedya.io/v1/node/details";
    const detailsResp = await fetch(detailsUrl, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ nodes: [NODE_ID] })
    });
    const details = await detailsResp.json();
    
    connection_key = details.data[NODE_ID].connectionKey;
    bind_sec = details.data[NODE_ID].nodebindingkey;
    device_id = uuidv4();
}

async function createStream() {
    const url = "https://api.anedya.io/v1/streams/create";
    const payload = {
        sources: { nodes: [NODE_ID] },
        events: ["valuestore::updates", "valuestore::delete", "events::nodeevents"],
        variables: VARIABLES,
        expiry: 86400,
    };

    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const info = await resp.json();
    stream_id = info.streamId;
    stream_url = info.streamURL;
}

async function createAccessToken() {
    const url = "https://api.anedya.io/v1/access/tokens/create";
    const payload = {
        ttlSec: 2629746,
        policy: {
            resources: {
                nodes: [NODE_ID],
                variables: ["*"],
                vsglobalscopes: ["*"],
                vskeys: ["*"],
                streams: [stream_id],
            },
            allow: [
                "data::getsnapshot", "data::getlatest", "data::gethistorical",
                "cmd::sendcommand", "cmd::listcommands", "cmd::getstatus",
                "cmd::invalidate", "vs::getvalue", "vs::setvalue",
                "vs::scankeys", "vs::deletekeys", "streams::connect",
                "health::gethbstats", "health::getstatus",
            ],
        },
    };

    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${API_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const info = await resp.json();
    token_id = info.tokenId;
    token = info.token;
}

async function bindDevice() {
    const url = "https://device.ap-in-1.anedya.io/v1/bindDevice";
    const payload = { deviceid: device_id, bindingsecret: bind_sec };

    const resp = await fetch(url, {
        method: 'POST',
        headers: { "Auth-mode": "key", "Authorization": connection_key, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const info = await resp.json();
    console.log(info.success ? "Device bound successfully" : "Device binding failed");
}

async function submitData(variable, value) {
    const url = "https://device.ap-in-1.anedya.io/v1/submitData";
    const payload = {
        data: [{ variable: variable, value: value, timestamp: 0 }]
    };

    const resp = await fetch(url, {
        method: 'POST',
        headers: { "Auth-mode": "key", "Authorization": connection_key, 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const info = await resp.json();
    console.log("Submit data response:", JSON.stringify(info));
}

function connectWS() {
    return new Promise((resolve) => {
        const timestamp = Math.floor(Date.now() / 1000);
        const signature = generateAnedyaSignature(token, timestamp);

        const headers = {
            "Authorization": "ANEDYASIGV1",
            "x-anedya-streamid": stream_id,
            "x-anedya-tokenid": token_id,
            "x-anedya-signature": signature,
            "x-anedya-timestamp": timestamp.toString(),
            "x-anedya-signatureversion": "v1",
        };

        ws = new WebSocket(stream_url, { headers });

        ws.on('open', () => {
            console.log(`CONNECTED! ${new Date().toISOString()}`);
            resolve();
        });

        ws.on('message', (data) => {
            console.log("Stream MSG:", data);
        });

        ws.on('error', (err) => console.error("WS ERROR:", err));
        
        ws.on('close', () => {
            console.log("CLOSED. Reconnecting...");
            setTimeout(connectWS, 2000);
        });
    });
}

// Main Execution Flow
async function main() {
    try {
        console.log("Creating node...");
        await createNode();
        console.log(`Node ID: ${NODE_ID}`);

        console.log("Creating stream...");
        await createStream();

        console.log("Creating access token...");
        await createAccessToken();

        console.log("Connecting to WebSocket...");
        await connectWS();

        console.log("Binding device...");
        await bindDevice();

        // Data Submission Loop
        setInterval(async () => {
            await submitData(VARIABLES[0], 25.0);
        }, 2000);

    } catch (error) {
        console.error("Initialization failed:", error);
    }
}

main();