# LiveATC Downloader

Downloads archived ATC recordings from LiveATC.net.

Currently WIP, may not work correctly for every airport.

## Local usage in this project

Use cookie file mode to avoid Cloudflare 403:

```bash
python main.py stations VHHH --cookie-file ./.local/liveatc_cookie.txt
python main.py download vhhh5 -o ./downloads --cookie-file ./.local/liveatc_cookie.txt
```
