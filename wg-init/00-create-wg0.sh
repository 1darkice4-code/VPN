#!/bin/sh
CONFIG_FILE=/config/wg0.conf

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Создаём wg0.conf..."
  umask 077
  PRIV_KEY=$(wg genkey)
  PUB_KEY=$(echo "$PRIV_KEY" | wg pubkey)

  cat <<EOF > $CONFIG_FILE
[Interface]
Address = 10.66.66.1/24
ListenPort = 51831
PrivateKey = $PRIV_KEY
DNS = 1.1.1.1, 8.8.8.8
MTU = 1420
EOF

  echo "Конфигурация wg0 создана"
fi