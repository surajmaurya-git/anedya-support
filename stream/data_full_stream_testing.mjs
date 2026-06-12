import crypto from "crypto";
import WebSocket from "ws";
import { v4 as uuidv4 } from "uuid";
import cbor from "cbor";

// Configuration
const API_KEY =
  "419f4d571f75936998447c2af41691c0d4dafe3af0fff58f85d64623660a0f79";
const VARIABLES = ["temperature", "humidity", "status"];

// State Variables
let NODE_ID, connection_key, bind_sec, device_id;
let stream_id, stream_url;
let token_id, token;
let ws = null;

/**
 * Parses and identifies incoming stream data using the exact protocol specification
 */
function handleIncomingStream(buffer) {
  if (buffer.length < 4) return; // Ensure we have headers + at least some payload data
  console.log("\n📥 Received Stream Data:", buffer.toString("hex"));

  const byte1 = buffer[0];
  const byte2 = buffer[1];
  const dataType = buffer[2];

  if (byte1 === 0x00 && byte2 === 0x02) {
    // ✅ Identifies Anedya Event Data
    try {
      const payload = buffer.slice(2);
      const decoded = cbor.decodeFirstSync(payload);

      console.log("📡 VALUESTORE DATA DETECTED:");
      console.log({
        nodeId: decoded?.ns?.id,
        scope: decoded?.ns?.scope,
        key: decoded?.key,
        value: decoded?.val,
        timestamp: decoded?.ts,
        type: decoded?.t,
      });
    } catch (err) {
      console.error("Failed to decode Event data:", err.message);
    }
  } else if (byte1 === 0x00 && byte2 === 0x01) {
    try {
      const payload = buffer.slice(3);
      const decoded = cbor.decodeFirstSync(payload);

      console.log("📊 VARIABLE DATA DETECTED:");
      console.log({
        nodeId: decoded?.n ? decoded.n.toString("hex") : undefined,
        variable: decoded?.v,
        value: decoded?.d,
        timestamp: decoded?.ts,
        dataType: dataType, // Includes the type flag from byte 3
      });
    } catch (err) {
      console.error("Failed to decode Variable data:", err.message);
    }
  } else {
    console.warn("Unknown message header type:", byte1, byte2);
  }
}

/**
 * Signature Helper
 */
function generateAnedyaSignature(token, timestamp, requestBody = "") {
  const bodyHash = crypto.createHash("sha256").update(requestBody).digest();
  const tsBuffer = Buffer.alloc(8);
  tsBuffer.writeBigUInt64BE(BigInt(timestamp));
  const sigVersionBytes = Buffer.from("v1");
  const tokenBytes = Buffer.from(token);

  const combined = Buffer.concat([
    bodyHash,
    tsBuffer,
    sigVersionBytes,
    tokenBytes,
  ]);
  return crypto.createHash("sha256").update(combined).digest("hex");
}

/**
 * REST API Provisioning calls
 */
async function createNode() {
  const url = "https://api.anedya.io/v1/node/create";
  const payload = {
    node_name: "Stream Test Node JS",
    node_desc: "Simple stream test script.",
    tags: [{ key: "Key1", value: "1.00" }],
    preAuthorize: false,
  };

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const info = await resp.json();
  NODE_ID = info.nodeId;

  const detailsUrl = "https://api.anedya.io/v1/node/details";
  const detailsResp = await fetch(detailsUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ nodes: [NODE_ID] }),
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
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
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
        "data::getsnapshot",
        "data::getlatest",
        "data::gethistorical",
        "cmd::sendcommand",
        "cmd::listcommands",
        "cmd::getstatus",
        "cmd::invalidate",
        "vs::getvalue",
        "vs::setvalue",
        "vs::scankeys",
        "vs::deletekeys",
        "streams::connect",
        "health::gethbstats",
        "health::getstatus",
      ],
    },
  };

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const info = await resp.json();
  token_id = info.tokenId;
  token = info.token;
}

async function bindDevice() {
  const url = "https://device.ap-in-1.anedya.io/v1/bindDevice";
  const payload = { deviceid: device_id, bindingsecret: bind_sec };

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Auth-mode": "key",
      Authorization: connection_key,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await resp.json();
  console.log("Device provisioned and bound successfully.");
}

async function submitData(variable, value) {
  const url = "https://device.ap-in-1.anedya.io/v1/submitData";
  const payload = {
    data: [{ variable: variable, value: value, timestamp: 0 }],
  };

  await fetch(url, {
    method: "POST",
    headers: {
      "Auth-mode": "key",
      Authorization: connection_key,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

function connectWS() {
  return new Promise((resolve) => {
    const timestamp = Math.floor(Date.now() / 1000);
    const signature = generateAnedyaSignature(token, timestamp);

    const headers = {
      Authorization: "ANEDYASIGV1",
      "x-anedya-streamid": stream_id,
      "x-anedya-tokenid": token_id,
      "x-anedya-signature": signature,
      "x-anedya-timestamp": timestamp.toString(),
      "x-anedya-signatureversion": "v1",
    };

    ws = new WebSocket(stream_url, { headers });

    ws.on("open", () => {
      console.log("WebSocket Connection Stream Established!");
      resolve();
    });

    ws.on("message", (data) => {
      handleIncomingStream(data);
    });

    ws.on("error", (err) => console.error("WS Error:", err.message));

    ws.on("close", () => {
      console.log("Stream closed. Attempting reconnect...");
      setTimeout(connectWS, 2000);
    });
  });
}

async function main() {
  try {
    console.log("Preparing Node, Stream, and Access Tokens...");
    await createNode();
    await createStream();
    await createAccessToken();
    await bindDevice();

    console.log("Initializing secure streams connection...");
    await Promise.all([
      connectWS()
    ]);

    // Periodically push subsequent telemetry
    console.log("\n🚀 Transmitting telemetry metric...");
    await submitData(VARIABLES[0], 25.0);
    setInterval(async () => {
      console.log("\n🚀 Transmitting telemetry metric...");
      await submitData(VARIABLES[0], 25.0);
    }, 3000);
  } catch (error) {
    console.error("Initialization Routine Error:", error);
  }
}

main();
