import queue
import threading
import operator
import ast
from collections import namedtuple

class RouterMessage:
    tbl_len = 30
    name_length = 5

    def __init__(self, router_name, table):
        self.table = table
        self.router_name = router_name

    def to_byte_S(self):
        # fancy stuff:
        byte_S = str(self.router_name).zfill(self.name_length)
        byte_S += str(self.table).zfill(self.tbl_len)
        return byte_S

    @classmethod
    def from_byte_S(self, byte_S):
        router_name = byte_S[:self.name_length]
        table = byte_S[self.name_length:]
        table = ast.literal_eval(table.strip('0'))
        return self(router_name, table)

# wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, name, maxsize=0):
        self.name = name
        self.in_queue = queue.Queue(maxsize)
        self.out_queue = queue.Queue(maxsize)
    
    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None
        
    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)
            
        
## Implements a network layer packet.
class NetworkPacket:
    ## packet encoding lengths 
    dst_S_length = 5
    prot_S_length = 1
    
    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst, prot_S, data_S):
        self.dst = dst
        self.data_S = data_S
        self.prot_S = prot_S
        
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()
        
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
        if self.prot_S == 'data':
            byte_S += '1'
        elif self.prot_S == 'control':
            byte_S += '2'
        else:
            raise('%s: unknown prot_S option: %s' %(self, self.prot_S))
        byte_S += self.data_S
        return byte_S
    
    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst = byte_S[0 : NetworkPacket.dst_S_length].strip('0')
        prot_S = byte_S[NetworkPacket.dst_S_length : NetworkPacket.dst_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise('%s: unknown prot_S field: %s' %(self, prot_S))
        data_S = byte_S[NetworkPacket.dst_S_length + NetworkPacket.prot_S_length : ]
        return self(dst, prot_S, data_S)
    

    

## Implements a network host for receiving and transmitting data
class Host:
    
    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface("network")]
        self.stop = False #for thread termination

    ## called when printing the object
    def __str__(self):
        return self.addr
       
    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst, data_S):
        p = NetworkPacket(dst, 'data', data_S)
        print('%s: sending packet "%s"' % (self, p))
        self.intf_L[0].put(p.to_byte_S(), 'out') #send packets always enqueued successfully
        
    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.intf_L[0].get('in')
        if pkt_S is not None:
            print('%s: received packet "%s"' % (self, pkt_S))
       
    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return

all_dest = ['H1', 'H2', 'H3',  'RA', 'RB','RC', 'RD']

## Implements a multi-interface router
class Router:

    Intf_data = namedtuple('Intf_data',['name','port'])
    def __init__(self, name, cost_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.neb_routers = [self.Intf_data(self.name,None)]
        self.intf_L = dict()
        self.fastest_D = dict()
        self.cost_D = cost_D    # {neighbor: {interface: cost}}
        
        print("costs: ",cost_D)
        self.rt_tbl_D = {}      # {destination: {router: cost}}
        for dest, interfaces in cost_D.items():
            assert(len(interfaces.keys()) == 1)
            for port, cost in interfaces.items():
                self.intf_L[port] = Interface(dest, max_queue_size)
                self.rt_tbl_D.update({dest:{self.name:cost}})
                self.fastest_D.update({dest:port})
            if 'R' in dest:
                self.neb_routers.append(self.Intf_data(dest, port))
        # cost to self is always zero:
        self.rt_tbl_D.update({self.name:{self.name:0}})
        self.neb_routers.sort(key=operator.itemgetter(0))
        print("neb_routers ", self.neb_routers)
        print(self.name, "interfaces: ")
        for port, intf in self.intf_L.items():
            print("port: ", port, "name ", intf.name)
        print('%s: Initialized routing table' % self)
        self.print_routes()


    ## called when printing the object
    def __str__(self):
        return self.name


    ## look through the content of incoming interfaces and
    # process data and control packets
    def process_queues(self):
        for i, interface in self.intf_L.items():
            pkt_S = None
            #get packet from interface i
            pkt_S = self.intf_L[i].get('in')
            #if packet exists make a forwarding decision
            if pkt_S is not None:
                p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                if p.prot_S == 'data':
                    self.forward_packet(p,i)
                elif p.prot_S == 'control':
                    mssg = RouterMessage.from_byte_S(p.data_S)
                    self.update_routes(mssg, self.intf_L[i].name)
                else:
                    raise Exception('%s: Unknown packet type in packet %s' % (self, p))
            

    ## forward the packet according to the routing table
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def forward_packet(self, p, i):
        try:
            # TODO: Here you will need to implement a lookup into the 
            # forwarding table to find the appropriate outgoing interface
            # for now we assume the outgoing interface is 1
            forward_port = self.fastest_D[p.dst]
            self.intf_L[forward_port].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % \
                (self, p, i, forward_port))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass


    ## send out route update
    # @param i Interface number on which to send out a routing update
    def send_routes(self, i):
        # TODO: Send out a routing table update
        #create a routing table update packet
        p = NetworkPacket(0, 'control',  RouterMessage(self.name, self.build_update_tbl() ).to_byte_S())
        try:
            #TODO: add logic to send out a route update
            print('%s: sending routing update "%s" from interface %d' % (self, p, i))
            self.intf_L[i].put(p.to_byte_S(), 'out', True)
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass

    def build_update_tbl(self):
        tbl = dict()
        for dest, routers in self.rt_tbl_D.items():
            tbl[dest] = routers[self.name]
        return tbl


    #  @param p Packet containing routing information
    def update_routes(self, p, intf_name):
        print('%s: Received routing update %s from interface %s' % (self, p, intf_name))
        print("updates: ",p.table)
        # update the table for the ports you just recieved:
        for host, cost in p.table.items():
            if host in self.rt_tbl_D.keys():
                self.rt_tbl_D[host][intf_name] = cost
            else:
                self.rt_tbl_D[host] = dict()
                self.rt_tbl_D[host][intf_name] = cost
        change = False
        # check to see if anything in your table changes:
        for dest, cost in p.table.items():
            new_cost = self.rt_tbl_D[intf_name][self.name] + cost
            if self.name in self.rt_tbl_D[dest].keys():
                old_cost = self.rt_tbl_D[dest][self.name]
            else:
                old_cost = float("inf")
            # print("dest: ", dest,"new cost: ",new_cost,"old_cost: ", old_cost)
            if new_cost < old_cost:
                self.rt_tbl_D[dest][self.name] = new_cost
                for port, intf in self.intf_L.items():
                    if intf.name == intf_name:
                        self.fastest_D[dest] = port
                        break
                # print("\n\n\nNew fastest port to %s: %d using router %s\n\n\n" % (dest, self.fastest_D[dest], intf_name))
                change = True
        if change:
            self.print_routes()
            for neghbor_data in self.neb_routers:
                if neghbor_data.name != self.name:
                    self.send_routes(neghbor_data.port)


    ## Print routing table
    print_lock = threading.Lock()
    def print_routes(self):
        self.print_lock.acquire()
        print("\n")
        print(self.name," ", end='')
        for dest in all_dest:
            print(dest," ",end='')
        print()
        for index, router in enumerate(self.neb_routers):
            # if index == 0:
            #     print("From ", end='')
            # else:
            #     print("     ", end='')
            print(router.name + "  ", end='')
            for dest in all_dest:
                if dest in self.rt_tbl_D.keys():
                    if router.name in self.rt_tbl_D[dest].keys():
                        print(str(self.rt_tbl_D[dest][router.name]) + "   ",end='')
                    else:
                        print("-   ", end='')
                else:
                    print("-   ", end='')
            print()
        print()
        self.print_lock.release()



    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return
