#!/usr/bin/env python

"""
This script prints some basic collection stats about the size of the
collections and their indexes.
"""

from prettytable import PrettyTable
import psutil
from socket import getfqdn
from pymongo import ReadPreference
from optparse import OptionParser
from distutils.version import StrictVersion
import pymongo

HAS_PYMONGO3 = bool(StrictVersion(pymongo.version) >= StrictVersion('3.0'))

if HAS_PYMONGO3:
    from pymongo import MongoClient
else:
    from pymongo import Connection as MongoClient  # pylint: disable=E0611

def compute_signature(index):
    signature = index["ns"]
    for key in index["key"]:
        signature += "%s_%s" % (key, index["key"][key])
    return signature

def get_collection_stats(database, collection):
    print("Checking DB: %s" % collection.full_name)
    return database.command("collstats", collection.name)

# From http://www.5dollarwhitebox.org/drupal/node/84
def convert_bytes(bytes):
    bytes = float(bytes)
    magnitude = abs(bytes)
    if magnitude >= 1099511627776:
        terabytes = bytes / 1099511627776
        size = '%.2fT' % terabytes
    elif magnitude >= 1073741824:
        gigabytes = bytes / 1073741824
        size = '%.2fG' % gigabytes
    elif magnitude >= 1048576:
        megabytes = bytes / 1048576
        size = '%.2fM' % megabytes
    elif magnitude >= 1024:
        kilobytes = bytes / 1024
        size = '%.2fK' % kilobytes
    else:
        size = '%.2fb' % bytes
    return size

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
                      help="SSL Certificate to use is SSL is enabled")
    parser.add_option("--ssl-ca-certs",
                      dest="ssl_ca_certs",
                      default=None,
                      metavar="CA",
                      help="SSL Certificate of CA for certificate validation if SSL is enabled")

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

def main(options=None):
    if options is None:
        options = get_cli_options()

    summary_stats = {
        "count" : 0,
        "size" : 0,
        "indexSize" : 0
    }
    all_stats = []

    connection = get_connection(options.host, options.port, options.user, options.password,
                                options.ssl_certfile, options.ssl_ca_certs)

    all_db_stats = {}

    databases = []
    if options.database:
        databases.append(options.database)
    else:
        databases = connection.database_names()

    for db in databases:
        # FIXME: Add an option to include oplog stats.
        if db == "local":
            continue

        database = connection[db]
        all_db_stats[database.name] = []
        for collection_name in database.collection_names():
            stats = get_collection_stats(database, database[collection_name])
            all_stats.append(stats)
            all_db_stats[database.name].append(stats)

            summary_stats["count"] += stats["count"]
            summary_stats["size"] += stats["size"]
            summary_stats["indexSize"] += stats.get("totalIndexSize", 0)

    x = PrettyTable(["Collection", "Index","% Size", "Index Size"])
    x.align["Collection"] = "l"
    x.align["Index"] = "l"
    x.align["% Size"] = "r"
    x.align["Index Size"] = "r"
    x.padding_width = 1

    print

    index_size_mapping = {}
    for db in all_db_stats:
        db_stats = all_db_stats[db]
        count = 0
        for stat in db_stats:
            count += stat["count"]
            for index in stat["indexSizes"]:
                index_size = stat["indexSizes"].get(index, 0)
                row = [stat["ns"], index,
                          "%0.1f%%" % ((index_size / float(summary_stats["indexSize"])) * 100),
                  convert_bytes(index_size)]
                index_size_mapping[index_size] = row
                x.add_row(row)


    print("Index Overview")
    print(x.get_string(sortby="Collection"))

    print
    print("Top 5 Largest Indexes")
    x = PrettyTable(["Collection", "Index","% Size", "Index Size"])
    x.align["Collection"] = "l"
    x.align["Index"] = "l"
    x.align["% Size"] = "r"
    x.align["Index Size"] = "r"
    x.padding_width = 1

    top_five_indexes = sorted(index_size_mapping.keys(), reverse=True)[0:5]
    for size in top_five_indexes:
        x.add_row(index_size_mapping.get(size))
    print(x)
    print

    print("Total Documents: %s" % summary_stats["count"])
    print("Total Data Size: %s" % convert_bytes(summary_stats["size"]))
    print("Total Index Size: %s" % convert_bytes(summary_stats["indexSize"]))

    # this is only meaningful if we're running the script on localhost
    if options.host == "localhost" or options.host == getfqdn():
        ram_headroom = psutil.phymem_usage()[0] - summary_stats["indexSize"]
        print("RAM Headroom: %s" % convert_bytes(ram_headroom))
        print("RAM Used: %s (%s%%)" % (convert_bytes(psutil.phymem_usage()[1]), psutil.phymem_usage()[3]))
        print("Available RAM Headroom: %s" % convert_bytes((100 - psutil.phymem_usage()[3]) / 100 * ram_headroom))

if __name__ == "__main__":
    options = get_cli_options()
    main(options)
