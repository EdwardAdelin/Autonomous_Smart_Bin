import network
import socket
import json
from machine import Pin, PWM, I2C, time_pulse_us
from time import sleep

# BMP280 driver code
class BMP280:
    def _init_(self, i2c, addr=0x76):
        self.i2c = i2c
        self.addr = addr
        self.dig_T1 = self._read16(0x88)
        self.dig_T2 = self._readS16(0x8A)
        self.dig_T3 = self._readS16(0x8C)
        self.t_fine = 0
        self._write(0xF4, 0x2F)
        self._write(0xF5, 0x0C)

    def _read16(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 2)
        return data[1] << 8 | data[0]

    def _readS16(self, reg):
        result = self._read16(reg)
        if result > 32767:
            result -= 65536
        return result

    def _write(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def _read24(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 3)
        return data[0] << 16 | data[1] << 8 | data[2]

    def temperature(self):
        adc_T = self._read24(0xFA) >> 4
        var1 = (((adc_T >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
        var2 = (((((adc_T >> 4) - self.dig_T1) * ((adc_T >> 4) - self.dig_T1)) >> 12) * self.dig_T3) >> 14
        self.t_fine = var1 + var2
        T = (self.t_fine * 5 + 128) >> 8
        return T / 100

# WiFi credentials
SSID = 'DIGI-h5H2'
PASSWORD = 'NGGu55hf2F'

# Setup ultrasonic sensor pins
trigger = Pin(14, Pin.OUT)  # GPIO 14 for trigger
echo = Pin(15, Pin.IN)      # GPIO 15 for echo

# Setup LED pin
led = Pin(0, Pin.OUT)  # GPIO 25 for LED (adjust as needed)

# Setup buzzer pin
buzzer = Pin(1, Pin.OUT)  # GPIO 26 for buzzer (adjust as needed)

# Setup I2C for BMP280
i2c = I2C(1, scl=Pin(19), sda=Pin(18))
bmp280 = BMP280(i2c)

# Temperature offset (adjust based on your observations)
TEMPERATURE_OFFSET = 2.0

def measure_distance():
    # Clear trigger
    trigger.low()
    sleep(0.002)  # Wait 2ms to settle
    
    # Send 10μs trigger pulse
    trigger.high()
    sleep(0.00001)  # 10 microseconds
    trigger.low()
    
    # Measure echo pulse duration
    duration = time_pulse_us(echo, 1, 30000)  # 30ms timeout
    
    # Debug print
    print(f"Raw duration: {duration} microseconds")
    
    # Calculate distance
    if duration > 0:
        # Speed of sound = 343.2 m/s = 0.03432 cm/μs
        # Distance = (time * speed) / 2 (round trip)
        distance = (duration * 0.0343) / 2
        print(f"Calculated distance: {distance} cm")
        
        # Blink LED and buzz if distance is less than 6.5 cm
        if distance < 6.5:
            led.high()
            buzzer.high()
            return round(distance, 1), True
        else:
            led.low()
            buzzer.low()
            return round(distance, 1), False
    else:
        print("Error: No echo received")
        led.low()  # Turn off LED if no echo
        buzzer.low()  # Turn off buzzer if no echo
        return None, False

def read_temperature():
    temperature = bmp280.temperature()
    return temperature - TEMPERATURE_OFFSET

# Setup servo
servo = PWM(Pin(16))  # GPIO 16
servo.freq(50)

# WiFi connection
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

while not wlan.isconnected():
    print('Connecting to WiFi...')
    sleep(1)
print(f'Connected! IP: {wlan.ifconfig()[0]}')

# Setup webserver
s = socket.socket()
s.bind(('', 80))
s.listen(5)

# Main loop
while True:
    conn, addr = s.accept()
    request = conn.recv(1024).decode()
    print(f"Request: {request}")
    
    # Handle GET requests
    if 'GET /open' in request:
        servo.duty_u16(8000)  # Open position
        response = "Lid Opened"
    elif 'GET /close' in request:
        servo.duty_u16(1500)  # Closed position
        response = "Lid Closed"
    elif 'GET /sensor' in request:
        distance, is_full = measure_distance()
        temperature = read_temperature()
        sensor_data = {
            'distance': str(distance if distance is not None else "Error"),
            'full': is_full,
            'temperature': round(temperature, 2)
        }
        response = json.dumps(sensor_data)
        conn.send('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')
        conn.send(response)
    else:
        # Return the HTML content
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Smart Bin Control</title>
            <style>
                body {
                    text-align: center;
                    font-family: Arial, sans-serif;
                    background-color: #f4f4f9;
                    margin: 0;
                    padding: 0;
                }
                .container {
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #fff;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                    border-radius: 10px;
                }
                h1 {
                    color: #333;
                }
                .button {
                    padding: 15px 30px;
                    margin: 10px;
                    font-size: 18px;
                    color: #fff;
                    background-color: #007bff;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    transition: background-color 0.3s ease;
                }
                .button:hover {
                    background-color: #0056b3;
                }
                .sensor-data {
                    margin: 20px 0;
                    padding: 15px;
                    background-color: #f0f0f0;
                    border-radius: 5px;
                    font-size: 20px;
                }
                .full-message {
                    color: red;
                    font-size: 22px;
                    margin-top: 20px;
                }
                .bin {
                    position: relative;
                    width: 100px;
                    height: 200px;
                    margin: 20px auto;
                    background-color: #ddd;
                    border: 2px solid #333;
                    border-radius: 10px;
                    overflow: hidden;
                }
                .bin-fill {
                    position: absolute;
                    bottom: 0;
                    width: 100%;
                    height: 0;
                    background-color: #007bff;
                    transition: height 0.5s ease;
                }
            </style>
            <script>
                function updateSensorData() {
                    fetch('/sensor')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('distance').innerText = data.distance;
                            document.getElementById('temperature').innerText = data.temperature;
                            if (data.full) {
                                document.getElementById('full-message').innerText = "Bin is full!";
                            } else {
                                document.getElementById('full-message').innerText = "";
                            }
                            updateBinFill(data.distance);
                        });
                }

                function updateBinFill(distance) {
                    const binFill = document.querySelector('.bin-fill');
                    const maxDistance = 20; // Maximum distance for an empty bin
                    const minDistance = 8;  // Minimum distance for a full bin
                    let fillHeight = 0;

                    if (distance <= minDistance) {
                        fillHeight = 100;
                    } else if (distance < maxDistance) {
                        fillHeight = ((maxDistance - distance) / (maxDistance - minDistance)) * 100;
                    }

                    binFill.style.height = fillHeight + '%';
                }

                // Update every 2 seconds
                setInterval(updateSensorData, 2000);
            </script>
        </head>
        <body>
            <div class="container">
                <h1>Smart Bin Control</h1>
                <div class="sensor-data">
                    Fill Level: <span id="distance">Loading...</span> cm
                </div>
                <div class="sensor-data">
                    Temperature: <span id="temperature">Loading...</span>C
                </div>
                <div id="full-message" class="full-message"></div>
                <div class="bin">
                    <div class="bin-fill"></div>
                </div>
                <button class="button" onclick="fetch('/open',{method:'GET'})">Open Lid</button>
                <button class="button" onclick="fetch('/close',{method:'GET'})">Close Lid</button>
            </div>
        </body>
        </html>
        """
        conn.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        conn.send(html)
    
    conn.close()