import socket
from builtins import len

from helper import (create_udp_header,convert_to_type,get_payload,
                    get_request,resolve_url,sort_buffer,get_datagram_header,
                    create_dict,parse_response,display_response,convert_to_ip_address)
from constants import ROUTER_IP,ROUTER_PORT
import sys
import argparse


def check_ack(response,sequence_number):
    decoded_response = get_payload(response[11:].decode('utf-8'))
    (packet_type, recieved_sequence_number, server_address, server_port) = convert_to_type(response)
    print('packet-type,sequence-number:', packet_type, recieved_sequence_number )
    if packet_type == 2 and sequence_number == recieved_sequence_number-1:
        return True
    else:
        return False

def send_request(socket,packet):
    socket.sendto(packet,(ROUTER_IP,ROUTER_PORT))

def receive_response(socket):
    return socket.recvfrom(1024)

def send_finish_message(socket,hostname,port):
    finish_ack_not_received = True
    datagram_header=get_datagram_header(hostname, port, 5, 10000)
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
    print('Payload Finished sending, Now Server will send the response for the whole request.')
    return True

def receive_response_from_server(socket,hostname,port):
    response_buffer={}
    final_response=''
    all_data_have_not_arrived=True
    datagram_header=get_datagram_header(hostname, port, 2, 20000)
    ack_packet=datagram_header
    send_request(socket, ack_packet)
    while all_data_have_not_arrived:
        response_data,router_address=receive_response(socket)
        response = get_payload(response_data[11:].decode('utf-8'))
        (packet_type, sequence_number, server_address, server_port) = convert_to_type(response_data)
        print('>>>>>>>>>>>>>>',server_address)
        if packet_type == 4:
            if sequence_number not in response_buffer:
                response_buffer[sequence_number] = get_payload(response_data[11:].decode('utf-8'))
            response_packet_header = get_datagram_header(server_address,server_port,2,sequence_number+1)
            response_payload = 'ACK'.encode('utf-8')
        elif packet_type==5:
            sorted_buffer=sort_buffer(response_buffer)
            final_response=get_request(sorted_buffer)
            print('>>Final Response',final_response)
            response_packet_header = get_datagram_header(server_address, server_port,6, sequence_number + 1)
            response_payload = 'FIN ACK'.encode('utf-8')
            all_data_have_not_arrived=False
        response_packet = response_packet_header + response_payload
        send_request(socket,response_packet)
    return final_response


def connect_to_server(socket,hostname,port):
    sync_ack_not_received = True
    datagram_header = get_datagram_header(hostname, port, 0, 1)
    sync_packet = datagram_header
    while sync_ack_not_received:
        try:
            send_request(socket,sync_packet)
            response_data,router_address=receive_response(socket)
            response = get_payload(response_data[11:].decode('utf-8'))
            (packet_type, sequence_number,server_address,server_port) = convert_to_type(response_data)
            if packet_type==1:
                sync_ack_not_received=False
        except socket.timeout:
            print('Socket-Timeout resending packet again')
            continue
    print('Connection Establish, Now send data.')
    return True

def send_udp_request(datagram_payload,hostname,port):
    final_response=''
    client_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_udp_socket.settimeout(10)
    sync_with_server=connect_to_server(client_udp_socket,hostname,port)
    udp_data_headers=[]
    frames=[datagram_payload[0:i+1013] for i in range(0,len(datagram_payload),1011)]
    packet_ack_not_received = [True for i in range(0, len(frames))]
    datagram_frames=[]
    all_packet_reached =True
    send_finish_message_to_server=False
    if sync_with_server:
        for i in range(0, len(frames)):
            sequence_number=2000 + i
            udp_data_headers.append(get_datagram_header(hostname, port, 4, sequence_number))
            print(udp_data_headers)
            datagram_frames.append(udp_data_headers[i]+frames[i])
            while(packet_ack_not_received[i]):
                try:
                    send_request(client_udp_socket,datagram_frames[i])
                    response_data, server_address = receive_response(client_udp_socket)
                    correct_ack=check_ack(response_data,sequence_number)
                    if correct_ack:
                        packet_ack_not_received[i] = False
                except socket.timeout:
                    print(f'Socket timeout for Packet: {i}. Resending...')
                    continue

        for _ in packet_ack_not_received:
            print(_)
            if _ == True:
                all_packet_reached=False

        if all_packet_reached:
            send_finish_message_to_server=send_finish_message(client_udp_socket,hostname,port)

        final_response=receive_response_from_server(client_udp_socket,hostname,port)
    print('Client Connection Closed')
    client_udp_socket.close()
    return final_response



def get_http(args,location):
    url=args.url
    #parse the attribute of the url with custom resolve_url method.
    hostname,port,path,params=resolve_url(url)
    print(hostname)
    #to store the response of the request
    response = b""
    #list for for the header components.
    headers={}
    #if there is any data in the request
    body=''
    # check value of location to change the path if it is a redirect request.
    if location:
        path = location
        print('redirecting to: ',path)
    #check if there is a header in the request, if yes split them and save in a list.
    if args.header:
        headers = args.header[0].split(',')

    #if there is a query params in the request.
    if params:
        request = f"GET {path}?{params} HTTP/1.0\r\n"
    else:
        request = f"GET {path} HTTP/1.0\r\n"
    request += f"Host: {hostname}\r\n"
    #if there is a header in the request.
    for header in headers:
        request += f"{header}\r\n"
    request += f"Content-Length: {len(body)}\r\n\r\n"
    request += f"{body}"
    #convert request to datagram payload
    datagram_payload=request.encode('utf-8')
    return send_udp_request(datagram_payload,hostname,port)


