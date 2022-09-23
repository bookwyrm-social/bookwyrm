#!/bin/bash

# exit on errors
set -e

echo Installing dependencies 
apt install postgresql redis nginx python3-venv libpq-dev

echo
echo Removing old bookwyrm install (not database, just config and files)
sleep 2
rm -r /opt/bookwyrm

echo
echo Creating new bookwyrm install dir in /opt/bookwyrm
mkdir /opt/bookwyrm
cd /opt/bookwyrm
git clone https://github.com/bookwyrm-social/bookwyrm ./
git checkout production
cp .env.example .env

echo
echo Making the python virtual enviroment
mkdir venv
python3 -m venv /opt/bookwyrm/venv

echo
echo Adding a system "bookwyrm" user
useradd bookwyrm -r

echo
echo "Run these to make your database:
CREATE USER bookwyrm WITH PASSWORD 'yourbookwyrmpostgresqlpassword';

CREATE DATABASE bookwyrm TEMPLATE template0 ENCODING 'UNICODE';

ALTER DATABASE bookwyrm OWNER TO bookwyrm;

GRANT ALL PRIVILEGES ON DATABASE bookwyrm TO bookwyrm;

\q
"
sudo -i -u postgres psql

echo
echo About to open the .env configuration file.
echo
echo To run WITHOUT nginx, turn debug on (not recommended) and you will need a custom run command (stated later)
echo Make sure to set you postgresql user and password correctly (host should be "localhost")
echo Your redis password(s) should be nothing by default
echo
echo You can modify this file later if nothing works
$EDITOR .env

echo
echo Installing the python requirements with pip
/opt/bookwyrm/venv/bin/pip3 install -r requirements.txt
/opt/bookwyrm/venv/bin/python3 manage.py migrate
/opt/bookwyrm/venv/bin/python3 manage.py initdb
/opt/bookwyrm/venv/bin/python3 manage.py collectstatic --no-input
/opt/bookwyrm/venv/bin/python3 manage.py admin_code

echo
echo Changing the owner of /opt/bookwyrm to the new bookwyrm user
sudo chown -R /opt/bookwyrm bookwyrm:bookwyrm

echo
echo Copying the nginx configs to /etc/nginx/sites-available/bookwyrm.nginx and /etc/nginx/conf.d/server_config
echo Remember to change the domain and restart nginx
cp /opt/bookwyrm/nginx/dockerless-production /etc/nginx/sites-available/bookwyrm.nginx
ln -s /etc/nginx/sites-available/bookwyrm.nginx /etc/nginx/sites-enabled/bookwyrm.nginx
cp /opt/bookwyrm/nginx/server_config /etc/nginx/conf.d/server_config

sleep 1
echo
echo Install complete. Please use dockerless-run.sh to run the server. You may wish to wrap that in a systemd/equiv script
