import socket
from helper import convert_to_type,create_udp_header,get_payload,sort_buffer,get_request,get_datagram_header,convert_to_ip_address
SERVER_IP='127.0.0.1'
SERVER_PORT=8007
from constants import ROUTER_IP,ROUTER_PORT


def check_ack(response,sequence_number):
    decoded_response = get_payload(response[11:].decode('utf-8'))
    (packet_type, recieved_sequence_number, server_address, server_port) = convert_to_type(response)
    print('packet-type,sequence-number:', packet_type, recieved_sequence_number )
    if packet_type == 2 and sequence_number == recieved_sequence_number-1:
        return True
    else:
        return False
def convert_address_to_list(address):
    address=address.split('.')
    address=list(map(int,address))
    return address

def send_finish_message(socket,client_address,client_port):
    finish_ack_not_received = True
    datagram_header=get_datagram_header(client_address,client_port, 5, 40000)
    finish_packet=datagram_header
    while finish_ack_not_received:
        try:
            send_request(socket,finish_packet)
            response_data,router_address=receive_response(socket)
            response = get_payload(response_data[11:].decode('utf-8'))
            (packet_type, sequence_number,server_address,server_port) = convert_to_type(response_data)
            if packet_type==6:
                finish_ack_not_received=False
        except socket.timeout:
            print('Socket-Timeout resending packet again')
            continue
    print('Payload Finished sending, Server will close the connection now.')
    return True
def send_request(socket,packet):
    socket.sendto(packet,(ROUTER_IP,ROUTER_PORT))

def receive_response(socket):
    return socket.recvfrom(1024)
def get_response(request):
    response="HTTP/1.1 200 OK\r\n"
    response+="Content-Length:10\r\n\r\n"
    response+="This is a data. replied!!!!!"
    return response
def send_response_to_client(socket,datagram_payload,client_address,client_port):
    udp_data_headers = []
    frames = [datagram_payload[0:i + 1013] for i in range(0, len(datagram_payload), 1011)]
    packet_ack_not_received=[True for i in range(0,len(frames))]
    datagram_frames = []
    all_packet_reached = True
    client_address=convert_to_ip_address(client_address)
    send_finish_message_to_client = False
    for i in range(0,len(frames)):
        sequence_number=25000+i
        print('Cleint>>>>>>>>>>>',client_address,client_port)
        udp_data_headers.append(get_datagram_header(client_address, client_port, 4, sequence_number))
        datagram_frames.append(udp_data_headers[i] + frames[i])
        while packet_ack_not_received[i]:
            try:
                send_request(socket, datagram_frames[i])
                response_data, server_address = receive_response(socket)
                correct_ack = check_ack(response_data, sequence_number)
                if correct_ack:
                    packet_ack_not_received[i] = False
            except socket.timeout:
                print(f'Socket timeout for Packet: {i}. Resending...')
                continue
    for _ in packet_ack_not_received:
        print(_)
        if _ == True:
            all_packet_reached = False

    if all_packet_reached:
        send_finish_message_to_client = send_finish_message(socket, client_address, client_port)
def main():
    server_socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    server_socket.bind((SERVER_IP,SERVER_PORT))
    print(f'Server started at: {SERVER_IP}: {SERVER_PORT}')
    request_buffer={}
    request=''
    program_flag=True
    while program_flag:
        data,router_address=server_socket.recvfrom(1024)
        # print('sender address',sender_address)
        # print(router_address)
        #parse request from the udp payload.
        packet_type, sequence_number,client_address,client_port=convert_to_type(data[:11])
        print(type(sequence_number))
        #parse necessary field from the udp header
        client_address=convert_address_to_list(client_address)
        print(packet_type, sequence_number)
        response_payload=''
        #packet to reply back to the client
        if packet_type==0:
            response_packet_header=create_udp_header(1,sequence_number+1,client_address,client_port)
            response_payload = 'SYNC ACK'.encode('utf-8')
        elif packet_type==2:
            #this sould give response from the server
            response=get_response(request)
            datagram_payload = response.encode('utf-8')
            send_response_to_client(server_socket,datagram_payload,client_address,client_port)
            response_packet_header = create_udp_header(2, sequence_number + 1, client_address, client_port)
            response_payload = 'ACK'.encode('utf-8')
            program_flag=False
        elif packet_type==4:
            if sequence_number not in request_buffer:
                request_buffer[sequence_number]=get_payload(data[11:].decode('utf-8'))
            response_packet_header = create_udp_header(2, sequence_number+1, client_address, client_port)
            response_payload = 'ACK'.encode('utf-8')
        elif packet_type==5:
            sorted_buffer=sort_buffer(request_buffer)
            request=get_request(sorted_buffer)
            print(request)
            response_packet_header = create_udp_header(6, sequence_number + 1, client_address, client_port)
            response_payload = 'FIN ACK'.encode('utf-8')
        response_packet=response_packet_header+response_payload
        server_socket.sendto(response_packet,(ROUTER_IP,ROUTER_PORT))

    print('Server Connection Closed!!')
    server_socket.close()

if __name__=='__main__':
    main()