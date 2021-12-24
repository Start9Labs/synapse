#!/bin/bash

set -e

# checks
if [ "$(whoami)" != "root" ]; then
	1>&2 echo Must run as root
	exit 1
fi
if [ "$(lsb_release -is)" != "Ubuntu" ] || [ "$(lsb_release -rs)" != "20.04" ]; then
	1>&2 echo This script is built for Ubuntu 20.04. It will likely not work on your system.
	exit 1
fi

read -p "Domain name: "
DOMAIN=$REPLY

echo Installing Docker...
apt-get update
apt-get install -y docker.io docker-compose

echo Fetching Tor Enabled Synapse Image...
docker pull "start9/synapse:v1.47.1"

read -p "Data Directory Location [/root]: "
DATADIR=$REPLY
if [ -z "$DATADIR" ]; then
	DATADIR="/root"
fi
if ! [ -d "$DATADIR" ]; then
	1>&2 echo Directory does not exist
	exit 1
fi
DATADIR="$DATADIR/synapse"

if [ -d "$DATADIR" ]; then
	1>&2 echo "$DATADIR" already exists. Move or delete before proceeding to setup a fresh instance.
	exit 1
fi

mkdir "$DATADIR"
mkdir "$DATADIR/synapse-data"
docker run -it --rm --mount type=bind,src="$DATADIR/synapse-data",dst=/data -e SYNAPSE_SERVER_NAME="$DOMAIN" -e SYNAPSE_REPORT_STATS=no "start9/synapse:v1.47.1" generate
cat >> "$DATADIR/synapse-data/homeserver.yaml" << EOT

federation_certificate_verification_whitelist:
  - '*.onion'
EOT

cat > "$DATADIR/docker-compose.yml" << EOT
version: '3'
services:
  synapse_clearnet:
    image: start9/synapse:v1.47.1
    restart: unless-stopped
    environment:
      - https_proxy=privoxy:8118
    volumes:
      - ./synapse-data:/data
    depends_on:
      - tor
      - privoxy
    ports:
      - 8008:8008/tcp
    logging:
        driver: journald
  tor:
    image: sirboops/tor
    restart: unless-stopped

  privoxy:
    image: sirboops/privoxy
    restart: unless-stopped
    volumes:
      - ./priv-config:/opt/config
EOT

cat > "$DATADIR/priv-config" << EOT
listen-address  0.0.0.0:8118

logdir /var/log
logfile privoxy.log
confdir /opt
debug 9217

forward .   .
forward-socks5t .onion  tor:9050    .
EOT

echo Installing NGINX and Certbot...
apt-get install -y nginx python3-certbot-nginx
certbot certonly --nginx -d "$DOMAIN"

cat > "/etc/nginx/conf.d/matrix.conf" << EOT
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    location / {
        proxy_pass http://localhost:8008;
        proxy_set_header X-Forwarded-For \$remote_addr;
        # Nginx by default only allows file uploads up to 1M in size
        # Increase client_max_body_size to match max_upload_size defined in homeserver.yaml
        client_max_body_size 10M;
    }
}

# This is used for Matrix Federation
# which is using default TCP port '8448'
server {
    listen 8448 ssl;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    location / {
        proxy_pass http://localhost:8008;
        proxy_set_header X-Forwarded-For \$remote_addr;
    }
}
EOT

sed -i 's/ *#* *server_names_hash_bucket_size \+[0-9]\+/server_names_hash_bucket_size 128/g' /etc/nginx/nginx.conf
nginx -t

systemctl restart nginx
