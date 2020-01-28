# fedireads

Social reading and reviewing, decentralized with ActivityPub

## Setting up the developer environment
You will need postgres installed and running on your computer.

``` bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
createdb fedireads
```

Create the psql user in `psql fedireads`:
``` psql
CREATE ROLE fedireads WITH LOGIN PASSWORD 'fedireads';
GRANT ALL PRIVILEGES ON DATABASE fedireads TO fedireads;
```

Initialize the database
``` bash
./rebuilddb.sh
```
This creates two users, `mouse@your-domain.com` with password `password123` and `rat@your-domain.com` with password `ratword`.

And go to the app at localhost:8000

For most testing, you'll want to use ngrok. Remember to set the DOMAIN in settings.py to your ngrok domain.
