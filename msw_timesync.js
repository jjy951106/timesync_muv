// for TAS of mission

let mqtt = require('mqtt');
let fs = require('fs');
let spawn = require('child_process').spawn;
let exec = require('child_process').exec;

let my_msw_name = 'msw_timesync';

let fc = {};
let config = {};

let sortie_name
try {                                   // for nCube-MUV (NodeJs)
    sortie_name = my_sortie_name
}
catch (e) {                             // for nCube-MUV-Python
    sortie_name = process.argv[2]
}

config.name = my_msw_name;

try {
    try {           // for nCube-MUV (NodeJs)
        config.directory_name = msw_directory[my_msw_name];
        config.sortie_name = '/' + sortie_name;
        config.gcs = drone_info.gcs;
        config.drone = drone_info.drone;
        config.lib = [];
    }
    catch (e) {     // for nCube-MUV-Python
        config.directory_name = process.argv[3];
        config.sortie_name = '/' + sortie_name;
        config.gcs = process.argv[4];
        config.drone = process.argv[5];
        config.lib = [];
    }
}
catch (e) {
    config.sortie_name = '';
    config.directory_name = '';
    config.gcs = 'KETI_MUV';
    config.drone = 'FC_MUV_01';
    config.lib = [];
}

// library 추가
let add_lib = {};
try {
    add_lib = JSON.parse(fs.readFileSync('./' + config.directory_name + '/lib_timesync.json', 'utf8'));
    config.lib.push(add_lib);
}
catch (e) {
    add_lib = {
        name: 'lib_timesync',
        target: 'armv6',
        description: '[name] [server ip] [interval] [protocol] [threshold] [server port]',
        scripts: './lib_timesync 203.253.128.177 5 udp 5 5005',
        data: ['TimeSync', 'Req'],
        control: ['system_time', 'timesync']
    };
    config.lib.push(add_lib);
}
// msw가 muv로 부터 트리거를 받는 용도
// 명세에 sub_container 로 표기
let msw_sub_muv_topic = [];

let msw_sub_fc_topic = [];
// msw_sub_fc_topic.push('/Mobius/' + config.gcs + '/Drone_Data/' + config.drone + '/heartbeat');
// msw_sub_fc_topic.push('/Mobius/' + config.gcs + '/Drone_Data/' + config.drone + '/global_position_int');
// msw_sub_fc_topic.push('/Mobius/' + config.gcs + '/Drone_Data/' + config.drone + '/attitude');
// msw_sub_fc_topic.push('/Mobius/' + config.gcs + '/Drone_Data/' + config.drone + '/battery_status');
msw_sub_fc_topic.push('/Mobius/' + config.gcs + '/Drone_Data/' + config.drone + '/system_time');
msw_sub_fc_topic.push('/Mobius/' + config.gcs + '/Drone_Data/' + config.drone + '/timesync');

let msw_sub_lib_topic = [];

function exitHandler(options, exitCode) {
    if (options.exit){
        exec('sudo kill $(pgrep -f msw_timesync)');
        process.exit();
    }
}

process.on('SIGINT', exitHandler.bind(null, {exit:true}));

function init() {
    if(config.lib.length > 0) {
        for(let idx in config.lib) {
            if(config.lib.hasOwnProperty(idx)) {
                if (msw_mqtt_client != null) {
                    for (let i = 0; i < config.lib[idx].control.length; i++) {
                        let sub_container_name = config.lib[idx].control[i];
                        _topic = '/Mobius/' + config.gcs + '/Mission_Data/' + config.drone + '/' + my_msw_name + '/' + sub_container_name;
                        msw_mqtt_client.subscribe(_topic);
                        msw_sub_muv_topic.push(_topic);
                        console.log('[msw_mqtt] msw_sub_muv_topic[' + i + ']: ' + _topic);
                    }

                    for (let i = 0; i < config.lib[idx].data.length; i++) {
                        let container_name = config.lib[idx].data[i];
                        let _topic = '/MUV/data/' + config.lib[idx].name + '/' + container_name;
                        msw_mqtt_client.subscribe(_topic);
                        msw_sub_lib_topic.push(_topic);
                        console.log('[lib_mqtt] lib_topic[' + i + ']: ' + _topic);
                    }
                }

                let obj_lib = config.lib[idx];
                setTimeout(runLib, 1000 + parseInt(Math.random()*10), JSON.parse(JSON.stringify(obj_lib)));
            }
        }
    }
}

function runLib(obj_lib) {
    try {
        let scripts_arr = obj_lib.scripts.split(' ');
        if(config.directory_name === '') {

        }
        else {
            scripts_arr[0] = scripts_arr[0].replace('./', '');
            scripts_arr[0] = './' + config.directory_name + '/' + scripts_arr[0];
        }

        let run_lib = spawn('sudo', [scripts_arr[0], scripts_arr.slice(1)]);
        // let run_lib = spawn('sudo', ['python3', scripts_arr[0] + '.py', scripts_arr.slice(1)]);

        run_lib.stdout.on('data', function(data) {
            console.log('stdout: ' + data);
        });

        run_lib.stderr.on('data', function(data) {
            console.log('stderr: ' + data);
//             setTimeout(init, 1000);
        });

        run_lib.on('exit', function(code) {
            console.log('exit: ' + code);
            setTimeout(run_lib, 3000, obj_lib);
        });

        run_lib.on('error', function(code) {
            console.log('error: ' + code);
        });
    }
    catch (e) {
        console.log(e.message);
    }
}

