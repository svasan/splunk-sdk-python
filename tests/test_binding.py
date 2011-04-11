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

# UNDONE: Test splunk namespace against baseline
# UNDONE: Test splunk.data loader

from pprint import pprint # UNDONE

from os import path
import sys
import unittest
import uuid
from xml.etree import ElementTree
from xml.etree.ElementTree import XML

import splunk
import splunk.data as data
import tools.cmdopts as cmdopts

# splunkd endpoint paths
PATH_USERS = "authentication/users"

# XML Namespaces
NAMESPACE_ATOM = "http://www.w3.org/2005/Atom"
NAMESPACE_REST = "http://dev.splunk.com/ns/rest"
NAMESPACE_OPENSEARCH = "http://a9.com/-/spec/opensearch/1.1"

# XML Extended Name Fragments
XNAMEF_ATOM = "{%s}%%s" % NAMESPACE_ATOM
XNAMEF_REST = "{%s}%%s" % NAMESPACE_REST
XNAMEF_OPENSEARCH = "{%s}%%s" % NAMESPACE_OPENSEARCH

# XML Extended Names
XNAME_FEED = XNAMEF_ATOM % "feed"
XNAME_TITLE = XNAMEF_ATOM % "title"
XNAME_ENTRY = XNAMEF_ATOM % "entry"

opts = None # Command line options

class PackageTestCase(unittest.TestCase):
    def test_names(self):
        names = dir(splunk)

def entry_titles(text):
    """Returns list of atom entry titles from the given atom text."""
    entry = data.load(text).entry
    if not isinstance(entry, list): entry = [entry]
    return [item.title for item in entry]

def uname():
    """Creates a unique name."""
    return str(uuid.uuid1())
    
class BindingTestCase(unittest.TestCase): # Base class
    def setUp(self):
        global opts
        self.context = splunk.connect(**opts.kwargs)

    def tearDown(self):
        pass

    def connect(self, username, password, namespace = None):
        return splunk.connect(
            scheme=self.context.scheme,
            host=self.context.host,
            port=self.context.port,
            username=username,
            password=password,
            namespace=namespace)

    def get(self, path, **kwargs):
        response = self.context.get(path, **kwargs)
        self.assertEqual(response.status, 200)
        return response

    def create(self, path, **kwargs):
        status = kwargs.get('status', 201)
        response = self.context.post(path, **kwargs)
        self.assertEqual(response.status, status)
        return response

    def delete(self, path, **kwargs):
        status = kwargs.get('status', 200)
        response = self.context.delete(path, **kwargs)
        self.assertEqual(response.status, status)
        return response

    def update(self, path, **kwargs):
        status = kwargs.get('status', 200)
        response = self.context.post(path, **kwargs)
        self.assertEqual(response.status, status)
        return response

    def test(self):
        # Just check to make sure the service is alive
        self.assertEqual(self.get("/services").status, 200)

class UsersTestCase(BindingTestCase):
    def eqroles(self, username, roles):
        """Answer if the given user is in exactly the given roles."""
        user = self.user(username)
        roles = roles.split(',')
        if len(roles) != len(user.roles): return False
        for role in roles:
            if not role in user.roles: 
                return False
        return True
        
    def create_user(self, username, password, roles):
        self.assertFalse(username in self.users())
        self.create(PATH_USERS, name=username, password=password, roles=roles)
        self.assertTrue(username in self.users())

    def user(self, username):
        """Returns entity value for given user name."""
        response = self.get("%s/%s" % (PATH_USERS, username))
        self.assertEqual(response.status, 200)
        self.assertEqual(XML(response.body).tag, XNAME_FEED)
        return data.load(response.body).entry.content

    def users(self):
        """Returns a list of user names."""
        response = self.get(PATH_USERS)
        self.assertEqual(response.status, 200)
        self.assertEqual(XML(response.body).tag, XNAME_FEED)
        return entry_titles(response.body)

    def test(self):
        self.get(PATH_USERS)
        self.get(PATH_USERS + "/_new")

    def test_create(self):
        username = uname()
        password = "changeme"
        userpath = "%s/%s" % (PATH_USERS, username)

        # Can't create a user without a role
        self.create(
            PATH_USERS, name=username, password=password,
            status=400)

        # Create a test user
        self.create_user(username, password, "user")
        try:
            # Cannot create a duplicate
            self.create(
                PATH_USERS, name=username, password=password, roles="user", 
                status=400) 

            # Connect as test user
            usercx = self.connect(username, password, "%s:-" % username)

            # Make sure the new context works
            response = usercx.get('/services')
            self.assertEquals(response.status, 200)

            # Test user does not have privs to create another user
            response = usercx.post(
                PATH_USERS, name="flimzo", password="dunno", roles="user")
            self.assertEquals(response.status, 404) # UNDONE: Why is this a 404?

            # User cannot delete themselvse ..
            response = usercx.delete(userpath)
            self.assertEquals(response.status, 404) # UNDONE: Why is this a 404?
    
        finally:
            self.delete(userpath)
            self.assertFalse(username in self.users())

    def test_edit(self):
        username = uname()
        password = "changeme"
        userpath = "%s/%s" % (PATH_USERS, username)

        self.create_user(username, password, "user")
        try:
            self.update(userpath, defaultApp="search")
            self.update(userpath, defaultApp=uname(), status=400)
            self.update(userpath, defaultApp="")
            self.update(userpath, realname="Renzo", email="email.me@now.com")
            self.update(userpath, realname="", email="")
        finally:
            self.delete(userpath)
            self.assertFalse(username in self.users())

    def test_password(self):
        username = uname()
        password = "changeme"
        userpath = "%s/%s" % (PATH_USERS, username)

        # Create a test user
        self.create_user(username, password, "user")
        try:
            # Connect as test user
            usercx = self.connect(username, password, "%s:-" % username)

            # User changes their own password
            response = usercx.post(userpath, password="changed")
            self.assertEqual(response.status, 200)

            # Change it again for giggles ..
            response = usercx.post(userpath, password="changeroo")
            self.assertEqual(response.status, 200)

            # Try to connect with original password ..
            self.assertRaises(splunk.HTTPError,
                self.connect, username, password, "%s:-" % username)

            # Admin changes it back
            self.update(userpath, password=password)

            # And now we can connect again with original password ..
            self.connect(username, password, "%s:-" % username)

        finally:
            self.delete(userpath)
            self.assertFalse(username in self.users())

    def test_roles(self):
        username = uname()
        password = "changeme"
        userpath = "%s/%s" % (PATH_USERS, username)

        # Create a test user
        self.create_user(username, password, "admin")
        try:
            self.assertTrue(self.eqroles(username, "admin"))

            # Update with multiple roles
            self.update(userpath, roles=["power", "user"])
            self.assertTrue(self.eqroles(username, "power,user"))

            # Set back to a single role
            self.update(userpath, roles="user")
            self.assertTrue(self.eqroles(username, "user"))

            # Fail adding unknown roles
            self.update(userpath, roles="__unknown__", status=400)

        finally:
            self.delete(userpath)
            self.assertTrue(username not in self.users())
        
def main(argv):
    global opts
    opts = cmdopts.parser().loadrc(".splunkrc").parse(argv).result
    unittest.main()

if __name__ == "__main__":
    main(sys.argv[1:])
