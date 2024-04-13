#挿入ライブラリ
import time
from smbus2 import SMBus
import math
import datetime
import pigpio
import RPi.GPIO as GPIO  
from pyproj import Proj
import serial
import numpy as np
from micropyGPS import MicropyGPS

#初期設定==============
pi=pigpio.pi()#gpio設定
i2c = SMBus(1)#i2c設定

# ゴールのgps設定
#シゲさんの家
Lon0=139
Lat0=35
GOAL=[Lon0,Lat0]

#9軸のi2cアドレス
ACCL_ADDR = 0x19
ACCL_R_ADDR = 0x02
MAG_ADDR = 0x13
MAG_R_ADDR = 0x42

#9軸センサのセットアップ
def bmx_setup():
    # mag_data_setup : 地磁気値をセットアップ
    data = i2c.read_byte_data(MAG_ADDR, 0x4B)
    if(data == 0):
    i2c.write_byte_data(MAG_ADDR, 0x4B, 0x83)
    time.sleep(0.5)
    i2c.write_byte_data(MAG_ADDR, 0x4B, 0x01)
    i2c.write_byte_data(MAG_ADDR, 0x4C, 0x00)
    i2c.write_byte_data(MAG_ADDR, 0x4E, 0x84)
    i2c.write_byte_data(MAG_ADDR, 0x51, 0x04)
    i2c.write_byte_data(MAG_ADDR, 0x52, 0x16)
    time.sleep(0.5)
    
#取得した磁気の生データを変換
def mag_value():
    data = [0, 0, 0, 0, 0, 0, 0, 0]
    mag_data = [0.0, 0.0, 0.0]
    try:
        for i in range(8):
            data[i] = i2c.read_byte_data(MAG_ADDR, MAG_R_ADDR + i)
        for i in range(3):
            if i != 2:
                mag_data[i] = ((data[2*i + 1] * 256) + (data[2*i] & 0xF8)) / 8
                if mag_data[i] > 4095:
                    mag_data[i] -= 8192
            else:
                mag_data[i] = ((data[2*i + 1] * 256) + (data[2*i] & 0xFE)) / 2
                if mag_data[i] > 16383:
                    mag_data[i] -= 32768
    except IOError as e:
        print("I/O error({0}): {1}".format(e.errno, e.strerror))
    return mag_data

SERVO_PIN_R = 23
SERVO_PIN_L = 22
pi.set_mode(SERVO_PIN_R, pigpio.OUTPUT)#gpioのピン番号
pi.set_mode(SERVO_PIN_L, pigpio.OUTPUT)#gpioのピン番号
	
def fix():
    mag_data = []
    #ループ変数。v=0でlistのx成分v=1でlistのy成分を参照 
    v=0
    #0回目取得で無条件にmax,minにいれる
    i=0
    #最大値と最小値用,最終的なオフセット用リスト。x.y方向あるから各々2データ
    max_buffer = [0,0,0]
    min_buffer = [0,0,0] 
    fix_value = [0,0,0]

    #rangeの値は適当
    for value in range(40):
        mag_data = mag_value()
        
        #デバッグ
        print('mag_data:' ,(mag_data))

        #ここからmagのリストのインデックスを見てる
        while(v<2):

            #iが1週ごとに回るからtmpは配列である必要なし
            tmp = mag_data[v]

            #i==0。一番最初は何も入ってないから無条件でmaxとminに入る
            if(i==0):
                max_buffer[v] = tmp
                min_buffer[v] = tmp
            #1番最初以外はすでにmax.minに値が入ってるから判定してあげる
            else:
                if(tmp > max_buffer[v]):
                    max_buffer[v] = tmp
                if(tmp < min_buffer[v]):
                    min_buffer[v] = tmp
            v = v+1
        #v++の位置は間違えないように!(配列のインデックスがずれる)

        #デバッグ
        #print('max_buffer:' ,max_buffer)
        #print('min_buffer:' ,min_buffer)

        #後でいじる
        time.sleep(0.5)

        #リセット忘れずに。iで何回目か
        v=0
        i = i+1

    #v=0でリストのx成分。v=1でリストのy成分を参照するためのloop
    v=0
    while(v<2):
        fix_value[v] = (max_buffer[v] + min_buffer[v])/2
        v = v+1
    
    #終了処理
    print("Stop!!")
    

    return fix_value
  

"""
Servo_pin = 18                      #変数"Servo_pin"に18を格納

#GPIOの設定
GPIO.setmode(GPIO.BCM)              #GPIOのモードを"GPIO.BCM"に設定
GPIO.setup(Servo_pin, GPIO.OUT)     #GPIO18を出力モードに設定

#PWMの設定
#サーボモータSG90の周波数は50[Hz]
Servo = GPIO.PWM(Servo_pin, 50)     #GPIO.PWM(ポート番号, 周波数[Hz])

Servo.start(0)                      #Servo.start(デューティ比[0-100%])
"""

###################################GPS#################################################