let msw_mqtt_client = null;

msw_mqtt_connect('localhost', 1883);

function msw_mqtt_connect(broker_ip, port) {
    if(msw_mqtt_client == null) {
        let connectOptions = {
            host: broker_ip,
            port: port,
//              username: 'keti',
//              password: 'keti123',
            protocol: "mqtt",
            keepalive: 10,
//              clientId: serverUID,
            protocolId: "MQTT",
            protocolVersion: 4,
            clean: true,
            reconnectPeriod: 2000,
            connectTimeout: 2000,
            rejectUnauthorized: false
        };

        msw_mqtt_client = mqtt.connect(connectOptions);

        msw_mqtt_client.on('connect', function () {
            console.log('[msw_mqtt_connect] connected to ' + broker_ip);
            for(idx in msw_sub_fc_topic) {
                if(msw_sub_fc_topic.hasOwnProperty(idx)) {
                    msw_mqtt_client.subscribe(msw_sub_fc_topic[idx]);
                    console.log('[msw_mqtt] msw_sub_fc_topic[' + idx + ']: ' + msw_sub_fc_topic[idx]);
                }
            }
        });

        msw_mqtt_client.on('message', function (topic, message) {
            for(let idx in msw_sub_muv_topic) {
                if (msw_sub_muv_topic.hasOwnProperty(idx)) {
                    if(topic === msw_sub_muv_topic[idx]) {
                        setTimeout(on_receive_from_muv, parseInt(Math.random() * 5), topic, message.toString());
                        break;
                    }
                }
            }

            for(idx in msw_sub_lib_topic) {
                if (msw_sub_lib_topic.hasOwnProperty(idx)) {
                    if(topic === msw_sub_lib_topic[idx]) {
                        let topic_arr = topic.split('/');
                        if (topic_arr[topic_arr.length - 1] === config.lib[0].data[0]) {
                            setTimeout(on_receive_from_lib, parseInt(Math.random() * 5), topic, message.toString());
                            break;
                        }
                        else if (topic_arr[topic_arr.length - 1] === config.lib[0].data[1]) {
                            setTimeout(on_receive_from_lib, parseInt(Math.random() * 5), topic, message.toString('hex'));
                            break;
                        }
                    }
                }
            }

            for(idx in msw_sub_fc_topic) {
                if (msw_sub_fc_topic.hasOwnProperty(idx)) {
                    if(topic === msw_sub_fc_topic[idx]) {
                        setTimeout(on_process_fc_data, parseInt(Math.random() * 5), topic, message.toString());
                        break;
                    }
                }
            }
        });

        msw_mqtt_client.on('error', function (err) {
            console.log(err.message);
        });
    }
}

function on_receive_from_muv(topic, str_message) {
    console.log('[' + topic + '] ' + str_message);

    parseControlMission(topic, str_message);
}

function on_receive_from_lib(topic, str_message) {
    console.log('[' + topic + '] ' + str_message + '\n');

    parseDataMission(topic, str_message);
}

function on_process_fc_data(topic, str_message) {
    console.log('[' + topic + '] ' + str_message + '\n');

    let topic_arr = topic.split('/');
    try {
        fc[topic_arr[topic_arr.length-1]] = JSON.parse(str_message.toString());
    }
    catch (e) {
    }

    parseFcData(topic, str_message);
}

setTimeout(init, 1000);

// 유저 디파인 미션 소프트웨어 기능
///////////////////////////////////////////////////////////////////////////////
function parseDataMission(topic, str_message) {
    try {
        let topic_arr = topic.split('/');
        if (topic_arr[topic_arr.length - 1] === config.lib[0].data[0]) {

            let data_topic = '/Mobius/' + config.gcs + '/Mission_Data/' + config.drone + '/' + config.name + '/' + topic_arr[topic_arr.length - 1];
            msw_mqtt_client.publish(data_topic, str_message);
        }
        else if (topic_arr[topic_arr.length - 1] === config.lib[0].data[1]) {
            if (mavPort != null) {
                if (mavPort.isOpen) {
                    mavPort.write(Buffer.from(str_message, 'hex'));
                }
            }
        }
    }
    catch (e) {
        console.log('[parseDataMission] data format of lib is not json');
    }
}
///////////////////////////////////////////////////////////////////////////////

function parseControlMission(topic, str_message) {
    try {
        let topic_arr = topic.split('/');
        let _topic = '/MUV/control/' + config.lib[0].name + '/' + topic_arr[topic_arr.length - 1];
        msw_mqtt_client.publish(_topic, str_message);
    }
    catch (e) {
        console.log('[parseControlMission] data format of lib is not json');
    }
}

function parseFcData(topic, str_message) {
    let topic_arr = topic.split('/');
    if (topic_arr[topic_arr.length-1] === 'system_time') {
        let _topic = '/MUV/control/' + config.lib[0].name + '/' + config.lib[0].control[0]; // 'system_time'
        msw_mqtt_client.publish(_topic, str_message);
    }
    else if (topic_arr[topic_arr.length-1] === 'timesync'){
        let _topic = '/MUV/control/' + config.lib[0].name + '/' + config.lib[0].control[1]; // 'timesync'
        msw_mqtt_client.publish(_topic, str_message);
    }
    else {
    }
}
