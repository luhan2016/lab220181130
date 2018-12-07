# coding=utf-8
# ------------------------------------------------------------------------------------------------------
# TDA596 - Lab 1
# server/server.py
# Input: Node_ID total_number_of_ID
# Student: John Doe
# ------------------------------------------------------------------------------------------------------
import traceback
import sys
import time
import json
import argparse

from threading import Thread

from bottle import Bottle, run, request, template
import requests
import random
import ast
import urllib
import operator
# ------------------------------------------------------------------------------------------------------
try:
    app = Bottle()

    board = {0:"nothing"} 


    # ------------------------------------------------------------------------------------------------------
    # BOARD FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    def add_new_element_to_store(entry_sequence, element, is_propagated_call=False):
        global board, node_id
        success = False
        try:
            board[entry_sequence] = element
            success = True
        except Exception as e:
            print e
        return success

    def modify_element_in_store(entry_sequence, modified_element, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            board[entry_sequence] = modified_element
            success = True
        except Exception as e:
            print e
        return success

    def delete_element_from_store(entry_sequence, is_propagated_call = False):
        global board, node_id
        success = False
        try:
            board.pop(entry_sequence)  
            success = True
        except Exception as e:
            print e
        return success

    # ------------------------------------------------------------------------------------------------------
    # DISTRIBUTED COMMUNICATIONS FUNCTIONS
    # ------------------------------------------------------------------------------------------------------
    # contact vessel, here we add a variable called leaderElected, this is used for avoid duplicated received message
    # if the leader is elected, for the dead node, do not propage to next neighbor
    def contact_vessel(vessel_id, vessel_ip, path, payload=None, req='POST', leaderElected=False):
        time.sleep(1)
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            if res.status_code == 200:
                success = True
        except Exception as e:
            if leaderElected == False:
                success = contact_deadnode_neighbor(vessel_id, vessel_ip, path, payload, req='POST')
        return success

    # when contact_verssel() can not reach the node, that means the node is dead, and we should contact the neighbor of dead node
    def contact_deadnode_neighbor(vessel_id, vessel_ip, path, payload=None, req='POST'):
        print("node " + vessel_id + " is dead")   
        dead_nodeID = vessel_id
        for vessel_id_next, vessel_ip_next in vessel_list.items():         
            if int(dead_nodeID) == int(node_num) -1 and int(vessel_id_next) == 1:
                contact_vessel(vessel_id_next, vessel_ip_next, path, payload, 'POST')
            elif int(vessel_id_next) == int(dead_nodeID)+ 1:
                contact_vessel(vessel_id_next, vessel_ip_next, path, payload, 'POST')
        return True

    def propagate_to_vessels(path, payload = None, req = 'POST', leaderElected=False):
        global vessel_list, node_id
        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id : # don't propagate to yourself
                success = contact_vessel(vessel_id, vessel_ip, path, payload, req, leaderElected)
                if not success:
                    print "Could not contact vessel {}".format(vessel_id)

    # propage received payload to neighbor, the if elif condition is used to check who is the next neighbor
    def propagate_to_neighbour(path,  payload = None, req = 'POST'):
        global vessel_list, node_id
        time.sleep(1)
        for vessel_id, vessel_ip in vessel_list.items():
            if node_id == node_num-1:
                if int(vessel_id) == 1:
                    t = Thread(target = contact_vessel, args = (vessel_id, vessel_ip, path, payload, req))
                    t.daemon = True
                    t.start()
            elif int(vessel_id) == node_id + 1:
                t = Thread(target = contact_vessel, args = (vessel_id, vessel_ip, path, payload, req))
                t.daemon = True
                t.start()

    # random number function creats random number for each node and propage the random number with node id to neighbor
    def random_number():
        global election_dict, countEM
        token = random.randint(1,10000)
        election_dict = { node_id : token }
        print("\nnode " + str(node_id) + " has random numer " + str(token) + "\nStart election\n")
        #time.sleep(1)
        countEM = countEM + 1
        t = Thread( target = propagate_to_neighbour, args= ('/em2neighbor/{}'.format(countEM), election_dict,'POST'))
        t.daemon = True
        t.start()
        

    # propagete received meaage to leader first
    def propagate_to_leader(path, payload = None, req = 'POST'):
        global vessel_list, node_id, entry_sequence_index, leader_dict, leader_id, leader_rNum
        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) == leader_id: # don't propagate to yourself
                success = contact_vessel(vessel_id, vessel_ip, path, payload, req)
                if not success:
                    print "Could not contact vessel {}".format(vessel_id)


    # ------------------------------------------------------------------------------------------------------
    # ROUTES
    # ------------------------------------------------------------------------------------------------------
    # a single example (index) should be done for get, and one for post
    # ------------------------------------------------------------------------------------------------------
    @app.route('/')
    def index():
        global board, node_id,leader_id,leader_rNum
        return template('server/index.tpl', board_title='Vessel {}'.format(node_id), \
               board_dict=sorted(board.iteritems()),  \
               IMleader = leader_id, leader_random_number = leader_rNum, \
               members_name_string='lhan@student.chalmers.se;shahn@student.chalmers.se')

    @app.get('/board')
    def get_board():
        global board, node_id
        print board  
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()))
    # ------------------------------------------------------------------------------------------------------

    # propage received message from webpage to leader first, and the leader willl update the store, then the leader will propage received message to other vessels
    @app.post('/board')
    def client_add_received():
        '''Adds a new element to the board , Called directly when a user is doing a POST request on /board'''
        global board, node_id, entry_sequence_index, countEM, election_dict
        try:
            new_entry = request.forms.get('entry') # new_entry is the user input from webpage
            # change board value from nothing to new_entry
            # propagate threads to avoid blocking,create the thread as a deamon
            t = Thread(target=propagate_to_leader, args = ('/entry2leader/add/{}'.format(entry_sequence_index),new_entry,'POST')) 
            t.daemon = True
            t.start()
            return True
        except Exception as e:
            print e
        return False

    # when receive modify or delete message from webpage, propage these message to leader first, then the leader will propage to others
    @app.post('/board/<element_id:int>/')
    def client_action_received(element_id):
        global board, node_id,entry_sequence_index
        try:
            # try to get user click, action_dom is action delete or modify
            action_dom = request.forms.get('delete') 
            if int(action_dom) == 0:
                modified_element = request.forms.get('entry') 
                t = Thread(target=propagate_to_leader, args = ('/entry2leader/modify/{}'.format(element_id),modified_element,'POST')) 
                t.daemon = True
                t.start()
                #modify_element_in_store(element_id, modified_element, is_propagated_call = False)
                #propagate_to_vessels('/propagate/modify/{}'.format(element_id),modified_element,'POST')
            elif int(action_dom) == 1:
                t = Thread(target=propagate_to_leader, args = ('/entry2leader/delete/{}'.format(element_id),)) 
                t.daemon = True
                t.start()
            return True
        except Exception as e:
            print e
        return False

    # according to the received action, decide modify the entry store
    @app.post('/propagate/<action>/<element_id:int>')
    def propagation_received(action, element_id):
        # check the action is add, modify or delete
        global board, node_id, entry_sequence_index, received_election_dict, election_dict, countEM, node_num
        try:
            if action == 'add':
                body = request.body.read()
                add_new_element_to_store(entry_sequence_index, body) # you might want to change None here
                entry_sequence_index = entry_sequence_index + 1
            elif action =='modify':
                body = request.body.read()
                modify_element_in_store(element_id, body)
            elif action == 'delete':
                delete_element_from_store(element_id)
            template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()))
            return True
        except Exception as e:
            print e
        return False


    # send election message to your neighbor, when finish sending to all nodes, start the coordinate message
    @app.post('/em2neighbor/<emessage_id:int>')
    def election_message(emessage_id):
        global received_election_dict, election_dict, countEM, countCM, node_num, leader_dict, leader_id, leader_rNum
        time.sleep(1)
        body = request.body.read()
        a, b = body.split('=')
        if int(b) > election_dict[node_id]:
            leader_dict = { int(a) : int(b)}
        else:
            leader_dict = { node_id : election_dict[node_id] }
        if countEM == node_num - 1:
            leader_id = leader_dict.keys()[0]
            leader_rNum = leader_dict[leader_id]
            print ("\nElection Done! vessel " + str(node_id) + " elects leader vessel" + str(leader_id) + " with random number " + str(leader_rNum))
            print "start coordinate phase\n"
            countCM = countCM + 1
            t = Thread( target = propagate_to_neighbour, args= ('/cm2neighbor/{}'.format(countCM), leader_dict,'POST'))
            t.daemon = True
            t.start()
        else:
            countEM = countEM + 1
            t = Thread(target=propagate_to_neighbour, args =('/em2neighbor/{}'.format(countEM), leader_dict,'POST'))
            t.daemon = True
            t.start()


    # send coordinator message to your neighbor and add your neighbor's leader in the received_coordinate_dict dictionary,
    # when after adding all nods' leader in the received_coordinate_dict, count how many elements in the dictionary
    # if all nodes have the same leader, then the received_coordinate_dict should only have one key pair, otherwise, some node has 
    # different leader as others
    @app.post('/cm2neighbor/<cmessage_id:int>')
    def coordination_message(cmessage_id):
        global countCM, node_num, leader_dict, countLeader, node_id
        time.sleep(1)
        try:
            body = request.body.read()
            a, b = body.split('=')
            received_coordinate_dict = {int(a) : int(b)}
            leader_id = leader_dict.keys()[0]
            leader_rNum = leader_dict[leader_id]
            received_coordinate_dict = {int(leader_id) : int(leader_rNum)}
            countCM = countCM + 1
            if countCM == node_num:
                for k,v in received_coordinate_dict.items():
                    countLeader = countLeader +1
                if countLeader == 1:
                    print ("\nfinish coordination & all nodes agree with the leadership of node " + str(leader_id) + " with random number "+ str(leader_rNum)+"\n")
                    return True
            else:
                t = Thread(target=propagate_to_neighbour, args =('/cm2neighbor/{}'.format(countCM), received_coordinate_dict,'POST'))
                t.daemon = True
                t.start()
        except Exception as e:
            print e
            print ("node " + str(node_id) + " doesn't agree with the leadership\n\n")
            return False

    # entry_leader function is the called after user input in the broswer send to the message to leader
    # the leader will check the action is add, modify or delete, and prpagate crosponding entry message to other vessles
    @app.post('/entry2leader/<action>/<element_id:int>')
    def entry_leader(action, element_id):
        global board, node_id, entry_sequence_index, received_election_dict, election_dict, countEM, node_num
        time.sleep(1)
        try:
            if action == 'add':
                body = request.body.read()
                add_new_element_to_store(entry_sequence_index, body) 
                t = Thread(target=propagate_to_vessels, args = ('/propagate/add/{}'.format(entry_sequence_index),body,'POST', True)) 
                t.daemon = True
                t.start()
                entry_sequence_index = entry_sequence_index + 1
            elif action == 'modify':
                body = request.body.read()
                modify_element_in_store(element_id, body)
                t = Thread(target=propagate_to_vessels, args = ('/propagate/modify/{}'.format(element_id),body,'POST',True)) 
                t.daemon = True
                t.start()
            elif action == 'delete':
                delete_element_from_store(element_id)
                t = Thread(target=propagate_to_vessels, args = ('/propagate/delete/{}'.format(element_id),)) 
                t.daemon = True
                t.start()
            template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()))
            return True
        except Exception as e:
            print e
        return False

    # ------------------------------------------------------------------------------------------------------
    # EXECUTION
    # ------------------------------------------------------------------------------------------------------
    # Execute the code
    def main():
        global vessel_list, node_id, app
        global entry_sequence_index, node_num
        global election_dict, countEM, countCM, leader_id, leader_rNum, countLeader

        entry_sequence_index = 0
        election_dict = {0:0}
        port = 80
        countEM = 0
        countCM = 0
        countLeader = 0
        parser = argparse.ArgumentParser(description='Your own implementation of the distributed blackboard')
        parser.add_argument('--id', nargs='?', dest='nid', default=1, type=int, help='This server ID')
        parser.add_argument('--vessels', nargs='?', dest='nbv', default=1, type=int, help='The total number of vessels present in the system')
        args = parser.parse_args()
        node_id = args.nid
        vessel_list = dict()
        node_num = args.nbv
        for i in range(1, args.nbv):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))
        #create a thread to generate random number for each node and compare the radom number
        t = Thread(target = random_number)
        t.daemon = True
        t.start()
        try:
            run(app, host=vessel_list[str(node_id)], port=port)
        except Exception as e:
            print e
    # ------------------------------------------------------------------------------------------------------
    if __name__ == '__main__':
        main()
except Exception as e:
        traceback.print_exc()
        while True:
            time.sleep(60.)

