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

# This simplistic example shows how to use the Splunk binding module to
# create a convenient 'wrapper" interface around the Splunk REST APIs.
# The example below binds to a sampling of endpoings, demonstrating access to
# resource collections, entities and "method-like" endpoints.

from splunk.binding import connect, Collection, Entity

import tools.cmdopts as cmdopts

class Services:
    def __init__(self, context):
        self.apps = Collection(context, "apps/local")
        self.roles = Collection(context, "authorization/roles")
        self.users = Collection(context, "authentication/users")
        self.indexes = Collection(context, "data/indexes")
        self.info = context.bind("server/info", "get")
        self.settings = Entity(context, "server/settings")
        self.export = context.bind("search/jobs/export", "post")

    def search(self, query, **kwargs):
        return self.export(search=query, **kwargs)

def main(argv):
    opts = cmdopts.parser().loadrc(".splunkrc").parse(sys.argv[1:]).result
    services = Services(connect(**opts.kwargs))
    assert services.apps().status == 200
    assert services.roles().status == 200
    assert services.users().status == 200
    assert services.indexes().status == 200
    assert services.info().status == 200
    assert services.settings().status == 200
    assert services.search("search 404").status == 200

if __name__ == "__main__":
    import sys
    main(sys.argv[1:])