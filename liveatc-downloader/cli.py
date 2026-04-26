import argparse
import sys

parser = argparse.ArgumentParser()

commands = parser.add_subparsers(title='command', dest='command')

parser_stations = commands.add_parser('stations', help='List stations for a given airport')
parser_stations.add_argument('icao', help='Airport ICAO code, e.g. KPDX')
parser_stations.add_argument('--user-agent', help='Optional custom User-Agent header')
parser_stations.add_argument('--cookie', help='Optional raw Cookie header')
parser_stations.add_argument('--cookie-file', help='Optional file path containing Cookie header value')

parser_download = commands.add_parser('download', help='Download MP3 archive for a given station')
parser_download.add_argument('station', help='Station identifier, e.g. kpdx_app')
parser_download.add_argument('-d', '--date', help='Archive date, e.g. Oct-01-2021 defaults to current date (LiveATC only saves archives for 30 days)')
parser_download.add_argument('-t', '--time', help='Archive Zulu time, e.g. 0000Z, defaults to current time')
parser_download.add_argument(
  '-o',
  '--output-dir',
  default='./downloads',
  help='Download folder, defaults to ./downloads'
)
parser_download.add_argument('--user-agent', help='Optional custom User-Agent header')
parser_download.add_argument('--cookie', help='Optional raw Cookie header')
parser_download.add_argument('--cookie-file', help='Optional file path containing Cookie header value')


def get_args():
  return parser.parse_args(sys.argv[1:])
