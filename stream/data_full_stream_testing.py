import hashlib
import json
import requests
import websocket
import time
import threading
import sys
import signal
import uuid

API_KEY = "9c25088b112905873537f8eb5079d71d26602975f1e8d6e18db30bcd99178673"

# Global websocket object
ws_app = None
ws_thread = None
stop_flag = False


def create_node():
    global NODE_ID, connection_key, bind_sec, device_id
    url = "https://api.anedya.io/v1/node/create"
    payload = {
        "node_name": "testnode52",
        "node_desc": "Node created from python.",
        "tags": [{"key": "Key1", "value": "1.00"}],
        "preAuthorize": False,
    }
    body_str = json.dumps(payload)
    # print("Creating node with payload:", json.dumps(payload, indent=2))
    headers = {"Authorization": f"Bearer {API_KEY}"}

    resp = requests.post(url, data=body_str, headers=headers)
    info = resp.json()
    # print("Bindind operation response:", json.dumps(info, indent=2))
    NODE_ID = info.get("nodeId", "")

    # Get node info
    url = "https://api.anedya.io/v1/node/details"
    payload = {"nodes": [NODE_ID]}
    body_str = json.dumps(payload)
    # print("Creating node with payload:", json.dumps(payload, indent=2))
    headers = {"Authorization": f"Bearer {API_KEY}"}

    resp = requests.post(url, data=body_str, headers=headers)
    info = resp.json()
    # print("Node details:", json.dumps(info, indent=2))
    # connection_key= info["nodes"][0]["connectionKey"]
    connection_key = info["data"][NODE_ID]["connectionKey"]
    bind_sec = info["data"][NODE_ID]["nodebindingkey"]
    device_id = str(uuid.uuid4())


def create_stream():
    global stream_id, stream_url
    url = "https://api.anedya.io/v1/streams/create"

    payload = {
        "sources": {"nodes": [NODE_ID]},
        "events": ["valuestore::updates", "valuestore::delete", "events::nodeevents"],
        "expiry": 86400,
    }
    body = json.dumps(payload)
    headers = {"Authorization": f"Bearer {API_KEY}"}
    resp = requests.post(url, data=body, headers=headers)
    info = resp.json()
    # print("Stream creation response:", json.dumps(info, indent=2))
    stream_id = info["streamId"]
    stream_url = info["streamURL"]


