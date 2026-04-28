import argparse
import sys

parser = argparse.ArgumentParser(description='LiveATC 历史音频下载工具')

commands = parser.add_subparsers(title='command', dest='command', help='可用命令')

# stations 命令 - 列出机场的电台
parser_stations = commands.add_parser('stations', help='列出指定机场的所有电台')
parser_stations.add_argument('icao', help='机场 ICAO 代码，例如 KPDX 或 VHHH')
parser_stations.add_argument('--user-agent', help='自定义 User-Agent 头')
parser_stations.add_argument('--cookie', help='自定义 Cookie 头')
parser_stations.add_argument('--cookie-file', help='包含 Cookie 头值的文件路径')

# download 命令 - 下载单个音频
parser_download = commands.add_parser('download', help='下载指定电台和时间的音频档案')
parser_download.add_argument('station', help='电台标识符，例如 kpdx_app')
parser_download.add_argument('-d', '--date', help='档案日期，格式 Oct-01-2021，默认为当前日期')
parser_download.add_argument('-t', '--time', help='档案 Zulu 时间，格式 0000Z，默认为当前时间')
parser_download.add_argument(
  '-o',
  '--output-dir',
  default='./downloads',
  help='下载目录，默认为 ./downloads'
)
parser_download.add_argument('--user-agent', help='自定义 User-Agent 头')
parser_download.add_argument('--cookie', help='自定义 Cookie 头')
parser_download.add_argument('--cookie-file', help='包含 Cookie 头值的文件路径')

# list 命令 - 列出历史音频
parser_list = commands.add_parser('list', help='列出电台的历史音频档案')
parser_list.add_argument('station', help='电台标识符，例如 kpdx_app')
parser_list.add_argument('--user-agent', help='自定义 User-Agent 头')
parser_list.add_argument('--cookie', help='自定义 Cookie 头')
parser_list.add_argument('--cookie-file', help='包含 Cookie 头值的文件路径')

# download-range 命令 - 下载日期范围内的音频
parser_download_range = commands.add_parser(
  'download-range',
  help='下载指定日期范围内的音频档案（注意：LiveATC 仅保存最近 30 天的档案）'
)
parser_download_range.add_argument('station', help='电台标识符，例如 kpdx_app')
parser_download_range.add_argument(
  '--start-date',
  required=True,
  help='开始日期，格式 YYYY-MM-DD，例如 2021-10-01'
)
parser_download_range.add_argument(
  '--end-date',
  required=True,
  help='结束日期，格式 YYYY-MM-DD，例如 2021-10-05'
)
parser_download_range.add_argument(
  '--times',
  help='要下载的 Zulu 时间列表，用逗号分隔，例如 0000Z,0030Z,0100Z。默认下载所有 30 分钟时段'
)
parser_download_range.add_argument(
  '-o',
  '--output-dir',
  default='./downloads',
  help='下载目录，默认为 ./downloads'
)
parser_download_range.add_argument('--user-agent', help='自定义 User-Agent 头')
parser_download_range.add_argument('--cookie', help='自定义 Cookie 头')
parser_download_range.add_argument('--cookie-file', help='包含 Cookie 头值的文件路径')


def get_args():
  return parser.parse_args(sys.argv[1:])
