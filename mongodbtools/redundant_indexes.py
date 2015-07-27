#!/usr/bin/env python

"""
This is a simple script to print out potentially redundant indexes in a mongdb instance.
For example, if an index is defined on {field1:1,field2:1} and there is another index
with just fields {field1:1}, the latter index is not needed since the first index already
indexes the necessary fields.
"""
from pymongo import ReadPreference
from optparse import OptionParser
from distutils.version import StrictVersion
import pymongo

HAS_PYMONGO3 = bool(StrictVersion(pymongo.version) >= StrictVersion('3.0'))

if HAS_PYMONGO3:
    from pymongo import MongoClient
else:
    from pymongo import Connection as MongoClient  # pylint: disable=E0611

def get_cli_options():
    parser = OptionParser(usage="usage: python %prog [options]",
                          description="""This script prints some basic collection stats about the size of the collections and their indexes.""")

    parser.add_option("-H", "--host",
                      dest="host",
                      default="localhost",
                      metavar="HOST",
                      help="MongoDB host")
    parser.add_option("-p", "--port",
                      dest="port",
                      default=27017,
                      metavar="PORT",
                      help="MongoDB port")
    parser.add_option("-d", "--database",
                      dest="database",
                      default="",
                      metavar="DATABASE",
                      help="Target database to generate statistics. All if omitted.")
    parser.add_option("-u", "--user",
                      dest="user",
                      default="",
                      metavar="USER",
                      help="Admin username if authentication is enabled")
    parser.add_option("--password",
                      dest="password",
                      default="",
                      metavar="PASSWORD",
                      help="Admin password if authentication is enabled")
    parser.add_option("--ssl-cert",
                      dest="ssl_certfile",
                      default=None,
                      metavar="CERTIFICATE",
                      help="SSL Certificate to use is SSL is enabled (only with pymongo >= 3)")
    parser.add_option("--ssl-ca-certs",
                      dest="ssl_ca_certs",
                      default=None,
                      metavar="CA",
                      help="SSL Certificate of CA for certificate validation if SSL is enabled (only with pymongo >= 3)")

    (options, args) = parser.parse_args()

    return options

def get_connection(host, port, username, password, ssl_certfile=None, ssl_ca_certs=None):
    userPass = ""
    if username and password:
        userPass = username + ":" + password + "@"

    mongoURI = "mongodb://" + userPass + host + ":" + str(port)

    conn_kwargs = dict(host=mongoURI, read_preference=ReadPreference.SECONDARY)

    if HAS_PYMONGO3:
        conn_kwargs.update(dict(ssl_certfile=ssl_certfile, ssl_ca_certs=ssl_ca_certs))

    return MongoClient(**conn_kwargs)

def main(options):
    connection = get_connection(options.host, options.port, options.user, options.password,
                                options.ssl_certfile, options.ssl_ca_certs)

    def compute_signature(index):
        signature = index["ns"]
        for key in index["key"]:
            try:
                signature += "%s_%s" % (key, int(index["key"][key]))
            except ValueError:
                signature += "%s_%s" % (key, index["key"][key])
        return signature

    def report_redundant_indexes(current_db):
        print("Checking DB: %s" % current_db.name)
        indexes = current_db.system.indexes.find()
        index_map = {}
        for index in indexes:
            signature = compute_signature(index)
            index_map[signature] = index

        for signature in index_map.keys():
            for other_sig in index_map.keys():
                if signature == other_sig:
                    continue
                if other_sig.startswith(signature):
                    print ("Index %s[%s] may be redundant with %s[%s]" % (
                        index_map[signature]["ns"],
                        index_map[signature]["name"],
                        index_map[other_sig]["ns"],
                        index_map[other_sig]["name"]))

    databases= []
    if options.database:
        databases.append(options.database)
    else:
        databases = connection.database_names()

    for db in databases:
        report_redundant_indexes(connection[db])

if __name__ == "__main__":
    options = get_cli_options()
    main(options)
