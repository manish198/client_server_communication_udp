import socket
import os
import threading
from helper import convert_to_type,create_udp_header,get_payload,sort_buffer,get_request,get_datagram_header,convert_to_ip_address
SERVER_IP='127.0.0.1'
SERVER_PORT=8007
from constants import ROUTER_IP,ROUTER_PORT
import argparse


DIR_PATH=''
file_locks={}
HOST='127.0.0.1'
PORT=8080
def parse_request(client_response):
    client_message = client_response
    message_list = client_message.split('\r\n')
    request_firstline = message_list[0].split(' ')
    request_method = request_firstline[0]
    request_path = request_firstline[1]
    request_body=client_message.split('\r\n\r\n')[1]
    return request_method,request_path,request_body

def check_request_path(request_path):
    count=0
    string_set=request_path.split('/')
    for string in string_set:
        if string=='..':
            count+=1
    if count: return False
    else: return True

def list_file():
    files=''
    status_code=''
    status_message=''
    for _ in os.listdir(DIR_PATH):
        files+=_+' '
    status_code=200
    status_message='OK'
    return files,status_code,status_message

def file_content(request_path):
    # print(request_path)
    content_type=''
    constent_disposition=''
    data=''
    status_code = ''
    status_message = ''
    file_path=os.path.join(DIR_PATH,request_path[1:])
    # print(file_path)
    if os.path.isfile(file_path):
        print('file exists!!!')
        file=open(f'{file_path}','r')
        lines=file.readlines()
        for line in lines:
            data+=line
        print(data)
        status_code=200
        status_message='OK'

        constent_disposition = f'attachment;filename="{os.path.basename(request_path)}"'

        filename=file_path.split('/')[-1]
        file_split=filename.split('.')
        extension=''
        if len(file_split)==2:
            extension=file_split[-1]
        if (extension=='' or extension=='html' or extension=='txt'):
            content_type='text/html'
        elif (extension=='json'):
            content_type='application/json'


    elif os.path.isdir(file_path):
        for _ in os.listdir(file_path):
            data += _+ ' '
        status_code = 200
        status_message = 'OK'
    else:
        print('Sorry, file or folder doesnot exists!!!')
        status_code=404
        status_message='NOT FOUND'
    return data,status_code,status_message,content_type,constent_disposition


def get_handler(request_path):
    data=''
    status_code=''
    status_message=''
    content_type=''
    content_disposition=''
    if request_path=='/':
        data,status_code,status_message=list_file()
    else:
        data,status_code,status_message,content_type,content_disposition=file_content(request_path)
    return data,status_code,status_message, content_type,content_disposition

def get_file_lock(file_path):
    file_locks.setdefault(file_path,threading.Lock())
    return file_locks[file_path]
def post_handler(request_path,request_body):
    data=''
    status_code=''
    status_message=''
    file_path = os.path.join(DIR_PATH, request_path[1:])
    with get_file_lock(file_path):
        #time.sleep(2)
        try:
            # append to a existing folder
            if os.path.isfile(file_path):
                print('file exists!!!')
                file = open(f'{file_path}', 'a')
                file.write(request_body+'\n')
                file.close()
                status_code = 200
                status_message = 'OK'
            #dont write in the folder.
            elif os.path.isdir(file_path):
                status_code='405'
                status_message='Bad Request'
                data='Cannot write to a folder'
            #create a new folder and write in it.
            else:
                file=open(file_path,"w")
                file.write(request_body+'\n')
                file.close()
                status_code = 200
                status_message = 'OK'
        except IOError:
            print(f"File {file_path} is currently locked.")
            status_code = 503
            status_message = 'Service Unavailable'
            data = 'File is locked by another process'
    return data,status_code,status_message
def client_request_handler(request):
    print('Client: statred a operation in a seperate thread')
    data = ''
    status_code=''
    status_message=''
    content_type=''
    content_disposition=''
    headers = {}
    request_method,request_path,request_body=parse_request(request)

    # check for directory traversal attack
    is_request_path_safe = check_request_path(request_path)
    if is_request_path_safe:
        if request_method == 'GET':
            data, status_code, status_message, content_type, content_disposition = get_handler(request_path)
        elif request_method == 'POST':
            data, status_code, status_message = post_handler(request_path, request_body)
    else:
        status_code = 405
        status_message = 'Not Allowed'

    if not (content_type == '' and content_disposition == ''):
        headers["Content-Type"] = content_type
        headers["Content-Disposition"] = content_disposition

    # creating a HTTP response step by step.
    response = f"HTTP/1.1 {status_code} {status_message}\r\n"
    for header in headers:
        response += header + ':' + headers[header] + '\r\n'
    response += f"Content-Length: {len(data)}\r\n\r\n"
    response += f"{data}"
    return response


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
# def get_response(request):
#     response="HTTP/1.1 200 OK\r\n"
#     response+="Content-Length:10\r\n\r\n"
#     response+="This is a data. replied!!!!!"
#     return response
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
def start_udp_communication():
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
            response=client_request_handler(request)
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
    description_text = 'httpfs is a simple file server'
    parser = argparse.ArgumentParser(description=description_text, usage='httpfs [-v] [-p PORT] [-d PATH-TO-DIR]')
    parser.add_argument('-v', help='print debugging message')
    parser.add_argument('-p', type=int, help='PORT', dest='port')
    parser.add_argument('-d', type=str, help='PATH-TO-DIR', dest='directory')
    args = parser.parse_args()
    # if directory name is not specified in an argument.
    if not args.directory:
        DIR_PATH = os.path.dirname(os.path.realpath(__file__))
    # if directory name is specified in an argument.
    else:
        # if directory exists!
        if os.path.isdir('./' + args.directory):
            DIR_PATH = os.path.abspath('./' + args.directory)
        # if there is no such directory, create one.
        else:
            os.mkdir('./' + args.directory)
            DIR_PATH = os.path.abspath('./' + args.directory)
            print('created')

    if args.port:
        PORT = args.port
    start_udp_communication()