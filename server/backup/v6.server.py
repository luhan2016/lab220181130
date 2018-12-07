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
    def contact_vessel(vessel_ip, path, payload=None, req='POST'):
        # Try to contact another server (vessel) through a POST or GET, once
        time.sleep(1)
        success = False
        try:
            if 'POST' in req:
                res = requests.post('http://{}{}'.format(vessel_ip, path), data=payload)
            elif 'GET' in req:
                res = requests.get('http://{}{}'.format(vessel_ip, path))
            else:
                print 'Non implemented feature!'
            if res.status_code == 200:
                success = True
        except Exception as e:
            print e
        return success

    def propagate_to_vessels(path, payload = None, req = 'POST'):
        global vessel_list, node_id
        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) != node_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)

    # propage message to neighbor, if current node is the last node (next node is 1), then propage to vessel 1
    # if not the last node, then propage to node_id + 1, sine node_id + 1 is this node's neighbor
    def propagate_to_neighbour(path,  payload = None, req = 'POST'):
        global vessel_list, node_id
        time.sleep(1)
        for vessel_id, vessel_ip in vessel_list.items():
            if node_id == node_num-1:
                if int(vessel_id) == 1:
                    t = Thread(target = contact_vessel, args = (vessel_ip, path, payload, req))
                    t.daemon = True
                    t.start()
                    success = t.join()
                    if not success:
                        print "\n\nSNN Could not contact vessel {}\n\n".format(vessel_id)
            elif int(vessel_id) == node_id + 1:
                t = Thread(target = contact_vessel, args = (vessel_ip, path, payload, req))
                t.daemon = True
                t.start()
                success = t.join()
                if not success:
                    print "\n\nSNN1 Could not contact vessel {}\n\n".format(vessel_id)

    # each node generate their random number and then propagate this random number to it's neighbor and elsect leader
    def random_number():
        global election_dict, countEM
        token = random.randint(1,10000)
        election_dict = { node_id : token }
        print election_dict
        countEM = countEM + 1
        t = Thread( target = propagate_to_neighbour, args= ('/em2neighbor/{}'.format(countEM), election_dict,'POST'))
        t.daemon = True
        t.start()
        
    # received entry or message from webpage send to leader first, the leader will propagate to all other vessels
    def propagate_to_leader(path, payload = None, req = 'POST'):
        global vessel_list, node_id, entry_sequence_index, leader_dict, leader_id, leader_rNum
        print leader_dict
        for vessel_id, vessel_ip in vessel_list.items():
            if int(vessel_id) == leader_id: # don't propagate to yourself
                success = contact_vessel(vessel_ip, path, payload, req)
                if not success:
                    print "\n\nCould not contact vessel {}\n\n".format(vessel_id)


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
        print board  #no input, print nothing
        return template('server/boardcontents_template.tpl',board_title='Vessel {}'.format(node_id), board_dict=sorted(board.iteritems()))
    # ------------------------------------------------------------------------------------------------------
    
    # send the received message from webpage to leader
    @app.post('/board')
    def client_add_received():
        '''Adds a new element to the board 
        Called directly when a user is doing a POST request on /board'''
        global board, node_id, entry_sequence_index
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

    # send the received updated message to leader or send the delete node info to leader
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
            elif int(action_dom) == 1:
                t = Thread(target=propagate_to_leader, args = ('/entry2leader/delete/{}'.format(element_id),)) 
                t.daemon = True
                t.start()
            return True
        except Exception as e:
            print e
        return False

    # check the action is add, modify or delete, if it's modify, then update the store, if it's delete, then remove the node
    @app.post('/propagate/<action>/<element_id:int>')
    def propagation_received(action, element_id):
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


    # send election message to neighbor and compare the neighbor random numer with the random number in leader_dict,
    # if current random number is larger than the leader_dict, then update the leader_dict
    # if traves all nodes, then go to the coordernate parts, otherwise send the leader_dict to the next neighbor and compare and update leader_dict
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
            print leader_dict
            leader_id = leader_dict.keys()[0]
            leader_rNum = leader_dict[leader_id]
            countCM = countCM + 1
            t = Thread( target = propagate_to_neighbour, args= ('/cm2neighbor/{}'.format(countCM), leader_dict,'POST'))
            t.daemon = True
            t.start()
        else:
            countEM = countEM + 1
            t = Thread(target=propagate_to_neighbour, args =('/em2neighbor/{}'.format(countEM), leader_dict,'POST'))
            t.daemon = True
            t.start()


    # send coordinator message to your neighbor
    # solution idead: if each node has the same leader, then received_coordinate_dict  will only has one kek pair (the leader key pair)
    # otherwise the system has several leaders, should select the leader again, this is for the optinal parts, we didn't implement the optional part
    @app.post('/cm2neighbor/<cmessage_id:int>')
    def coordination_message(cmessage_id):
        global countCM, node_num, leader_dict, countLeader
        time.sleep(1)
        try:
            body = request.body.read()
            a, b = body.split('=')
            received_coordinate_dict = {int(a) : int(b)}
            countCM = countCM + 1
            if countCM == node_num:
                for k,v in received_coordinate_dict.items():
                    countLeader = countLeader +1
                if countLeader == 1:
                    print "finish coordination & all nodes agree with the leadership\n\n"
                else:
                    print "someone has a different leader, please choose the leader again\n\n"
                    #t = Thread(target = random_number)
                    #t.daemon = True
                    #t.start()
            else:
                t = Thread(target=propagate_to_neighbour, args =('/cm2neighbor/{}'.format(countCM), received_coordinate_dict,'POST'))
                t.daemon = True
                t.start()
        except Exception as e:
            print e


    @app.post('/entry2leader/<action>/<element_id:int>')
    def entry_leader(action, element_id):
        # check the action is add, modify or delete
        global board, node_id, entry_sequence_index, received_election_dict, election_dict, countEM, node_num
        time.sleep(1)
        try:
            if action == 'add':
                body = request.body.read()
                add_new_element_to_store(entry_sequence_index, body) # you might want to change None here
                t = Thread(target=propagate_to_vessels, args = ('/propagate/add/{}'.format(entry_sequence_index),body,'POST')) 
                t.daemon = True
                t.start()
                entry_sequence_index = entry_sequence_index + 1
            elif action == 'modify':
                body = request.body.read()
                modify_element_in_store(element_id, body)
                t = Thread(target=propagate_to_vessels, args = ('/propagate/modify/{}'.format(element_id),body,'POST')) 
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
        # We need to write the other vessels IP, based on the knowledge of their number
        for i in range(1, args.nbv):
            vessel_list[str(i)] = '10.1.0.{}'.format(str(i))

        # when start the main(), start the random number generator
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
