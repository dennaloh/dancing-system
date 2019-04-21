import pandas as pd
from feature_extraction import extract
from sklearn.externals import joblib
import numpy as np

import serial
import collections
from collections import Counter
import time
import os
import socket
import base64
import sys
from Crypto.Cipher import AES
from Crypto import Random
import RPi.GPIO as GPIO

#Initialization for Arduino
GPIO.setmode(GPIO.BOARD)
GPIO.setup(40, GPIO.OUT)
duinoConnectionEstablished = False
port = "/dev/ttyS0"
s1 = serial.Serial(port, baudrate=115200)
val = 0
handshake = 0
checksumPi = 0

#Initialization for Power
cumPower = 0

#Initialization for Server
VERBOSE = False
sock = None
serverConnectionEstablished = False
paddedData = ""
Key = 'please give us A'
secret_key = bytes(str(Key), encoding = "utf8")

if len(sys.argv) != 3 :
    print('Invalid number of arguments')
    print('python3 myclient.py [IP address] [Port]')
    sys.exit()

IP_ADDRESS = sys.argv[1]
IP_PORT = int(sys.argv[2])

#Initialization for ML
buffer = []
bufferSize = 50
enterML = False
temp2X = 999
temp2Y = 999
temp2Z = 999
pred_arr = []

moves = {
1: 'raffles',
2: 'chicken',
3: 'crab',
4: 'hunchback',
5: 'cowboy',
6: 'mermaid',
7: 'doublepump',
8: 'runningman',
9: 'snake',
10: 'jamesbond',
11: 'logout_haha'
}
scaler_chu = joblib.load('scaler_17april_logout.joblib')
scaler_df = joblib.load('scaler_df.joblib')
mlp_chu = joblib.load('mlp_17april_logout.joblib')
mlp_df = joblib.load('model_df.joblib')

#ML
def extract_features(segment):
    data = np.asarray(extract(np.asarray(segment)))
    data = np.array([data])
    data_chu = scaler_chu.transform(data)
    data_df = scaler_df.transform(data)

    return data_chu, data_df

def predict(segment):
    extracted_features_chu, extracted_features_df = extract_features(segment)
    extracted_features_chu = np.nan_to_num(extracted_features_chu)
    extracted_features_df = np.nan_to_num(extracted_features_df)
    mlp_chu_pred = int(mlp_chu.predict(extracted_features_chu))
    mlp_df_pred = int(mlp_df.predict_classes(extracted_features_df))+1
    pred_arr.append(mlp_chu_pred)
    pred_arr.append(mlp_df_pred)
    mode, num_mode = Counter(pred_arr).most_common(1)[0]

    if (num_mode>=3):
        final_pred = moves.get(mode)
        return final_pred

    return 'another segment'

#Sensor Readings Processing
def calcCheckSum(arr, volt, curr):
    checksum = arr[0] ^ arr[1]
    for i in range(2, len(arr)) :
        checksum = checksum ^ arr[i]
    checksum = checksum ^ int(volt*10)
    checksum = checksum ^ int(curr*10)
    return checksum

def createReadingArr(x1, y1, z1, x2, y2, z2, x3, y3, z3):
    arr = []
    arr.append(x1)
    arr.append(y1)
    arr.append(z1)
    arr.append(x2)
    arr.append(y2)
    arr.append(z2)
    arr.append(x3)
    arr.append(y3)
    arr.append(z3)
    return arr

#Server
def debug(text):
    if VERBOSE:
        print ("Debug:---", text)

def sendMSG(msg):
    debug("sendMSG() with msg")
    try:
        sock.sendall(msg)
    except:
        debug("Exception in sendMSG()")
        closeConnection()

def closeConnection():
    global serverConnectionEstablished
    debug("Closing socket")
    sock.close()
    serverConnectionEstablished = False

def connect(IP_ADDRESS, IP_PORT):
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    debug("Connecting to Server...")
    try:
        sock.connect((IP_ADDRESS, IP_PORT))
    except:
        debug("Connection to Server failed.")
        return False
    return True

def formStr(act, volt, curr, pow, cumPow):
    return '#' + str(act) + '|' + str(volt) + '|' + str(curr) + '|' + str(pow) + '|' + str(cumPow) + '|'

