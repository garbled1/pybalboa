import balboa
import binascii

def test_crc():
    config_resp = bytes.fromhex('1E0ABF9402148000152737EFED0000000000000000001527FFFF37EFED42')
    config_resp_crc = 0x42
    
    panel_conf_resp = bytes.fromhex('0B0ABF2E0A0001500000BF')
    panel_conf_resp_crc = 0xbf

    status_update = bytes.fromhex('7E1DFFAF13000064082D00000100000400000000000000000064000000067E')
    status_update_crc = 0x06

    conf_req = bytes.fromhex('7E050ABF04777E')
    conf_req_crc = 0x77

    spa = balboa.BalboaSpaWifi('none', 52)

    result = spa.balboa_calc_cs(conf_req[1:], 4)
    print('Expected CRC={0} got {1}'.format(hex(conf_req_crc), hex(result)))
    if result != conf_req_crc:
        return 1

    result = spa.balboa_calc_cs(status_update[1:], 28)
    print('Expected CRC={0} got {1}'.format(hex(status_update_crc), hex(result)))
    if result != status_update_crc:
        return 1

test_crc()

