"""
Proyek Mini - Dashboard Node-RED untuk Kontrol Relay dan Monitoring Suhu
Perangkat IoT simulasi (pengganti ESP32) berbasis Python.

Fungsi:
1. Mengirim suhu (simulasi DHT22) setiap 3 detik
2. Menerima perintah relay "ON"/"OFF" -> GPIO 26
3. Menerima nilai PWM 0-255 -> kecerahan LED di GPIO 2
4. Mengirim feedback status relay dan PWM ke dashboard
"""
import time
import random
import threading
import paho.mqtt.client as mqtt

# ================= KONFIGURASI =================
NIM = "2410010503"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_CLIENT_ID = f"PythonDevice-{NIM}"

TOPIC_SUHU = f"iot/{NIM}/sensor/suhu"
TOPIC_RELAY = f"iot/{NIM}/aktuator/relay"
TOPIC_PWM = f"iot/{NIM}/aktuator/pwm"
TOPIC_STATUS_RELAY = f"iot/{NIM}/status/relay"
TOPIC_STATUS_PWM = f"iot/{NIM}/status/pwm"

INTERVAL_PUBLISH = 3  # detik
PIN_RELAY = 26
PIN_LED_PWM = 2

# ================= GPIO (asli jika di Raspberry Pi, simulasi jika tidak) =================
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_RELAY, GPIO.OUT)
    GPIO.setup(PIN_LED_PWM, GPIO.OUT)
    pwm_led = GPIO.PWM(PIN_LED_PWM, 1000)  # 1 kHz
    pwm_led.start(0)
    GPIO_ASLI = True
except (ImportError, RuntimeError):
    GPIO_ASLI = False
    print("[GPIO] RPi.GPIO tidak tersedia, memakai mode simulasi")

# ================= STATE GLOBAL =================
relay_state = "OFF"
pwm_value = 0


def set_relay(state):
    """Kendalikan relay di GPIO 26."""
    if GPIO_ASLI:
        GPIO.output(PIN_RELAY, GPIO.HIGH if state == "ON" else GPIO.LOW)
    print(f"[GPIO {PIN_RELAY}] Relay -> {state}")


def set_pwm(value):
    """Kendalikan kecerahan LED di GPIO 2 (nilai 0-255)."""
    if GPIO_ASLI:
        pwm_led.ChangeDutyCycle(value / 255 * 100)
    persen = round(value / 255 * 100)
    print(f"[GPIO {PIN_LED_PWM}] PWM -> {value}/255 ({persen}%)")


# ================= CALLBACK MQTT =================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Terhubung ke broker")
        client.subscribe(TOPIC_RELAY, qos=0)
        client.subscribe(TOPIC_PWM, qos=0)
        print(f"[MQTT] Subscribe: {TOPIC_RELAY}")
        print(f"[MQTT] Subscribe: {TOPIC_PWM}")
    else:
        print(f"[MQTT] Gagal terhubung, kode: {rc}")


def on_message(client, userdata, msg):
    global relay_state, pwm_value
    payload = msg.payload.decode("utf-8").strip()
    print(f"[MQTT] Pesan masuk [{msg.topic}]: {payload}")

    if msg.topic == TOPIC_RELAY:
        if payload in ("ON", "1"):
            relay_state = "ON"
        elif payload in ("OFF", "0"):
            relay_state = "OFF"
        else:
            print(f"[RELAY] Perintah tidak dikenal: {payload}")
            return
        set_relay(relay_state)
        client.publish(TOPIC_STATUS_RELAY, relay_state, qos=0)

    elif msg.topic == TOPIC_PWM:
        try:
            nilai = int(float(payload))
        except ValueError:
            print(f"[PWM] Nilai tidak valid: {payload}")
            return
        if not 0 <= nilai <= 255:
            print(f"[PWM] Di luar rentang 0-255: {nilai}")
            return
        pwm_value = nilai
        set_pwm(pwm_value)
        client.publish(TOPIC_STATUS_PWM, str(pwm_value), qos=0)


def on_disconnect(client, userdata, rc):
    print(f"[MQTT] Terputus (kode: {rc}). Mencoba reconnect...")


# ================= PEMBACAAN SENSOR =================
def baca_suhu():
    """
    Simulasi DHT22. Untuk DHT22 asli di Raspberry Pi, ganti dengan:
        import Adafruit_DHT
        hum, temp = Adafruit_DHT.read_retry(Adafruit_DHT.DHT22, 4)
        return round(temp, 2) if temp is not None else None
    """
    return round(27.0 + random.uniform(-1.5, 1.5), 2)


def publish_loop(client):
    """Kirim suhu setiap INTERVAL_PUBLISH detik."""
    while True:
        try:
            suhu = baca_suhu()
            if suhu is not None:
                client.publish(TOPIC_SUHU, str(suhu), qos=0)
                print(f"[SENSOR] Publish suhu: {TOPIC_SUHU} -> {suhu} C")
        except Exception as e:
            print(f"[SENSOR] Error: {e}")
        time.sleep(INTERVAL_PUBLISH)


# ================= MAIN =================
def main():
    client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    print(f"[MQTT] Menghubungkan ke {MQTT_BROKER}:{MQTT_PORT}...")
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()
    time.sleep(1)

    set_relay(relay_state)
    set_pwm(pwm_value)

    publisher = threading.Thread(target=publish_loop, args=(client,), daemon=True)
    publisher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[MAIN] Menghentikan program...")
        client.loop_stop()
        client.disconnect()
        if GPIO_ASLI:
            pwm_led.stop()
            GPIO.cleanup()


if __name__ == "__main__":
    main()