# def main():
#     message='Hi Server'
    # # receive data back from the server.
    # (response_data,router_address)=client_socket.recvfrom(1024)
    # resonse_header=convert_to_type(response_data[:11])
    # response_payload=get_payload(response_data[11:].decode('utf-8'))
    # print(response_payload)
    # client_socket.close()

if __name__=='__main__':
    description_text = ''
    # descriptions for the help
    if (len(sys.argv) == 2 and sys.argv[1] == '--help'):
        print('httpc --help\nhttpc is a curl-like application but supports HTTP protocol only.')
        description_text = """The commands are:
            -    get executes a HTTP GET request and prints the response.
            -    post executes a HTTP POST request and prints the response.
            -    help prints this screen.

            Use "httpc help [command]" for more information about a command.
            """
    elif (len(sys.argv) == 3 and sys.argv[1] == 'get' and sys.argv[2] == '--help'):
        print('httpc get --help')
        description_text = """Get executes a HTTP GET request for a given URL
                -v Prints the detail of the response such as protocol, status,
                    and headers.
                -h key:value Associates headers to HTTP Request with the format 'key:value'.
                """
    elif (len(sys.argv) == 3 and sys.argv[1] == 'post' and sys.argv[2] == '--help'):
        print('httpc post --help')
        description_text = """Post executes a HTTP POST request for a given URL with inline data or from file.
                -v Prints the detail of the response such as protocol, status, and headers.
                -h key:value Associates headers to HTTP Request with the format 'key:value'.
                -d string Associates an inline data to the body HTTP POST request.
                -f file Associates the content of a file to the body HTTP POSTrequest.
            Either [-d] or [-f] can be used but not both.
                """

    # argparser to parse a command line arguments.
    parser = argparse.ArgumentParser(description=description_text, add_help=False,
                                     formatter_class=argparse.RawTextHelpFormatter, usage="httpc [argument] command")
    parser.add_argument('--help', default=argparse.SUPPRESS, action='help', help=argparse.SUPPRESS)
    # subparser for http methods.
    subparsers = parser.add_subparsers(dest='method')
    # Arguments for the GET requests.
    get_parser = subparsers.add_parser('get', description=description_text, usage="httpc get [-v] [-h key:value] URL",
                                       add_help=False, formatter_class=argparse.RawTextHelpFormatter)
    get_parser.add_argument('--help', default=argparse.SUPPRESS, action='help', help=argparse.SUPPRESS)
    get_parser.add_argument('-v', '--verbose', action='count', default=0)
    get_parser.add_argument('-h', '--header', action='append', type=str, help='Header of the request')
    get_parser.add_argument('url', type=str)
    get_parser.add_argument('-o', '--filetowrite', type=str)
    # Arguments for the POST requests.
    post_parser = subparsers.add_parser('post', description=description_text,
                                        usage="httpc post [-v] [-h key:value]  [-d inline-data] [-f file]  URL",
                                        add_help=False, formatter_class=argparse.RawTextHelpFormatter)
    post_parser.add_argument('--help', default=argparse.SUPPRESS, action='help', help=argparse.SUPPRESS)
    post_parser.add_argument('-v', '--verbose', action='count', default=0)
    post_parser.add_argument('-h', '--header', action='append', type=str, help='Header of the request')
    post_parser.add_argument('-d', '--data', metavar='Data', type=str, help='Data for post requests.')
    post_parser.add_argument('-f', '--file', metavar='File', type=str, help='File for the post request')
    post_parser.add_argument('url', type=str)
    post_parser.add_argument('-o', '--filetowrite', type=str)

    # argument dictionary is assigned to a variable.
    args = parser.parse_args()
    method = args.method
    print('Arguments: ', args)

    # Check whether there is data or file in the post request or not
    if method == 'post' and not (args.data or args.file):
        parser.error('-d or -f should be used with post to provide data or file')
    # Check if there is both data and the file in the post request
    elif method == 'post' and (args.data and args.file):
        parser.error('either -d or -f should be used but not both with post')

    # get method implementation
    if method == 'get':
        location = ''  # location is used to store redirect location
        redirect = 0  # to count number of redirect
        while redirect < 10:
            response = get_http(args, location)
            print('Finally response is here',response)
            # fetch the attributes of the response
            headers, body, status_line, status_code, status_message = parse_response(response)
            # Display the response.
            display_response(headers, body, args.verbose, args.filetowrite, status_code, status_message)
            headers_dict = create_dict(headers)

            # check for the status code
            if int(status_code) >= 300 and int(status_code) < 400:
                # fetching redirect location
                if "location" in headers_dict:
                    location = headers_dict['location']
                    redirect += 1
                    continue
                # if there is no location in the header then break the loop
                else:
                    break
            # if status code is not redirect get out of the loop
            else:
                break

    # post method implementation
    # elif method == 'post':
    #     response = post_http(args)
    #     # fetch the attributes of the response
    #     headers, body, status_line, status_code, status_message = parse_response(response.decode())
    #     # Display the response.
    #     display_response(headers, body, args.verbose, args.filetowrite, status_code, status_message)

    # if the request is not get or post
    else:
        print('Invaild Http Method!')

# def convert_to_ascii_list(str):
#     list=[]
#     for c in str:
#         list.append(ord(c))
#     return list