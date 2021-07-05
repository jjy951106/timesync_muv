from tis.oneM2M import *
from pymavlink import mavutil
from datetime import datetime as dt
from pytz import timezone
import os, threading
import subprocess
import platform
import json
import time
from socket import *
# Warning!! In each class, one must implement only one method among get and control methods

# Uplink class (for time offset monitoring)
class Monitor(Thing):

    # Initialize
    def __init__(self):
        Thing.__init__(self)
        self.protocol = 'up'
        self.interval = 5
        self.topic = []
        self.name = 'Monitor'
        self.server_addr = ''
        self.server_port = ''
        self.trans_protocol = 'udp'
        self.threshold = 5
        self.ct_path = ''
        self.fc_port = None
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
        
        print(self.ct_path)

        # OS address bit check
        (os_bit, _) = platform.architecture()
        if os_bit == '32bit':
            self.client_sw = self.ct_path[:-2] + '86'
        elif os_bit == '64bit':
            self.client_sw = self.ct_path[:-2] + '64'

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
            
            # Time offset calculation
            mc_offset = subprocess.getoutput( self.client_sw + ' 3 ' + self.server_addr + ' ' + self.server_port + ' ' + str(self._protocol) )
            
            data_temp = mc_offset.split('+')
            del data_temp[-1]
            
            payload = dict()
            payload['server'] = dt.fromtimestamp( float( data_temp[0] ) ).astimezone(timezone('Asia/Seoul')).strftime('%Y%m%dT%H%M%S%f')[:-3]
            payload['mc_time'] = dt.fromtimestamp( float( data_temp[1] ) ).astimezone(timezone('Asia/Seoul')).strftime('%Y%m%dT%H%M%S%f')[:-3]
            payload['mc_offset'] = int( data_temp[2] )

            # Check the FC connection
            if self.fc_port == None:
                payload['fc_time'] = dt.fromtimestamp( float( data_temp[1] ) ).astimezone(timezone('Asia/Seoul')).strftime('%Y%m%dT%H%M%S%f')[:-3]
                payload['fc_offset'] = int( data_temp[2] )
            else:
                payload['fc_time'] = dt.fromtimestamp( self.fc_time ).astimezone(timezone('Asia/Seoul')).strftime('%Y%m%dT%H%M%S%f')[:-3]
                payload['fc_offset'] = self.fc_offset

            payload = json.dumps(payload, indent=4)

            # Time offset check
            if abs(float(data_temp[2])) > float(self.threshold):
                # Excute synchronizer
                subprocess.call([self.client_sw, '1', self.server_addr, self.server_port, str(self._protocol), str(self.threshold)], stdout = subprocess.PIPE, stderr = subprocess.PIPE)
                print('Synchronizer is executed')

            # Return the calculated time offset
            return payload

        else :
            pass


    # Function to measure RTT of the FC link
    def rtt_measure(self):
        
        if self.fc_port != None:

            HOST = "1.239.197.74" # 1.239.197.74
            PORT = 5005
            ADDR = (HOST, PORT)

            count = tmp = fc_lt = 0
            N = 10 # this is needed to reduce
            sendTerm = 5 # second

            sock = socket(AF_INET, SOCK_DGRAM)

            # Interval initialize
            self.fc_port.mav.request_data_stream_send( self.fc_port.target_system, self.fc_port.target_system, 0, 5, 1 )            

            # Set FC time
            while True:
                
                # self.fc_port.mav.param_set_send('BRD_RTC_TYPES', 2)
                
                self.fc_port.mav.system_time_send( int( dt.timestamp(dt.now()) * 1e6 ) , 0 )
                msg = self.fc_port.recv_match(type='SYSTEM_TIME',blocking=True)
                if msg.time_unix_usec > 10: break
            
            start = time.time()
            
            while True:

                # Send timesync
                tx_time = dt.timestamp(dt.now())
                self.fc_port.mav.timesync_send(0, int( tx_time ))

                # Time sync message reception
                msg = self.fc_port.recv_match(type='TIMESYNC',blocking=True)
                if msg.tc1 == 0:
                    continue
                else:
                    rx_time = dt.timestamp(dt.now())
                    if self.fc_lt != 0: self.fc_lt = (self.fc_lt + (rx_time - tx_time) / 2 ) / 2
                    else: self.fc_lt = (rx_time - tx_time) / 2

                # print("fc_lt : {}, rx_time : {}, tx_time : {}".format(self.fc_lt, rx_time, tx_time))
                
                # System time message reception
                msg = self.fc_port.recv_match(type='SYSTEM_TIME',blocking=True)
                now = float( dt.timestamp( dt.now() ) )
                self.fc_time = float( msg.time_unix_usec / 1e6 )
                self.fc_offset = int( ( (self.fc_time + self.fc_lt) - now ) * 1000 )
                
                # print("msg : {}\nfc_time : {}\nfc_offset : {}\nnow : {}".format(msg, self.fc_time, self.fc_offset, now))

                # send ms measure
                count = count + 1
                tmp = tmp + (self.fc_offset / N)
                if count is N:
                    enteredTime = time.time() - start
                    if sendTerm - enteredTime >= 0:
                        time.sleep(sendTerm - enteredTime)
                        
                    # more than 1s companste gps time assumes gps sync problem and so this problem is ignored.
                    if abs(tmp) < 1000:
                        sock.sendto(str(tmp).encode(), ADDR)
                    count = 0
                    tmp = 0
                        
                    # startTime initialization
                    start = time.time()

                    # print(f'enteredTime : {enteredTime}, sleepTime : {sendTerm - enteredTime}')      
        else:
            return



        
        