def create_access_token():
    global token_id, token
    url = "https://api.anedya.io/v1/access/tokens/create"

    payload = {
        "ttlSec": 2629746,
        "policy": {
            "resources": {
                "nodes": [NODE_ID],
                "variables": ["*"],
                "vsglobalscopes": ["*"],
                "vskeys": ["*"],
                "streams": [stream_id],
            },
            "allow": [
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
    }
    body = json.dumps(payload)
    headers = {"Authorization": f"Bearer {API_KEY}"}
    resp = requests.post(url, data=body, headers=headers)
    info = resp.json()
    # print("Access token response:", json.dumps(info, indent=2))
    token_id = info["tokenId"]
    token = info["token"]


def bind_device():
    url = "https://device.ap-in-1.anedya.io/v1/bindDevice"
    payload = {"deviceid": str(device_id), "bindingsecret": str(bind_sec)}
    body_str = json.dumps(payload)
    # print("Binding device with payload:", json.dumps(payload, indent=2))
    headers = {"Auth-mode": "key", "Authorization": connection_key}

    resp = requests.post(url, data=body_str, headers=headers)
    info = resp.json()
    # print("Bindind operation response:", json.dumps(info, indent=2))
    if info.get("success", False):
        print("Device bound successfully\n")
    else:
        print("Device binding failed :", json.dumps(info, indent=2))


def set_key():
    url = "https://device.ap-in-1.anedya.io/v1/valuestore/setValue"
    payload = {
        "reqId": "",
        "key": "nodeKey1",
        "value": "Value set from python client",
        "type": "string",
    }
    headers = {
        "Auth-mode": "key",
        "Authorization": connection_key,
    }
    body_str = json.dumps(payload)

    resp = requests.post(url, data=body_str, headers=headers)
    info = resp.json()
    print("Set key operation response:", json.dumps(info))


def submit_data(variable_identifier, value, timestamp=0):
    url = "https://device.ap-in-1.anedya.io/v1/submitData"
    payload = {
        "data": [
            {"variable": variable_identifier, "value": value, "timestamp": timestamp}
        ]
    }
    headers = {
        "Auth-mode": "key",
        "Authorization": connection_key,
    }
    body_str = json.dumps(payload)
    print(body_str)

    resp = requests.post(url, data=body_str, headers=headers)
    info = resp.json()
    print("Submit data operation response:", json.dumps(info))


def generate_anedya_signature(token: str, timestamp: int, request_body=None):
    if request_body is None:
        body_hash = hashlib.sha256(b"").digest()
    else:
        body_hash = hashlib.sha256(request_body.encode()).digest()

    timestamp_bytes = timestamp.to_bytes(8, "big", signed=False)
    sig_version_bytes = b"v1"
    token_bytes = token.encode()

    combined = body_hash + timestamp_bytes + sig_version_bytes + token_bytes
    return hashlib.sha256(combined).hexdigest()


connected = False


def on_open(ws):
    global connected
    connected = True
    print(f"CONNECTED! {time.strftime('%Y-%m-%d %H:%M:%S')}")


def connect_ws():
    global ws_app

    timestamp = int(time.time())
    signature = generate_anedya_signature(token, timestamp)

    ws_headers = [
        "Authorization: ANEDYASIGV1",
        f"x-anedya-streamid: {stream_id}",
        f"x-anedya-tokenid: {token_id}",
        f"x-anedya-signature: {signature}",
        f"x-anedya-timestamp: {timestamp}",
        "x-anedya-signatureversion: v1",
    ]

    print("\nConnecting with headers:")
    print("\n".join(ws_headers), "\n")

    ws_app = websocket.WebSocketApp(
        stream_url,
        header=ws_headers,
        on_message=lambda ws, msg: print("MSG:", msg),
        on_error=lambda ws, e: print("ERROR:", e),
        on_close=lambda ws, a, b: print("CLOSED", a, b),
        on_open=on_open,
    )

    ws_app.run_forever()


def start_ws_thread():
    global ws_thread, stop_flag
    stop_flag = False
    ws_thread = threading.Thread(target=connect_ws)
    ws_thread.daemon = True
    ws_thread.start()


def reconnect():
    print("\n🔄 Reconnecting to WebSocket...\n")
    time.sleep(1)
    start_ws_thread()


def handle_keyboard_interrupt(signum, frame):
    global ws_app, ws_thread, stop_flag

    print("\n\n⚠️  KeyboardInterrupt detected!")
    print("Closing connection and reconnecting...\n")

    stop_flag = True

    try:
        if ws_app:
            ws_app.close()
    except:
        pass

    time.sleep(1)
    reconnect()


# Attach Ctrl+C handler
signal.signal(signal.SIGINT, handle_keyboard_interrupt)


# Keep main thread alive
while True:
    time.sleep(1)
    print("Creating node...")
    create_node()
    print("Node created with id:", NODE_ID)
    print(f"Connection key: {connection_key}")
    print(f"Binding secret: {bind_sec}")
    print(f"Generated Device id: {device_id}")

    print("Creating stream...")
    create_stream()
    print("Stream created with id:", stream_id)
    print("Stream URL:", stream_url)

    print("Creating access token...")
    create_access_token()
    print("Access token created with id:", token_id)
    print("Access token:", token)

    print("\nConnecting to WebSocket...")
    # Start First Connection
    start_ws_thread()

    while not connected:
        time.sleep(1)

    print("\nDevice is connected. Proceeding with bind and set key operations...")
    bind_device()

    for _ in range(10):
        # set_key()
        submit_data("temperature", 25.00, 0)
        time.sleep(2)
        print("")
    while True:
        time.sleep(1)
