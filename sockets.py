#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect, jsonify
from flask_sockets import Sockets
import gevent
from gevent import queue
from queue import Empty
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

clients = list()

def send_all(msg):
    for client in clients:
        client.put(msg)

def send(obj):
    send_all(json.dumps(obj))

class Client:
    def __init__(self) -> None:
        self.queue = queue.Queue()

    def put(self, msg):
        self.queue.put_nowait(msg)

    def get(self):
        return self.queue.get()


class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()

    def add_set_listener(self, listener):
        self.listeners.append(listener)

    def update(self, entity, key, value):
        entry = self.space.get(entity, dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners(entity)

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners(entity)

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity, dict())

    def world(self):
        return self.space


myWorld = World()


def set_listener(entity, data):
    ''' do something with the update ! '''
    # send updated data
    pass

myWorld.add_set_listener(set_listener)


@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return redirect("/static/index.html")


def read_ws(ws):
    '''A greenlet function that reads from the websocket and updates the world'''
    
    while True:
        msg = ws.receive()
        print("WS RECEIVE %s" % msg)
        if msg is not None:
            packet = json.loads(msg)
            entities = list(packet.keys())
            for entity in entities:
                for k, v in packet[entity].items():
                    myWorld.update(entity, k, v)
                send({entity: packet[entity]})
        else:
            break
    
    return


@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    client = Client()
    clients.append(client) 
    g = gevent.spawn(read_ws, ws)

    while True:
        try:
            msg = client.get()
            ws.send(msg)
        except Empty:
            continue
        except Exception as e:
            print(e)
            break
    print("Killed")
    clients.remove(client)
    gevent.kill(g)
    

    return


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])


@app.route("/entity/<entity>", methods=['POST', 'PUT'])
def update(entity):
    '''update the entities via this interface'''
    json = flask_post_json()
    myWorld["entity"] = json["entity"]
    return {'sccuess': 1}, 200


@app.route("/world", methods=['POST', 'GET'])
def world():
    '''you should probably return the world here'''
    if request.method != "GET":
        return {}, 405
    return jsonify(myWorld.world()), 200


@app.route("/entity/<entity>")
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    w = myWorld.get(entity)
    if w:
        return {entity:w}, 200
    return {'success': 0}, 404


@app.route("/clear", methods=['POST', 'GET'])
def clear():
    '''Clear the world out!'''
    if request.method == "GET":
        myWorld.clear()
        return {"success": 1}, 200
    return {"success": 0}, 405


if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
