import binascii
import sys

import client
import metainfo
import peer_connection
import select
import socket

connect = 0
announce = 1


class Session(object):
    def __init__(self, torrentFile):
        self.metainfo_file = metainfo.MetainfoFile(torrentFile)
        self.client = client.Client()
        self.sock = 0
        self.host = self.metainfo_file.announce_url_and_port[0]
        self.port = self.metainfo_file.announce_url_and_port[1]
    
    def connect_to_tracker(self):
        timeout = 1
        self.sock = self.client.open_socket_with_timeout(timeout)
        print 'Socket created.\n'
        
        connection_packet = self.client.make_connection_packet()
        response, address = self.client.send_packet(self.sock, self.host, self.port, connection_packet)
        return response
        
    def announce(self):
        announce_packet = self.client.make_announce_packet(self.metainfo_file.total_length, self.metainfo_file.bencoded_info_hash)
        response, address = self.client.send_packet(self.sock, self.host, self.port, announce_packet) 
        return response
    
    def get_torrent(self):
        connection_response = self.connect_to_tracker()
        connection_status = self.client.check_packet(connect, connection_response)
        self.check_status(connection_status, "connect")
        
        announce_response = self.announce()
        announce_status = self.client.check_packet(announce, announce_response)
        self.check_status(announce_status, "announce")
        
        peer_list = self.client.get_list_of_peers(announce_response)
                
        waiting_for_read = []
        waiting_for_write = []
        for peer_info_list in peer_list:   
            peer = self.client.build_peer(peer_info_list, self.metainfo_file.num_pieces, self.metainfo_file.bencoded_info_hash)
            peer.schedule_handshake(self.client.peer_id)
            waiting_for_read.append(peer)
            try:
                peer.sock.connect((peer.ip, peer.port))
            except socket.error as e:
                print e
                pass
        
        while waiting_for_read or waiting_for_write:
            for peer in waiting_for_read:
                if peer.out_buffer and (peer not in waiting_for_write):
                    waiting_for_write.append(peer)
            
            readable, writeable, errors = select.select(waiting_for_read, waiting_for_write, [])
#             print "selected: "
            print len(readable), len(writeable), len(errors)
            
            print "writeables" 
            for peer in writeable:
                print peer
                print "******* OUT BUFFER"
                print repr(peer.out_buffer)
                success = peer.send_from_out_buffer()
                if not success:
                    print "could not send"
                    pass
                else:
                    print "SENT"
            
            
            print "readables"
            for peer in readable:
                print peer
                try:
                    response = peer.sock.recv(1024)
                    print "~~~~~~~ response!!!"
                    print repr(response)
                except socket.error as e:
                    print e
                    continue
                peer.in_buffer += response
                while peer.handle_in_buffer():
                    pass
                    
        
        self.sock.close()

    def check_status(self, status, failure):
        if status < 0:
            print "Session: " + failure
            sys.exit(1)

def main():
    s = Session('../../walden.torrent')
    s.get_torrent()

if __name__ == '__main__':
    main()