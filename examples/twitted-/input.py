#!/usr/bin/env python
#
# Copyright 2011 Splunk, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"): you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""This utility reads the Twitter 'spritzer' and writes status results 
   (aka tweets) to Splunk for indexing."""

# UNDONE: Hardening ..
#   * Script doesn't handle loss of the twitter HTTP connection or the Splunk
#     TCP connection
# UNDONE: Command line args - Splunk host/port
# UNDONE: Basic auth will be disabled in August/2010 .. need to support OAuth2

from pprint import pprint # UNDONE

import base64
import httplib
import json
import socket
import sys

import splunk

TWITTER_STREAM_HOST = "stream.twitter.com"
TWITTER_STREAM_PATH = "/1/statuses/sample.json"

SPLUNK_HOST = "localhost"
SPLUNK_PORT = 9001

ingest = None       # The splunk ingest socket
verbose = True

class Twitter:
    def __init__(self, username, password):
        self.buffer = ""
        self.username = username
        self.password = password

    def connect(self):
        # Login using basic auth
        login = "%s:%s" % (self.username, self.password)
        token = "Basic " + str.strip(base64.encodestring(login))
        headers = {
            'Content-Length': "0",
            'Authorization': token,
            'Host': "stream.twitter.com",
            'User-Agent': "twitted.py/0.1",
            'Accept': "*/*",
        }
        connection = httplib.HTTPConnection(TWITTER_STREAM_HOST)
        connection.request("GET", TWITTER_STREAM_PATH, "", headers)
        response = connection.getresponse()
        if response.status != 200:
            raise Exception, "HTTP Error %d (%s)" % (
                response.status, response.reason)
        return response

RULES = {
    'tusername': {
        'flags': ["--twitter:username"],
        #'default': None,
        'help': "Twitter username",
    },
    'tpassword': { 
        'flags': ["--twitter:password"],
        #'default': None,
        'help': "Twitter password",
    },
}

def cmdline():
    from getpass import getpass
    from utils.cmdopts import parse

    kwargs = parse(sys.argv[1:], RULES, ".splunkrc").kwargs

    # Prompt for Twitter username/password if not provided on command line
    if not kwargs.has_key('tusername'):
        kwargs['tusername'] = raw_input("Twitter username: ")
    if not kwargs.has_key('tpassword'):
        kwargs['tpassword'] = getpass("Twitter password:")

    # Prompt for Splunk username/password if not provided on command line
    if not kwargs.has_key('username'):
        kwargs['username'] = raw_input("Splunk username: ")
    if not kwargs.has_key('password'):
        kwargs['password'] = getpass("Splunk password:")

    return kwargs

# Returns a str, dict or simple list
def flatten(value, prefix=None):
    """Takes an arbitrary JSON(ish) object and 'flattens' it into a dict
       with values consisting of either simple types or lists of simple
       types."""

    def issimple(value): # foldr(True, or, value)?
        for item in value:
            if isinstance(item, dict) or isinstance(item, list):
                return False
        return True

    if isinstance(value, unicode):
        return value.encode("utf8")

    if isinstance(value, list):
        if issimple(value): return value
        offset = 0
        result = {}
        prefix = "%d" if prefix is None else "%s.%%d" % prefix
        for item in value:
            k = prefix % offset
            v = flatten(item, k)
            if not isinstance(v, dict): v = {k:v}
            result.update(v)
            offset += 1
        return result

    if isinstance(value, dict):
        result = {}
        prefix = "%s" if prefix is None else "%s.%%s" % prefix
        for k,v in value.iteritems():
            k = prefix % str(k)
            v = flatten(v, k)
            if not isinstance(v, dict): v = {k:v}
            result.update(v)
        return result

    return value

def listen(username, password):
    twitter = Twitter(username, password)
    stream = twitter.connect()
    buffer = ""
    while True:
        offset = buffer.find("\r\n")
        if offset != -1:
            status = buffer[:offset]
            buffer = buffer[offset+2:]
            process(status)
            continue # Consume all statuses in buffer before reading more
        buffer += stream.read(2048)

def output(record):
    global splunk, verbose

    if verbose: print_record(record)

    for k, v in record.iteritems():
        if v is None or k.endswith("_str"):
            continue # Ignore

        if isinstance(v, list):
            if len(v) == 0: continue
            v = ','.join([str(item) for item in v])

        format = '%s:"%s" ' if isinstance(v, str) else "%s:%r "
        result = format % (k, v)

        #print result
        ingest.send(result)

    ingest.send("\r\n")

def print_record(record):
    if record.has_key('delete.status.id'):
        print "delete %d %d" % (
            record['delete.status.id'],
            record['delete.status.user_id'])
    else:
        print "status %s %d %d" % (
            record['created_at'], 
            record['id'], 
            record['user.id'])

def process(status):
    status = json.loads(status)
    record = flatten(status)
    output(record)

def main():
    kwargs = cmdline()

    print "Initializing Splunk .."
    service = splunk.client.connect(**kwargs)

    if "twitter" not in service.indexes.list():
        print "Creating index 'twitter' .."
        service.indexes.create("twitter")

    # UNDONE: Ensure index exists
    # UNDONE: Ensure TCP input is configured
    # UNDONE: Ensure twitter sourcetype is defined

    global ingest
    ingest = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ingest.connect((SPLUNK_HOST, SPLUNK_PORT))
    ingest.send("***SPLUNK*** sourcetype=twitter\n") # Initialize stream

    print "Listening .."
    listen(kwargs['tusername'], kwargs['tpassword'])
        
if __name__ == "__main__":
	main()

