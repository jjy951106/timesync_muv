from tis.oneM2M import *
from pymavlink import mavutil
import paho.mqtt.client as mqtt
from pymavlink.dialects.v10 import ardupilotmega
from datetime import datetime as dt
from pytz import timezone
import os, threading
import subprocess
import platform
import json
import time
import serial
from socket import *

class fifo(object):
    def __init__(self):
        self.buf = []
    def write(self, data):
        self.buf += data
        return len(data)
    def read(self):
        return self.buf.pop(0)

# Warning!! In each class, one must implement only one method among get and control methods

# Uplink class (for time offset monitoring)
class Monitor(Thing):

    # Initialize
    def __init__(self):
        Thing.__init__(self)
        self.protocol = 'up'
        self.interval = 5
        self.topic = []
        self.topic_systime = ''
        self.topic_timesync = ''
        self.topic_req = ''
        self.name = 'Monitor'
        self.server_addr = ''
        self.server_port = ''
        self.trans_protocol = 'udp'
        self.threshold = 5
        self.ct_path = ''
        self.tx_time = []
        self.fc_lt = 0
        self.fc_time = 0
        self.fc_offset = 0

        # client path check
        if os.path.exists('./linux_client_x86'):
            self.ct_path = os.path.abspath('linux_client_x86')
        elif os.path.exists('./device/linux_client_x86'):
            self.ct_path = os.path.abspath('./device/linux_client_x86')
        else:
            for name in os.listdir('./'):
                if name.find('_timesync') != -1:
                    if os.path.exists('./' + name + '/linux_client_x86'):
                        self.ct_path = os.path.abspath('./' + name + '/linux_client_x86')
                        break
                    elif os.path.exists('./' + name + '/device/linux_client_x86'):
                        self.ct_path = os.path.abspath('./' + name + '/device/linux_client_x86')
                        break

        # OS address bit check
        (os_bit, _) = platform.architecture()
        if os_bit == '32bit':
            self.client_sw = self.ct_path[:-2] + '86'
        elif os_bit == '64bit':
            self.client_sw = self.ct_path[:-2] + '64'
            
        print(self.client_sw)

        # Change of ownership
        subprocess.call(['sudo', 'chmod', '777', self.client_sw])


    # Thing dependent get function
    def get(self, key):

        if key in self.topic:

            # protocol check
            if self.trans_protocol == 'tcp':
                self._protocol = 1
            elif self.trans_protocol == 'udp':
                self._protocol = 0
            
            payload = dict()
            
            Index = True
            while Index:
                # Time offset calculation
                mc_offset = subprocess.getoutput( self.client_sw + ' 3 ' + self.server_addr + ' ' + self.server_port + ' ' + str(self._protocol) )
                    
                data_temp = mc_offset.split('+')
                del data_temp[-1]
                
                try:
                    payload['server'] = dt.fromtimestamp( float( data_temp[0] ) ).astimezone(timezone('Asia/Seoul')).strftime('%Y%m%dT%H%M%S%f')[:-3]
                    payload['mc_time'] = dt.fromtimestamp( float( data_temp[1] ) ).astimezone(timezone('Asia/Seoul')).strftime('%Y%m%dT%H%M%S%f')[:-3]
                    payload['mc_offset'] = int( data_temp[2] )
                    Index = False
                except IndexError:
                    time.sleep(3)
                    continue 

            # Check the FC connection
            if self.fc_offset == 0:
                payload['fc_time'] = payload['mc_time']
            else:
                payload['fc_time'] = dt.fromtimestamp( self.fc_time ).astimezone(timezone('Asia/Seoul')).strftime('%Y%m%dT%H%M%S%f')[:-3]
            #payload['fc_offset'] = self.fc_offset
            payload['fc_offset'] = int( data_temp[2] - self.fc_offset )
            payload = json.dumps(payload, indent=4)

            # Time offset check
            if abs(float(data_temp[2])) > float(self.threshold):
                # Excute synchronizer
                subprocess.call(['sudo', self.client_sw, '1', self.server_addr, self.server_port, str(self._protocol), str(self.threshold)], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
                print('Synchronizer is executed')

            # Return the calculated time offset
            return payload

        else :
            pass


    # Function to measure RTT of the FC link
    def rtt_measure(self, muv_tis, sc):

        settings = {
            'SendTerm'       : 4,
            'InitialPacket'  : 15,
            'TransmitPacket' : 5,
            'Hz'             : 0.6,
        }
        
        f = fifo()
        mav = ardupilotmega.MAVLink(f)

        ADDR = (self.server_addr, int(self.server_port))

        count = tmp = 0
        sock = socket(AF_INET, SOCK_DGRAM)

        start = time.time()
                
        initial = 0
                    
        while True:
            
            try:
                # 2hz
                time.sleep(settings['Hz'])
                    
                # Send timesync
                self.tx_time = dt.timestamp(dt.now())
                m = mav.timesync_encode(0, int( self.tx_time ))
                m.pack(mav)
                tx_msg = m.get_msgbuf()
                sc.publish(self.topic_req, tx_msg)
                # print('Time synch is published')

                # send ms measure
                count = count + 1
                tmp = tmp + (self.fc_offset / settings['TransmitPacket'])
                
                if count is settings['TransmitPacket']:
                    enteredTime = time.time() - start
                    if settings['SendTerm'] - enteredTime >= 0:
                        time.sleep(settings['SendTerm'] - enteredTime)
                    
                    if tmp is not 0:
                        if initial < settings['InitialPacket']:
                            sock.sendto(str(tmp).encode(), ADDR)
                            initial = initial + 1
                                
                        # more than 2min companste gps time assumes gps sync problem and so this problem is ignored.
                        elif abs(tmp) <= 120000:
                            sock.sendto(str(tmp).encode(), ADDR)
                    
                    count = 0
                    tmp = 0
                                
                    # startTime initialization
                    start = time.time()
            
            except KeyboardInterrupt:
                muv_tis.join()
                sc.close()
                return 0

        
        