def encodeStr(data):
    extra = len(data) % 16
    if extra > 0 :
        paddedData = (' ' * (16 - extra)) + data

        iv = Random.new().read(AES.block_size) # GENERATING INITIAL VECTOR
        cipher = AES.new(secret_key,AES.MODE_CBC,iv) # CREATING CIPHER
        encryptedMSG = iv + cipher.encrypt(paddedData)
        return base64.b64encode(encryptedMSG)


#Reset Arduino
GPIO.output(40, GPIO.HIGH)
time.sleep(1)
GPIO.output(40, GPIO.LOW)
time.sleep(1)
GPIO.cleanup()
print("Arduino resetted!")

s1.flushInput()

#HANDSHAKE
while handshake == 0 :
    s1.write(b'0')
    print("Sent request")
    time.sleep(1)
    if s1.in_waiting > 0 :
        val = s1.read(1).decode("utf-8")
        if val == '1' :
            print("Received ACK: " + val)
            handshake = 1
while handshake == 1 :
    s1.write(b'1')
    print("Sent ACK of ACK")
    time.sleep(1)
    if s1.in_waiting > 0 :
        handshake = 2
        duinoConnectionEstablished = True
        print("handshake=2")

prevTime = time.time()

#START MAIN
if duinoConnectionEstablished and connect(IP_ADDRESS,IP_PORT):
    serverConnectionEstablished = True
    print ("Connection to Server established")
    s1.flushInput()
    print("Starting loop now")

    while serverConnectionEstablished:
        while len(buffer) < bufferSize :
            if s1.in_waiting :
                try:
                    val = s1.read_until().decode("utf-8")
                except:
                    print("SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED SKIPPED")
                    val = s1.read_until().decode("utf-8", "ignore")
                    continue
                val = val[:-1]
                #print("msg = " + val)

                if val.startswith("#") :
                    val = val.lstrip('#')
                    try:
                        sensor1 = val.split('|')[0]
                        sensor1x = int(sensor1.split(',')[0])
                        sensor1y = int(sensor1.split(',')[1])
                        sensor1z = int(sensor1.split(',')[2])
                        sensor2 = val.split('|')[1]
                        sensor2x = int(sensor2.split(',')[0])
                        sensor2y = int(sensor2.split(',')[1])
                        sensor2z = int(sensor2.split(',')[2])
                        sensor3 = val.split('|')[2]
                        sensor3x = int(sensor3.split(',')[0])
                        sensor3y = int(sensor3.split(',')[1])
                        sensor3z = int(sensor3.split(',')[2])
                        voltage = float(val.split('|')[3])
                        current = float(val.split('|')[4])
                        checksumDuino = int(val.split('|')[5])
                    except ValueError or IndexError:
                        print("ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR ERROR")
                        continue
                    #print("voltage = " + str(voltage))
                    #print("current = " + str(current))
                    #print("checksumDuino = " + str(checksumDuino))

                    if enterML == False:
                        buffer = []

                        if temp2X == 999 and temp2Y == 999 and temp2Z == 999:
                            temp2X = sensor2x
                            temp2Y = sensor2y
                            temp2Z = sensor2z
                        else:
                            if abs(sensor2x - temp2X) >= 15 or abs(sensor2y - temp2Y) >= 15 or abs(sensor2z - temp2Z) >= 15 :
                                enterML = True

                    dataIntArr = createReadingArr(sensor1x, sensor1y, sensor1z, sensor2x, sensor2y, sensor2z, sensor3x, sensor3y, sensor3z)
                    checksumPi = calcCheckSum(dataIntArr, voltage, current)

                    if checksumPi == checksumDuino :
                        buffer.append(dataIntArr) # Store in buffer

        if enterML == True:
            action = predict(buffer)
            if action == 'another segment' :
                buffer = buffer[20:]
                continue

            #Power Calculation
            power = current*voltage
            currTime = time.time()
            intervalTime = currTime - prevTime
            intervalTime = intervalTime/3600
            cumPower = cumPower + (power*intervalTime)
            prevTime = currTime

            string = formStr(action, voltage, current, power, cumPower)
            encodedMSG = encodeStr(string)
            print ("Sending action: %s" % action)
            sendMSG(encodedMSG)

            time.sleep(1.5)
            buffer = []
            pred_arr = []
        s1.flushInput()

else:
    print ("Connection to %s:%d failed" % (IP_ADDRESS, IP_PORT))
closeConnection()
print ("done")
