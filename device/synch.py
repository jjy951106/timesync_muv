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
        
        settings = {
            'DataRate'       : 2,
            'TransmitPacket' : 10,
            'SendTerm'       : 5,
            'BRD_RTC_TYPES'  : 3,   # GPS, MAVLINK
        }
        
        if self.fc_port != None:

            ADDR = (self.server_addr, int(self.server_port))

            count = tmp = fc_lt = 0
            sock = socket(AF_INET, SOCK_DGRAM)
            
            # For Ardupilot
            self.fc_port.mav.param_set_send( self.fc_port.target_system, self.fc_port.target_component, b'BRD_RTC_TYPES',\
                                             settings['BRD_RTC_TYPES'], mavutil.mavlink.MAV_PARAM_TYPE_INT32 )

            self.fc_port.mav.param_request_read_send( self.fc_port.target_system, self.fc_port.target_component, b'BRD_RTC_TYPES', -1 )
            time.sleep(2)

            try:
                message = fc_port.recv_match(type='PARAM_VALUE', blocking=True).to_dict()
                print(message['param_id'], message['param_value'])
            except Exception as e:
                print(e)
                exit(0)
            
            # Interval initialize
            self.fc_port.mav.request_data_stream_send( self.fc_port.target_system, self.fc_port.target_system, 0, settings['DataRate'], 1 )
      
            # Set FC time
            while True:

                self.fc_port.mav.system_time_send( int(time.time() * 1e6) , 0 )
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
                    if fc_lt != 0: fc_lt = (fc_lt + (rx_time - tx_time) / 2 ) / 2
                    else: fc_lt = (rx_time - tx_time) / 2 

                # System time message reception
                msg = self.fc_port.recv_match(type='SYSTEM_TIME',blocking=True)
                now = float( dt.timestamp( dt.now() ) - self.fc_port.time_since('SYSTEM_TIME') )
                fc_time = float( msg.time_unix_usec / 1e6 )
                fc_offset = int( ( (fc_time + fc_lt) - now ) * 1000 )
                
                """
                print("\n----------------------------------------------------------------------------")
                print("msg : {}\nfc_time : {}\nfc_offset : {}\nnow : {}".format(msg, fc_time, fc_offset, now))
                print("----------------------------------------------------------------------------\n")
                """
                
                # send ms measure
                count = count + 1
                tmp = tmp + (fc_offset / settings['TransmitPacket'])
                if count is settings['TransmitPacket']:
                    enteredTime = time.time() - start
                    if settings['SendTerm'] - enteredTime >= 0:
                        time.sleep(settings['SendTerm'] - enteredTime)
                    
                    # more than 200ms companste gps time assumes gps sync problem and so this problem is ignored.
                    if abs(tmp) < 200:
                        sock.sendto(str(tmp).encode(), ADDR)
                    count = 0
                    tmp = 0
                    
                    # startTime initialization
                    start = time.time()
                    
                    """
                    print('(Transmission Packet, Interval) : ({}, {}s)\n(EnteredTime, SleepTime) : ({:.3f}, {:.3f})'\
                           .format(settings['TransmitPacket'], settings['SendTerm'], enteredTime, settings['SendTerm'] - enteredTime))
                    """
        else:
            return



        
        