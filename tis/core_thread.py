from select import *
from threading import *
import time



# Client uplink thread
class Client_up(Thread):
    
    def __init__(self, rf_sc, thing):
        Thread.__init__(self)
        self.rf_sc = rf_sc
        self.thing = thing
        self.topic = thing.topic
        self.interval = thing.interval
        print(thing.name + ' interface is started')
        
        
    def run(self):
        
        # Data transmission
        while True:
            
            try:
                
                if len(self.topic) == 0:
                    break
                
                # If uplink array is vacant
                if not len(self.topic):
                    break
                
                # Update delay (second)
                time.sleep(self.interval)
                
                # Sending sensor values
                for i in range(0, len(self.topic)):
                    payload = self.thing.read(self.topic[i])
                    self.rf_sc.send( bytes(payload, 'UTF-8') )
                    print(payload)
                    
            except KeyboardInterrupt:
                self.rf_sc.close()


# Client uplink thread
class MUV_up(Thread):
    
    def __init__(self, rf_sc, thing):
        Thread.__init__(self)
        self.rf_sc = rf_sc
        self.thing = thing
        self.topic = thing.topic
        self.interval = thing.interval
        print(thing.name + ' interface is started')
        
        
    def run(self):
        # Data transmission
        while True:
            
            try:
                
                if len(self.topic) == 0:
                    break
                
                # If uplink array is vacant
                if not len(self.topic):
                    break
                
                # Update delay (second)
                time.sleep(self.interval)
                
                # Sending sensor values
                payload = self.thing.read(self.topic)
                print(payload)
                self.rf_sc.publish(self.thing.topic, payload)
                # print('Successfully published')
                    
            except KeyboardInterrupt:
                self.rf_sc.close()
        


# Client downlink threadN
class Client_down(Thread):
    
    def __init__(self, rf_sc, thing):
        Thread.__init__(self)
        self.rf_sc = rf_sc
        self.thing = thing
        self.topic = thing.topic
        print(thing.name + ' interface is started')
        
    def run(self):
        
        # Mux list
        input_conn = [self.rf_sc]
        
        # Notification for device starting
        for i in range( len(self.topic) ):
            self.rf_sc.send(self.thing.encode(self.topic[i], 'on'))          
            
            
        # Data reception
        while True:
            
            try:
                
                if len(self.topic) == 0:
                    break
                    
                
                # Check stream
                read, write, err = select(input_conn, [], [], 5)
                
                
                for input in read:
                            
                    # If the input stream is RF port
                    if input == self.rf_sc :
                        
                        # Receive data from RF port
                        data = self.rf_sc.recv(2048)
                        if not data: break
                        
                        
                        # Check the received data if the key of the data is included in down_arr
                        for obj in self.thing.parse(data):    
                            key, value = obj
                            
                            # Ignore if the msg is start signal
                            if value == 'on':
                                continue
                            
                            # If the key is included in arr, write the operation
                            if key in self.topic:
                                payload = self.thing.encode(key, value)
                                self.thing.write(payload.decode('UTF-8'))


            except KeyboardInterrupt:
                
                # Close serial
                self.rf_sc.close()
                
                
                
                
                
                
class Server_thread(Thread):
    
    def __init__(self, sc, rf_sc):
        Thread.__init__(self)
        self.sc = sc
        self.rf_sc = rf_sc
        print('Gateway interface is started')
        
    def run(self):
        
        # Mux list
        input_conn = [self.sc, self.rf_sc]
    
        # Start connection loop
        while True:
        
            try :
                
                # Check stream
                read, write, err = select(input_conn, [], [], 5)
                
                        
                # Input stream
                for input in read:
                    
                    # If the input stream is socket
                    if input == self.sc :
                        
                        # Receive socket data
                        data = input.recv(2048)
                        
                        if not data :
                            break
                        
                        self.rf_sc.send(data)
                            
                            
                    # If the input stream is RF port
                    elif input == self.rf_sc :
                        
                        # Receive data from RF port
                        data = self.rf_sc.recv()
                        
                        # Send data to &cube, receive ACK, 
                        self.sc.send(data)
      
                
            except KeyboardInterrupt:
                
                # Close all ports
                self.rf_sc.close()
                self.sc.close()