import sys
import os
import time
import paho.mqtt.client as mqtt
import ssl
import json
import tempfile


REGION_CODE = "ap-in-1"
PHYSICAL_DEVICE_ID = "e95cf8e2-8cc7-4ccf-9236-211342a5fc68"
CONNECTION_KEY = "79acfdbbd334cc8f3e14d7daca3d1471"
HEARTBEAT_INTERVAL = 10                # 5 minutes (in seconds)

cert = """
-----BEGIN CERTIFICATE-----
MIICDDCCAbOgAwIBAgITQxd3Dqj4u/74GrImxc0M4EbUvDAKBggqhkjOPQQDAjBL
MQswCQYDVQQGEwJJTjEQMA4GA1UECBMHR3VqYXJhdDEPMA0GA1UEChMGQW5lZHlh
MRkwFwYDVQQDExBBbmVkeWEgUm9vdCBDQSAzMB4XDTI0MDEwMTAwMDAwMFoXDTQz
MTIzMTIzNTk1OVowSzELMAkGA1UEBhMCSU4xEDAOBgNVBAgTB0d1amFyYXQxDzAN
BgNVBAoTBkFuZWR5YTEZMBcGA1UEAxMQQW5lZHlhIFJvb3QgQ0EgMzBZMBMGByqG
SM49AgEGCCqGSM49AwEHA0IABKsxf0vpbjShIOIGweak0/meIYS0AmXaujinCjFk
BFShcaf2MdMeYBPPFwz4p5I8KOCopgshSTUFRCXiiKwgYPKjdjB0MA8GA1UdEwEB
/wQFMAMBAf8wHQYDVR0OBBYEFNz1PBRXdRsYQNVsd3eYVNdRDcH4MB8GA1UdIwQY
MBaAFNz1PBRXdRsYQNVsd3eYVNdRDcH4MA4GA1UdDwEB/wQEAwIBhjARBgNVHSAE
CjAIMAYGBFUdIAAwCgYIKoZIzj0EAwIDRwAwRAIgR/rWSG8+L4XtFLces0JYS7bY
5NH1diiFk54/E5xmSaICIEYYbhvjrdR0GVLjoay6gFspiRZ7GtDDr9xF91WbsK0P
-----END CERTIFICATE-----
"""

RES_TOPIC = f"$anedya/device/{PHYSICAL_DEVICE_ID}/response"
ERR_TOPIC = f"$anedya/device/{PHYSICAL_DEVICE_ID}/errors"
COMM_TOPIC = f"$anedya/device/{PHYSICAL_DEVICE_ID}/commands"
UPDATE_STATUS_TOPIC = f"$anedya/device/{PHYSICAL_DEVICE_ID}/commands/updateStatus/json"


def on_connect(client, userdata, flags, reasonCode, properties):
    print(f"Connected with Anedya (MQTT v5) Reason Code: {reasonCode}")
    client.subscribe(RES_TOPIC)
    client.subscribe(ERR_TOPIC)
    client.subscribe(COMM_TOPIC)


def on_message(client, userdata, msg):
    global mqtt_received_command
    payload = msg.payload.decode()
    print(f"Received message: {payload}")

    try:
        message = json.loads(payload)
        command_id = message.get("commandId")
        command = message.get("command")
        data = message.get("data")
        # print(mqtt_received_command)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")


def connect_to_anedya():
    global client
    broker = f"mqtt.{REGION_CODE}.anedya.io"
    print(f"Id: {PHYSICAL_DEVICE_ID}")
    print(CONNECTION_KEY)

    with tempfile.NamedTemporaryFile(
        delete=False, mode="w", suffix=".pem"
    ) as cert_file:
        cert_file.write(cert)
        cert_file_path = cert_file.name

    # Setup MQTT client
    client = mqtt.Client(client_id=PHYSICAL_DEVICE_ID, protocol=mqtt.MQTTv5)

    client.username_pw_set(username=PHYSICAL_DEVICE_ID, password=CONNECTION_KEY)

    # Setup SSL/TLS for secure connection using cert file
    client.tls_set(ca_certs=cert_file_path, tls_version=ssl.PROTOCOL_TLS)

    client.on_connect = on_connect
    client.on_message = on_message

    # Connect to MQTT broker
    client.connect(broker, port=8883, keepalive=60)

    # Start the network loop
    client.loop_start()


# -------------------------------------------------------------
# HEARTBEAT PUBLISH FUNCTION
# -------------------------------------------------------------
def publish_heartbeat():
    # reqId = random integer / slot number (Anedya firmwares use slot)
    req_id = "1"

    payload = {
        "reqId": req_id
    }

    topic = f"$anedya/device/{PHYSICAL_DEVICE_ID}/heartbeat/json"
    json_payload = json.dumps(payload)

    print(f"[MQTT] Publishing heartbeat → {topic}")
    print(f"Payload: {json_payload}")

    result = client.publish(topic, json_payload, qos=0, retain=False)

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print("[MQTT] Failed to publish heartbeat! rc =", result.rc)


if __name__ == "__main__":
    connect_to_anedya()
    time.sleep(2)
    while 1:
        publish_heartbeat()
        time.sleep(HEARTBEAT_INTERVAL)
