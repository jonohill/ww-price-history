Hacky python script to download Woolworths NZ order confirmation emails, scrape the purchased items, and output as CSV. Only tested against Gmail. Uses uv for dependency management.

## Run

Set at least IMAP_USERNAME and IMAP_PASSWORD in the environment, IMAP_HOST if not using Gmail. The password should be an app password for Gmail.

```shell
uv run python scrape_emails.py
```
Output is to stdout. You could, e.g. pipe this to a sqlite database for further analysis.

```shell
uv run python scrape_emails.py | sqlite3 -csv data.sqlite ".import '|cat -' price_history"
```
