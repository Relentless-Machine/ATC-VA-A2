#!/usr/bin/env python3

from pathlib import Path
from cli import get_args
from liveatc import get_stations, download_archive
from datetime import datetime, timedelta

# Gets the last Zulu period of 30 minutes
# E.g. if time is 10:35:00, it will return 10:00:00
def get_last_zulu_period(date, minutes=30):
  return date - timedelta(minutes=minutes) - (date - datetime.min) % timedelta(minutes=minutes)


def resolve_cookie(args):
  if args.cookie:
    return args.cookie
  if getattr(args, "cookie_file", None):
    content = Path(args.cookie_file).read_text(encoding="utf-8").strip()
    return content or None
  return None


def stations(args):
  cookie = resolve_cookie(args)
  stations = get_stations(args.icao, user_agent=args.user_agent, cookie=cookie)
  for station in stations:
    print(f"[{station['identifier']}] - {station['title']}")

    for freq in station['frequencies']:
      print(f"\t{freq['title']} - {freq['frequency']}")

    print()


def download(args):
  cookie = resolve_cookie(args)
  date_now = datetime.utcnow()

  last_period = get_last_zulu_period(date_now)

  if not args.date and not args.time:
    date = last_period.strftime('%b-%d-%Y')
    time = last_period.strftime('%H%MZ')
  else:
    date = args.date if args.date else date_now.strftime('%b-%d-%Y')
    time = args.time if args.time else last_period.strftime('%H%MZ')

  download_archive(
    args.station,
    date,
    time,
    output_dir=args.output_dir,
    user_agent=args.user_agent,
    cookie=cookie,
  )


if __name__ == '__main__':
  args = get_args()
  print(args)

  if args.command == 'stations':
    stations(args)
  elif args.command == 'download':
    download(args)
