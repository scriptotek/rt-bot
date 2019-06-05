## rt-bot

This repo contains a Python 3 script that delegates tickets from a central Request Tracker (RT) queue to other queues based on a few simple rules.
The script integrates with the Alma API to find additional information about the sender and documents mentioned in the tickets.

For a walkthrough of the script, see [this blog post](http://scriptotek.github.io/blog/2018/08/10/rt-automation.html).

### Usage

- Run `pip install .` to install rtbot from the folder containing this file.
- Make a copy of the `.env.example` file, name it `.env` and fill in the secrets there (login information to RT + an Alma API key with read access to Bibs and Users).
- Run `rtbot`.

