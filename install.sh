GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Cek apakah dijalankan sebagai root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Harap jalankan script ini sebagai root (sudo bash install.sh)${NC}"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
local_ip=$(hostname -I | awk '{print $1}')

echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}==================  KKK   KKK   NNNN    NNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}==================  KKK  KKK    NNNNN   NNN   SS          ==================${NC}"
echo -e "${GREEN}==================  KKKKKKK     NNN NN  NNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}==================  KKK  KKK    NNN  NN NNN           SS  ==================${NC}"
echo -e "${GREEN}==================  KKK   KKK   NNN   NNNNN   SSSSSSSSSS  ==================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}========================= . Info 081-947-215-703 ===========================${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}${NC}"
echo -e "${GREEN}Autoinstall GenieACS.${NC}"
echo -e "${GREEN}${NC}"
echo -e "${GREEN}============================================================================${NC}"
echo -e "${RED}${NC}"
echo -e "${GREEN} Apakah anda ingin melanjutkan? (y/n)${NC}"
read confirmation

if [ "$confirmation" != "y" ]; then
    echo -e "${GREEN}Install dibatalkan. Tidak ada perubahan dalam ubuntu server anda.${NC}"
    exit 1
fi
for ((i = 5; i >= 1; i--)); do
	sleep 1
    echo "Melanjutkan dalam $i. Tekan ctrl+c untuk membatalkan"
done

echo -e "${YELLOW}Memulai instalasi GenieACS...${NC}"
echo "Menginstal Node.js..."
curl -sL https://deb.nodesource.com/setup_20.x -o /tmp/nodesource_setup.sh
bash /tmp/nodesource_setup.sh
apt install -y nodejs
node -v

echo "Menginstal MongoDB..."
curl -fsSL https://www.mongodb.org/static/pgp/server-4.4.asc | apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu focal/mongodb-org/4.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-4.4.list
apt update
apt install -y mongodb-org mongodb-org-tools
systemctl start mongod.service
systemctl enable mongod

mongo --eval 'db.runCommand({ connectionStatus: 1 })' 2>/dev/null || mongosh --eval 'db.runCommand({ connectionStatus: 1 })' 2>/dev/null || true

#GenieACS
if ! systemctl is-active --quiet genieacs-{cwmp,fs,ui,nbi}; then
    echo -e "${GREEN}================== Menginstall genieACS CWMP, FS, NBI, UI ==================${NC}"
    npm install -g genieacs@1.2.13

    BIN_DIR=$(dirname "$(which genieacs-cwmp 2>/dev/null || echo "/usr/bin/genieacs-cwmp")")
    if [ "$BIN_DIR" != "/usr/bin" ] && [ -f "$BIN_DIR/genieacs-cwmp" ]; then
        ln -sf "$BIN_DIR"/genieacs-* /usr/bin/
    fi

    useradd --system --no-create-home --user-group genieacs 2>/dev/null || true
    mkdir -p /opt/genieacs
    mkdir -p /opt/genieacs/ext
    chown -R genieacs:genieacs /opt/genieacs/ext
    cat << EOF > /opt/genieacs/genieacs.env
GENIEACS_CWMP_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-cwmp-access.log
GENIEACS_NBI_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-nbi-access.log
GENIEACS_FS_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-fs-access.log
GENIEACS_UI_ACCESS_LOG_FILE=/var/log/genieacs/genieacs-ui-access.log
GENIEACS_DEBUG_FILE=/var/log/genieacs/genieacs-debug.yaml
GENIEACS_EXT_DIR=/opt/genieacs/ext
GENIEACS_UI_JWT_SECRET=secret
EOF
    chown genieacs:genieacs /opt/genieacs/genieacs.env
    chown -R genieacs:genieacs /opt/genieacs
    chmod 600 /opt/genieacs/genieacs.env
    mkdir -p /var/log/genieacs
    chown -R genieacs:genieacs /var/log/genieacs

    # create systemd unit files
## CWMP
    cat << EOF > /etc/systemd/system/genieacs-cwmp.service
[Unit]
Description=GenieACS CWMP
After=network.target

[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-cwmp

[Install]
WantedBy=default.target
EOF

## NBI
    cat << EOF > /etc/systemd/system/genieacs-nbi.service
[Unit]
Description=GenieACS NBI
After=network.target
 
[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-nbi
 
[Install]
WantedBy=default.target
EOF

## FS
    cat << EOF > /etc/systemd/system/genieacs-fs.service
[Unit]
Description=GenieACS FS
After=network.target
 
[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-fs
 
[Install]
WantedBy=default.target
EOF

## UI
    cat << EOF > /etc/systemd/system/genieacs-ui.service
[Unit]
Description=GenieACS UI
After=network.target
 
[Service]
User=genieacs
EnvironmentFile=/opt/genieacs/genieacs.env
ExecStart=/usr/bin/genieacs-ui
 
[Install]
WantedBy=default.target
EOF

# config logrotate
 cat << EOF > /etc/logrotate.d/genieacs
/var/log/genieacs/*.log /var/log/genieacs/*.yaml {
    daily
    rotate 30
    compress
    delaycompress
    dateext
}
EOF
    echo -e "${GREEN}========== Install APP GenieACS selesai... ==============${NC}"
    systemctl daemon-reload
    systemctl enable --now genieacs-{cwmp,fs,ui,nbi}
    systemctl start genieacs-{cwmp,fs,ui,nbi}    
    echo -e "${GREEN}================== Sukses genieACS CWMP, FS, NBI, UI ==================${NC}"
else
    echo -e "${GREEN}============================================================================${NC}"
    echo -e "${GREEN}=================== GenieACS sudah terinstall sebelumnya. ==================${NC}"
fi

NODE_MODULES_DIR=$(npm root -g 2>/dev/null || echo "/usr/lib/node_modules")

if [ -d "$SCRIPT_DIR/genieacs" ]; then
    echo -e "${YELLOW}Meng-copy modul GenieACS Multitab...${NC}"
    cp -r "$SCRIPT_DIR/genieacs" "$NODE_MODULES_DIR/"
    echo -e "${GREEN}✅ Multitab berhasil di-copy ke $NODE_MODULES_DIR/genieacs${NC}"
fi

if [ -d "$SCRIPT_DIR/db" ]; then
    echo -e "${YELLOW}Melakukan restore database virtual parameter...${NC}"
    mongorestore --db genieacs --drop "$SCRIPT_DIR/db" 2>/dev/null || echo -e "${RED}Gagal restore database. Pastikan mongorestore terinstall.${NC}"
fi

systemctl daemon-reload
systemctl restart genieacs-{cwmp,fs,ui,nbi}

#Sukses
echo -e "${GREEN}============================================================================${NC}"
echo -e "${GREEN}========== GenieACS UI akses port 3000: http://$local_ip:3000 ============${NC}"
echo -e "${GREEN}=================== Informasi: Whatsapp 081947215703 =======================${NC}"
echo -e "${GREEN}============================================================================${NC}"
