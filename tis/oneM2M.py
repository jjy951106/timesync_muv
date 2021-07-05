from tis.core_thread import *
import json


# OneM2M TIS class for devices
class TIS(Thread):
    
    # Initialize
    def __init__(self, thing, sc, rf_sc = None):
        Thread.__init__(self)
        self.thing = thing
        self.sc = sc
        self.rf_sc = rf_sc
        
    def run(self):
        # ================== communication and routine ======================

        try:
            
            # Initialization for threads
            threads = []
            
            # Wi-Fi connection
            if self.rf_sc == None: conn = self.sc
            # Other connection
            else: conn = self.rf_sc.ser
                
            # Creation of threads
            if self.thing.protocol == 'up': threads.append( Client_up(conn, self.thing) )
            elif self.thing.protocol == 'down': threads.append( Client_down(conn, self.thing) )
            
            # Start all threads and sleep repeatedly
            for thr in threads: thr.start()
                            
        except KeyboardInterrupt:
            self.sc.close()


# OneM2M TIS class for devices
class MUV_TIS(Thread):
    
    # Initialize
    def __init__(self, thing, sc, rf_sc = None):
        Thread.__init__(self)
        self.thing = thing
        self.sc = sc
        self.rf_sc = rf_sc
        
        
    def run(self):
        # ================== communication and routine ======================

        try:
            
            # Initialization for threads
            threads = []
            
            # Wi-Fi connection
            if self.rf_sc == None: conn = self.sc
            # Other connection
            else: conn = self.rf_sc.ser
                
            # Creation of threads
            if self.thing.protocol == 'up': threads.append( MUV_up(conn, self.thing) )
            elif self.thing.protocol == 'down': threads.append( Client_down(conn, self.thing) )
            
            # Start all threads and sleep repeatedly
            for thr in threads: thr.start()
                            
        except KeyboardInterrupt:
            self.sc.close()



# OneM2M TIS class for gateways
class TIS_G(Thread):
    
    # Initialize
    def __init__(self, thing, sc, rf_sc):
        Thread.__init__(self)
        self.thing = thing
        self.sc = sc
        self.rf_sc = rf_sc
        
        
    def run(self):
        # ================== communication and routine ======================

        try:
            # Start gateway thread and repeated sleep
            Server_thread(self.sc, self.rf_sc.ser).start() 
            while True: time.sleep(0.5)
            
                            
        except KeyboardInterrupt:
            self.sc.close()



# ==============   Base thing device
class Thing:
    
    # Initialize value object
    def __init__(self, interval = 0.5):
        self.interval = interval
        self.tag = []
        self.name = 'Thing'
    
    
    # Check multiple json objects
    def check_muljson(self, data):
        
        jsons = data.replace('<EOF>','')
        json_list = []
        
        i = 0
        end = 1
        
        while i < len(jsons) :
            
            if jsons[i] == '{':
                end = 0
                for j in range( i+1, len(jsons) ) :
                    
                    # Turn on the end flag
                    if jsons[j] == '}' : 
                        json_list.append(jsons[i:j+1])
                        i = j
                        end = 1
                        break
                
            elif jsons[i] == '}' :
                raise Exception
            
            if end == 0 :
                raise Exception
            
            i = i+1
                
        # Return the result of check for 
        return json_list

                
    # Formation function for sensor values
    def encode(self, con, data):
        payload = '{"ctname":"%s","con":"%s"}<EOF>' % (con, data)
        return payload
    
    
    # Function to get json object
    def parse(self, payload):
        
        json_list = self.check_muljson(payload)
        obj_list = []
        
        # return the list of json objects
        for sample in json_list :
        
            obj = json.loads(sample)
            key = str( obj['ctname'] )
            value = obj['con']
            
            if value == '2001':
                continue
            else:
                result = (key, value)
                obj_list.append(result)

        return obj_list
    
    
    # Thing dependent get function
    def get(self, key):
        pass
    
    # Thing dependent control function
    def control(self, key, value):
        pass
    
    
    # Function to read payload data
    def read(self, key):
        data = self.get(key)
        payload = self.encode(key, data)
        return data
    
   

    # Function to write payload data
    def write(self, payload):
        obj_list = self.parse(payload)
        
        for obj in obj_list :
            key, value = obj
            
            if value == '2001':
                pass
            else    :
                self.control(key, value)
        
        