def GPS():
    
    # シリアル通信設定
    uart = serial.Serial('/dev/serial0', 9600, timeout = 100)
    # gps設定
    my_gps = MicropyGPS(9, 'dd')
    
    # 10秒ごとに表示
    tm_last = 0
    while True:
        sentence = uart.readline()
        if len(sentence) > 0:
                for x in sentence:
                    if 20 <= x <= 126:
                        stat = my_gps.update(chr(x))
                        if stat:
                            tm = my_gps.timestamp
                            tm_now = (tm[0] * 3600) + (tm[1] * 60) + int(tm[2])
                            if (tm_now - tm_last) >= 10000:
                                print('=' * 20)
                                #print(my_gps.date_string(), tm[0], tm[1], int(tm[2]))
                                #print("latitude:", my_gps.latitude[0], ", longitude:", my_gps.longitude[0])
                                
                                Lon=np.array([Lon0,my_gps.longitude[0]])
                                Lat=np.array([Lat0,my_gps.latitude[0]])
                                a=np.array([Lon0,Lat0])
                                b=np.array([my_gps.longitude[0],my_gps.latitude[0]])
                                
                                    
                                #print("radian",type(np.arctan2(vec[0],vec[1])))
                                radian = np.arctan2(vec[0],vec[1])
                                KOKO=(my_gps.latitude[0],my_gps.longitude[0])
                                dis0=geodesic(GOAL,KOKO).m
                                angle = 180*radian/math.pi
                                Lon1=my_gps.longitude[0]
                                Lat1=my_gps.latitude[0]
                                #result = distance.vincenty_inverse(Lat1, Lon1, Lat0, Lon0, 1)
                                #print("kyori:",dis)
                                #dis1=round(result['distance'], 3))
                                #angle=result['azimuth1'])
                                #print('方位角(終点→始点)：%s' % result['azimuth2'])
                                
    return Lon1,Lat1,angle,dis0


#相対位置角度
def pos(Lon1,Lat1):
    Lon=Lon0-Lon1
    Lat=Lat0-Lat1
    print("Lon,Lat->",end='')
    print(Lon,Lat)
    pos_theta_1=math.atan2(Lat,Lon)#範囲は-π〜π
    pos_theta=math.degrees(pos_theta_1)#範囲は-180~180
    return (pos_theta)

#キャリブレーション補正有り位置角度    
def sat(offsetx,offsety):
    magx=mag_value()[0]-offsetx
    magy=mag_value()[1]-offsety
    print("magx,magy->",end='')
    print(magx,magy)
    sat_theta_1=math.degrees(math.atan2(magy,magx))#範囲は-180〜180
    if sat_theta_1>-90 and sat_theta_1<0:
        sat_theta = sat_theta_1    
    elif sat_theta_1>90 and sat_theta_1<180:
        sat_theta = sat_theta_1  
    elif sat_theta_1>90 and sat_theta_1<180:
        sat_theta = sat_theta_1 +180
    else:
        sat_theta = sat_theta_1 -180 
    print(sat_theta)
    return (sat_theta)

SERVO_PIN_R = 23
SERVO_PIN_L = 22

GPIO.setmode(GPIO.BCM)              #GPIOのモードを"GPIO.BCM"に設定
GPIO.setup(SERVO_PIN_R, GPIO.OUT) 
GPIO.setup(SERVO_PIN_L, GPIO.OUT) 
ServoR = GPIO.PWM(SERVO_PIN_R, 50)#後でpigpioモジュールに直す  #GPIO.PWM(ポート番号, 周波数[Hz])
ServoL = GPIO.PWM(SERVO_PIN_L, 50) 
ServoR.start(0)  
ServoL.start(0)   

pi.set_mode(SERVO_PIN_R, pigpio.OUTPUT)#gpioのピン番号
pi.set_mode(SERVO_PIN_L, pigpio.OUTPUT)

#角度からデューティ比を求める関数
def servo_angle(angle):
    duty = 2.5 + (12.0 - 2.5) * (angle + 90) / 180   #角度からデューティ比を求める
    ServoR.ChangeDutyCycle(duty)     #デューティ比を変更
    ServoL.ChangeDutyCycle(-duty) 
    time.sleep(0.3)                 #0.3秒間待つ

def PID2(pos_theta,sat_theta,dis0):   
    pre_turn = pos_theta-sat_theta#機体の旋回する角度
    r = 105#機体の横の長さ/2
    r_1 = 67.5#車輪の半径
    turn = r/r_1*pre_turn
    d_s = 0.05#後で直す
    seconds = dis0*d_s

    servo_angle(turn)                #サーボモータ  角度
    ServoR.stop() 
    ServoL.stop()                  #サーボモータをストップ
    GPIO.cleanup()
    pi.set_servo_pulsewidth( SERVO_PIN_R, 1000 )
    pi.set_servo_pulsewidth( SERVO_PIN_L, 1000 )
    time.sleep( seconds )




 #以下，誘導
while True:
    GPS_data = GPS()
    if GPS_data[4]>10:
        while True:
            #GPSの情報取得
            GPS_data = GPS()
            if GPS_data[4]<10:
                 break
            else:
            #PID制御
                PID2(pos_theta,sat_theta,dis0)
                #PID一回終了ごとにGPS取得のため一旦停止
                pi.stop()
print("GPS PROCESS FINISH!")